"""
SQL Investigation Agent using LangGraph.
Performs multi-step SQL investigations to answer analytical questions.
"""
from typing import Any, Literal, TypedDict

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agents.sql_agent.executor import ExecutionResult, execute_sql
from agents.sql_agent.generator import SQLGenerationResult, generate_sql
from agents.sql_agent.schema import get_relevant_schema
from agents.sql_agent.validator import validate_sql
from config.settings import settings


def _create_llm():
    """Create LLM instance based on provider (OpenAI or OpenRouter)."""
    if settings.llm_provider == "openrouter":
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            default_headers={
                "HTTP-Referer": settings.openrouter_http_referer or "",
                "X-Title": settings.openrouter_x_title or "",
            } if settings.openrouter_http_referer or settings.openrouter_x_title else None,
        )
    else:
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.openai_api_key,
            organization=settings.openai_organization,
        )


class SQLAgentState(TypedDict):
    """State for SQL Agent investigation."""
    question: str
    step: int
    max_steps: int
    sql_queries: list[dict[str, Any]]
    sql_results: list[dict[str, Any]]
    current_hypothesis: str
    context: str
    done: bool
    error: str | None
    final_answer: str


class SQLInvestigationAgent:
    """LangGraph-based SQL investigation agent."""

    def __init__(self):
        self.llm = _create_llm()
        self.max_steps = settings.agent_max_steps
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(SQLAgentState)

        # Nodes
        workflow.add_node("generate_sql", self._generate_sql_node)
        workflow.add_node("validate_sql", self._validate_sql_node)
        workflow.add_node("execute_sql", self._execute_sql_node)
        workflow.add_node("interpret_results", self._interpret_results_node)
        workflow.add_node("decide_next_step", self._decide_next_step_node)

        # Edges
        workflow.set_entry_point("generate_sql")
        workflow.add_edge("generate_sql", "validate_sql")
        workflow.add_conditional_edges(
            "validate_sql",
            self._validation_router,
            {
                "valid": "execute_sql",
                "invalid": "generate_sql",  # Retry
            }
        )
        workflow.add_edge("execute_sql", "interpret_results")
        workflow.add_conditional_edges(
            "interpret_results",
            self._continuation_router,
            {
                "continue": "decide_next_step",
                "done": END,
            }
        )
        workflow.add_edge("decide_next_step", "generate_sql")

        return workflow.compile(checkpointer=MemorySaver())

    def _validation_router(self, state: SQLAgentState) -> Literal["valid", "invalid"]:
        """Route based on validation result."""
        last_validation = state.get("sql_queries", [{}])[-1].get("validation", {})
        return "valid" if last_validation.get("is_valid", False) else "invalid"

    def _continuation_router(self, state: SQLAgentState) -> Literal["continue", "done"]:
        """Decide whether to continue investigation."""
        if state.get("done", False):
            return "done"
        if state.get("step", 0) >= state.get("max_steps", self.max_steps):
            return "done"
        if state.get("error"):
            return "done"
        return "continue"

    def _generate_sql_node(self, state: SQLAgentState) -> SQLAgentState:
        """Generate SQL for the current question."""
        question = state.get("question", "")
        context = state.get("context", "")

        # Get relevant schema
        schema_info = get_relevant_schema(question)

        # Build context from previous steps
        full_context = context
        if state["sql_queries"]:
            full_context += "\n\nPrevious queries and results:"
            for i, (q, r) in enumerate(zip(state["sql_queries"], state["sql_results"])):
                full_context += f"\nStep {i+1}: {q.get('sql', '')}"
                full_context += f"\nResult: {r.get('row_count', 0)} rows"
                if r.get("data"):
                    full_context += f"\nSample: {r['data'][:3]}"

        # Generate SQL
        result: SQLGenerationResult = generate_sql(question, full_context)

        # Add to history
        new_state = state.copy()
        new_state["sql_queries"] = state["sql_queries"] + [{
            "step": state["step"] + 1,
            "question": question,
            "sql": result.sql,
            "explanation": result.explanation,
            "tables_used": result.tables_used,
            "confidence": result.confidence,
            "validation": {},  # Will be filled by validate node
        }]

        return new_state

    def _validate_sql_node(self, state: SQLAgentState) -> SQLAgentState:
        """Validate the generated SQL."""
        last_query = state["sql_queries"][-1]
        sql = last_query.get("sql", "")

        validation = validate_sql(sql)

        new_state = state.copy()
        new_state["sql_queries"][-1]["validation"] = {
            "is_valid": validation.is_valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "tables_referenced": list(validation.tables_referenced) if validation.tables_referenced else [],
            "columns_referenced": list(validation.columns_referenced) if validation.columns_referenced else [],
            "complexity_score": validation.complexity_score,
        }

        if not validation.is_valid:
            new_state["error"] = f"SQL validation failed: {'; '.join(validation.errors)}"

        return new_state

    def _execute_sql_node(self, state: SQLAgentState) -> SQLAgentState:
        """Execute the validated SQL."""
        last_query = state["sql_queries"][-1]
        sql = last_query.get("sql", "")

        result: ExecutionResult = execute_sql(sql)

        new_state = state.copy()
        new_state["sql_results"] = state["sql_results"] + [{
            "step": state["step"] + 1,
            "success": result.success,
            "columns": result.columns,
            "data": result.data,
            "row_count": result.row_count,
            "truncated": result.truncated,
            "execution_time_ms": result.execution_time_ms,
            "error": result.error,
        }]

        if not result.success:
            new_state["error"] = f"SQL execution failed: {result.error}"

        return new_state

    def _interpret_results_node(self, state: SQLAgentState) -> SQLAgentState:
        """Interpret query results and update hypothesis."""
        last_result = state["sql_results"][-1]

        if not last_result.get("success", False):
            return state

        # Use LLM to interpret results
        interpretation_prompt = f"""
        Analyze the SQL query results and provide insights.
        
        Question: {state['question']}
        Current Hypothesis: {state.get('current_hypothesis', 'None')}
        
        Query: {state['sql_queries'][-1].get('sql', '')}
        Explanation: {state['sql_queries'][-1].get('explanation', '')}
        
        Results: {last_result.get('row_count', 0)} rows
        Columns: {last_result.get('columns', [])}
        Sample Data: {last_result.get('data', [])[:5]}
        
        Provide:
        1. Key findings
        2. Updated hypothesis
        3. Whether investigation is complete
        4. Next question to investigate (if any)
        
        Return JSON with keys: findings, hypothesis, done, next_question
        """

        response = self.llm.invoke([HumanMessage(content=interpretation_prompt)])

        try:
            import json
            interpretation = json.loads(response.content)
        except json.JSONDecodeError:
            interpretation = {
                "findings": "Could not parse interpretation",
                "hypothesis": state.get("current_hypothesis", ""),
                "done": True,
                "next_question": "",
            }

        new_state = state.copy()
        new_state["current_hypothesis"] = interpretation.get("hypothesis", state.get("current_hypothesis", ""))
        new_state["done"] = interpretation.get("done", True)
        new_state["context"] = state.get("context", "") + f"\n\nStep {state['step']+1} findings: {interpretation.get('findings', '')}"

        if interpretation.get("next_question"):
            new_state["question"] = interpretation["next_question"]

        return new_state

    def _decide_next_step_node(self, state: SQLAgentState) -> SQLAgentState:
        """Increment step counter."""
        new_state = state.copy()
        new_state["step"] = state["step"] + 1
        return new_state

    def investigate(self, question: str, thread_id: str = "default") -> dict[str, Any]:
        """Run a full investigation."""
        initial_state = SQLAgentState(
            question=question,
            step=0,
            max_steps=self.max_steps,
            sql_queries=[],
            sql_results=[],
            current_hypothesis="",
            context="",
            done=False,
            error=None,
            final_answer="",
        )

        config = {"configurable": {"thread_id": thread_id}}
        result = self.graph.invoke(initial_state, config)

        # Generate final answer
        if result.get("sql_results"):
            final_answer = self._generate_final_answer(result)
        else:
            final_answer = "Investigation failed to produce results."

        return {
            "question": question,
            "final_answer": final_answer,
            "hypothesis": result.get("current_hypothesis", ""),
            "steps": list(zip(result.get("sql_queries", []), result.get("sql_results", []))),
            "error": result.get("error"),
            "confidence": self._calculate_confidence(result),
        }

    def _generate_final_answer(self, state: SQLAgentState) -> str:
        """Generate final answer from investigation results."""
        summary_prompt = f"""
        Summarize the investigation findings.
        
        Original Question: {state['question']}
        
        Steps taken:
        """
        for i, (q, r) in enumerate(zip(state.get("sql_queries", []), state.get("sql_results", []))):
            summary_prompt += f"\n{i+1}. {q.get('explanation', '')}"
            summary_prompt += f"\n   SQL: {q.get('sql', '')[:200]}..."
            summary_prompt += f"\n   Result: {r.get('row_count', 0)} rows"
            if r.get("data"):
                summary_prompt += f"\n   Key data: {r['data'][:3]}"

        summary_prompt += f"""
        
        Hypothesis: {state.get('current_hypothesis', '')}
        
        Provide a clear, concise answer to the original question with evidence.
        """

        response = self.llm.invoke([HumanMessage(content=summary_prompt)])
        return response.content

    def _calculate_confidence(self, state: SQLAgentState) -> float:
        """Calculate overall confidence in the investigation."""
        if not state.get("sql_results"):
            return 0.0

        successful_steps = sum(1 for r in state["sql_results"] if r.get("success", False))
        total_steps = len(state["sql_results"])

        if total_steps == 0:
            return 0.0

        base_confidence = successful_steps / total_steps

        # Adjust for validation warnings
        warning_penalty = 0
        for q in state.get("sql_queries", []):
            validation = q.get("validation", {})
            warning_penalty += len(validation.get("warnings", [])) * 0.05

        return max(0.0, min(1.0, base_confidence - warning_penalty))


# Convenience function
def run_sql_investigation(question: str, thread_id: str = "default") -> dict[str, Any]:
    """Run a SQL investigation."""
    agent = SQLInvestigationAgent()
    return agent.investigate(question, thread_id)
