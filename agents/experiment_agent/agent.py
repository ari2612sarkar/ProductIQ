"""
Experiment Agent - Investigates A/B experiments with deterministic statistics.
"""
from typing import Dict, List, Any, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from agents.experiment_agent.analyzer import ExperimentAnalyzer, analyze_experiment_simple
from agents.experiment_agent.statistics import ExperimentResult
from config.settings import settings
from db.connection import get_sync_session


def _create_llm():
    """Create LLM instance based on provider (OpenAI or OpenRouter)."""
    if settings.llm_provider == "openrouter":
        from langchain_openai import ChatOpenAI
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
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.openai_api_key,
            organization=settings.openai_organization,
        )


@dataclass
class ExperimentAgentState:
    """State for Experiment Agent."""
    question: str
    experiment_id: Optional[str] = None
    metric: str = "conversion"
    metric_type: Literal["proportion", "mean", "ratio"] = "proportion"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    experiment_data: Optional[Dict[str, Any]] = None
    analysis_result: Optional[Dict[str, Any]] = None
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    done: bool = False


class ExperimentAgent:
    """Agent for investigating A/B experiments with deterministic statistics."""
    
    def __init__(self):
        self.llm = _create_llm()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(ExperimentAgentState)
        
        # Nodes
        workflow.add_node("identify_experiment", self._identify_experiment_node)
        workflow.add_node("determine_metrics", self._determine_metrics_node)
        workflow.add_node("run_analysis", self._run_analysis_node)
        workflow.add_node("interpret_results", self._interpret_results_node)
        workflow.add_node("synthesize_evidence", self._synthesize_evidence_node)
        
        # Edges
        workflow.set_entry_point("identify_experiment")
        workflow.add_edge("identify_experiment", "determine_metrics")
        workflow.add_edge("determine_metrics", "run_analysis")
        workflow.add_edge("run_analysis", "interpret_results")
        workflow.add_edge("interpret_results", "synthesize_evidence")
        workflow.add_edge("synthesize_evidence", END)
        
        return workflow.compile()
    
    def _identify_experiment_node(self, state: ExperimentAgentState) -> ExperimentAgentState:
        """Identify relevant experiment from question."""
        if state.experiment_id:
            return state
        
        # Use LLM to identify experiment
        prompt = f"""
        Analyze the question and identify if it references a specific A/B experiment.
        
        Question: {state.question}
        
        If the question mentions an experiment name, ID, or describes an experiment, 
        return the experiment identifier. Otherwise, return "auto" to search for relevant experiments.
        
        Return only the experiment ID/name or "auto".
        """
        
        response = self.llm.invoke([HumanMessage(content=prompt)])
        experiment_ref = response.content.strip()
        
        return ExperimentAgentState(
            question=state.question,
            experiment_id=experiment_ref if experiment_ref != "auto" else None,
            metric=state.metric,
            metric_type=state.metric_type,
            start_date=state.start_date,
            end_date=state.end_date,
        )
    
    def _determine_metrics_node(self, state: ExperimentAgentState) -> ExperimentAgentState:
        """Determine which metrics to analyze."""
        if state.experiment_id:
            # Get recommended metrics from experiment
            with get_sync_session() as session:
                analyzer = ExperimentAnalyzer(session)
                experiment = analyzer.get_experiment(state.experiment_id)
                if experiment:
                    recommended = analyzer.get_recommended_metrics(experiment)
                    return ExperimentAgentState(
                        question=state.question,
                        experiment_id=state.experiment_id,
                        metric=recommended[0]["metric"] if recommended else "conversion",
                        metric_type=recommended[0]["metric_type"] if recommended else "proportion",
                        start_date=state.start_date,
                        end_date=state.end_date,
                    )
        
        # Use LLM to determine metric from question
        prompt = f"""
        Determine the primary metric to analyze based on the question.
        
        Question: {state.question}
        
        Common metrics:
        - conversion (proportion)
        - activation (proportion) 
        - retention (proportion)
        - revenue (mean)
        - arpu (ratio)
        - engagement (mean)
        
        Return JSON: {{"metric": "...", "metric_type": "proportion|mean|ratio"}}
        """
        
        response = self.llm.invoke([HumanMessage(content=prompt)])
        
        try:
            import json
            metrics = json.loads(response.content)
            return ExperimentAgentState(
                question=state.question,
                experiment_id=state.experiment_id,
                metric=metrics.get("metric", "conversion"),
                metric_type=metrics.get("metric_type", "proportion"),
                start_date=state.start_date,
                end_date=state.end_date,
            )
        except:
            return state
    
    def _run_analysis_node(self, state: ExperimentAgentState) -> ExperimentAgentState:
        """Run statistical analysis on the experiment."""
        try:
            with get_sync_session() as session:
                if state.experiment_id:
                    result = analyze_experiment_simple(
                        session=session,
                        experiment_id=state.experiment_id,
                        metric=state.metric,
                        metric_type=state.metric_type,
                    )
                else:
                    # Search for relevant experiments
                    from db.schema.models import Experiment
                    experiments = session.query(Experiment).filter(
                        Experiment.status == "completed"
                    ).limit(5).all()
                    
                    if not experiments:
                        return ExperimentAgentState(
                            question=state.question,
                            experiment_id=state.experiment_id,
                            metric=state.metric,
                            metric_type=state.metric_type,
                            error="No completed experiments found",
                        )
                    
                    # Analyze first relevant experiment
                    result = analyze_experiment_simple(
                        session=session,
                        experiment_id=str(experiments[0].id),
                        metric=state.metric,
                        metric_type=state.metric_type,
                    )
                    state.experiment_id = str(experiments[0].id)
                
                return ExperimentAgentState(
                    question=state.question,
                    experiment_id=state.experiment_id,
                    metric=state.metric,
                    metric_type=state.metric_type,
                    start_date=state.start_date,
                    end_date=state.end_date,
                    analysis_result=result,
                )
        except Exception as e:
            return ExperimentAgentState(
                question=state.question,
                experiment_id=state.experiment_id,
                metric=state.metric,
                metric_type=state.metric_type,
                error=f"Analysis failed: {str(e)}",
            )
    
    def _interpret_results_node(self, state: ExperimentAgentState) -> ExperimentAgentState:
        """Interpret statistical results."""
        result = state.analysis_result
        
        if not result or "error" in result:
            return state
        
        prompt = f"""
        Interpret the following experiment analysis results.
        
        Experiment: {result.get('experiment_name', 'Unknown')}
        Metric: {result.get('metric', 'Unknown')} ({result.get('metric_type', 'Unknown')})
        
        Control: {result.get('control', {})}
        Treatment: {result.get('treatment', {})}
        
        Effect Size: {result.get('effect_size', 'N/A')}
        Effect Size CI: {result.get('effect_size_ci', 'N/A')}
        P-value: {result.get('p_value', 'N/A')}
        Statistically Significant: {result.get('statistically_significant', False)}
        Test Used: {result.get('test_used', 'N/A')}
        Assumptions Met: {result.get('assumptions_met', 'N/A')}
        Warnings: {result.get('warnings', [])}
        Achieved Power: {result.get('achieved_power', 'N/A')}
        
        Provide:
        1. Plain English interpretation
        2. Business significance
        3. Caveats and limitations
        4. Recommendation (launch, iterate, or stop)
        
        Return as structured text.
        """
        
        response = self.llm.invoke([HumanMessage(content=prompt)])
        
        return ExperimentAgentState(
            question=state.question,
            experiment_id=state.experiment_id,
            metric=state.metric,
            metric_type=state.metric_type,
            start_date=state.start_date,
            end_date=state.end_date,
            analysis_result=state.analysis_result,
            evidence=state.evidence,
        )
    
    def _synthesize_evidence_node(self, state: ExperimentAgentState) -> ExperimentAgentState:
        """Synthesize analysis into evidence for investigation."""
        result = state.analysis_result
        
        if not result or "error" in result:
            return ExperimentAgentState(
                question=state.question,
                experiment_id=state.experiment_id,
                metric=state.metric,
                metric_type=state.metric_type,
                error=result.get("error") if result else "No analysis result",
                done=True,
            )
        
        # Create evidence entries
        evidence = []
        
        # Fact: statistical result
        evidence.append({
            "type": "fact",
            "source": "experiment",
            "content": f"Experiment '{result.get('experiment_name', 'Unknown')}' {result.get('metric', 'metric')} test: {result.get('test_used', 'test')}, p={result.get('p_value', 0):.4f}, effect size={result.get('effect_size', 0):.3f}",
            "confidence": 1 - result.get("p_value", 0.5),
            "citation": f"experiment_{state.experiment_id}_{state.metric}",
            "metadata": {
                "experiment_id": str(state.experiment_id),
                "metric": state.metric,
                "metric_type": state.metric_type,
                "p_value": result.get("p_value"),
                "effect_size": result.get("effect_size"),
                "significant": result.get("statistically_significant"),
                "test_used": result.get("test_used"),
                "assumptions_met": result.get("assumptions_met"),
                "power": result.get("achieved_power"),
            },
        })
        
        # Inference: business interpretation
        if result.get("statistically_significant"):
            direction = "improvement" if result.get("effect_size", 0) > 0 else "decline"
            evidence.append({
                "type": "inference",
                "source": "experiment",
                "content": f"Experiment shows statistically significant {direction} in {state.metric} (p={result.get('p_value', 0):.4f}). Recommendation: {result.get('interpretation', 'N/A')}",
                "confidence": 0.85,
                "citation": f"experiment_{state.experiment_id}_interpretation",
                "metadata": {
                    "direction": direction,
                    "recommendation": "launch" if direction == "improvement" else "iterate",
                },
            })
        else:
            evidence.append({
                "type": "inference",
                "source": "experiment",
                "content": f"Experiment did not detect significant effect on {state.metric} (p={result.get('p_value', 0):.4f}). Power: {result.get('achieved_power', 0):.2f}",
                "confidence": 0.7,
                "citation": f"experiment_{state.experiment_id}_null",
                "metadata": {
                    "direction": "null",
                    "recommendation": "iterate",
                    "power": result.get("achieved_power"),
                },
            })
        
        # Add warnings as separate evidence
        for warning in result.get("warnings", []):
            evidence.append({
                "type": "hypothesis",
                "source": "experiment",
                "content": f"Analysis warning: {warning}",
                "confidence": 0.5,
                "citation": f"experiment_{state.experiment_id}_warning",
                "metadata": {"warning": warning},
            })
        
        return ExperimentAgentState(
            question=state.question,
            experiment_id=state.experiment_id,
            metric=state.metric,
            metric_type=state.metric_type,
            start_date=state.start_date,
            end_date=state.end_date,
            analysis_result=state.analysis_result,
            evidence=evidence,
            done=True,
        )
    
    def investigate(
        self,
        question: str,
        experiment_id: Optional[str] = None,
        metric: str = "conversion",
        metric_type: Literal["proportion", "mean", "ratio"] = "proportion",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Run experiment investigation."""
        initial_state = ExperimentAgentState(
            question=question,
            experiment_id=experiment_id,
            metric=metric,
            metric_type=metric_type,
            start_date=start_date,
            end_date=end_date,
        )
        
        result = self.graph.invoke(initial_state)
        
        return {
            "question": question,
            "experiment_id": str(result.get("experiment_id")) if result.get("experiment_id") else None,
            "metric": result.get("metric"),
            "metric_type": result.get("metric_type"),
            "analysis_result": result.get("analysis_result"),
            "evidence": result.get("evidence", []),
            "error": result.get("error"),
        }
    
    def analyze_experiment(
        self,
        experiment_id: str,
        metric: str = "conversion",
        metric_type: Literal["proportion", "mean", "ratio"] = "proportion",
    ) -> Dict[str, Any]:
        """Direct experiment analysis."""
        with get_sync_session() as session:
            return analyze_experiment_simple(session, experiment_id, metric, metric_type)


def run_experiment_investigation(
    question: str,
    experiment_id: Optional[str] = None,
    metric: str = "conversion",
    metric_type: Literal["proportion", "mean", "ratio"] = "proportion",
) -> Dict[str, Any]:
    """Run an experiment investigation."""
    agent = ExperimentAgent()
    return agent.investigate(question, experiment_id, metric, metric_type)


def analyze_experiment_direct(
    experiment_id: str,
    metric: str = "conversion",
    metric_type: Literal["proportion", "mean", "ratio"] = "proportion",
) -> Dict[str, Any]:
    """Direct experiment analysis."""
    with get_sync_session() as session:
        return analyze_experiment_simple(session, experiment_id, metric, metric_type)