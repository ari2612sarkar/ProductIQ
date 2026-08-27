"""
SQL Generation for SQL Agent.
Generates PostgreSQL queries from natural language questions using LLM.
"""
import json
from dataclasses import dataclass
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from agents.sql_agent.schema import get_relevant_schema
from config.settings import settings


@dataclass
class SQLGenerationResult:
    sql: str
    explanation: str
    tables_used: list[str]
    confidence: float


class SQLGenerator:
    """Generates SQL from natural language questions."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.openai_api_key,
        )
        self._setup_prompt()

    def _setup_prompt(self):
        """Set up the SQL generation prompt."""
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_system_prompt()),
            ("human", self._get_user_prompt()),
        ])

    def _get_system_prompt(self) -> str:
        return """You are an expert PostgreSQL analyst. Generate SQL queries to answer analytical questions about product data.

DATABASE SCHEMA:
{schema}

RULES:
1. ONLY generate SELECT queries - no INSERT, UPDATE, DELETE, DDL
2. Use proper PostgreSQL syntax
3. Always use explicit column names (no SELECT *)
4. Use CTEs for complex queries
5. Add LIMIT {max_rows} to all queries
6. Use proper type casting
7. Handle NULLs appropriately
8. Use indexes where possible (check schema for indexed columns)
9. For time-series: use DATE_TRUNC, GENERATE_SERIES for gaps
10. For cohorts: use DATE_TRUNC on user signup date
11. For funnels: use conditional aggregation
12. For retention: use self-joins or window functions

COMMON PATTERNS:
- DAU: COUNT(DISTINCT user_id) FROM events WHERE DATE(timestamp) = ...
- Retention: Cohort signup date + activity date, self-join events
- Funnel: SUM(CASE WHEN event_name = 'step1' THEN 1 END) as step1, ...
- Segmentation: GROUP BY plan, channel, country, etc.
- Percentiles: percentile_cont(0.5) WITHIN GROUP (ORDER BY ...)

Return JSON with:
{{
  "sql": "the query",
  "explanation": "step-by-step explanation",
  "tables_used": ["table1", "table2"],
  "confidence": 0.0-1.0
}}"""

    def _get_user_prompt(self) -> str:
        return """QUESTION: {question}

CONTEXT: {context}

Generate the SQL query to answer this question."""

    def generate(self, question: str, context: str = "") -> SQLGenerationResult:
        """Generate SQL from a question."""
        # Get relevant schema
        schema_info = get_relevant_schema(question)
        schema_json = json.dumps({
            name: {
                "row_count_estimate": t.row_count,
                "columns": [
                    {"name": c.name, "type": c.type, "nullable": c.nullable, "primary_key": c.primary_key, "foreign_key": c.foreign_key}
                    for c in t.columns
                ],
                "indexes": t.indexes or [],
            }
            for name, t in schema_info.items()
        }, indent=2)

        # Add context from previous queries if provided
        full_context = f"{context}\n\nRelevant Schema:\n{schema_json}" if context else schema_json

        # Generate
        response = self.llm.invoke(self.prompt.format_messages(
            schema=schema_json,
            question=question,
            context=full_context,
            max_rows=settings.sql_max_rows,
        ))

        # Parse response
        try:
            result = json.loads(response.content)
            return SQLGenerationResult(
                sql=result.get("sql", ""),
                explanation=result.get("explanation", ""),
                tables_used=result.get("tables_used", []),
                confidence=result.get("confidence", 0.5),
            )
        except json.JSONDecodeError:
            # Fallback: extract SQL from markdown
            content = response.content
            sql = self._extract_sql(content)
            return SQLGenerationResult(
                sql=sql,
                explanation=content,
                tables_used=[],
                confidence=0.3,
            )

    def _extract_sql(self, text: str) -> str:
        """Extract SQL from markdown code blocks."""
        import re
        # Try ```sql ... ``` blocks
        matches = re.findall(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if matches:
            return matches[0].strip()
        # Try ``` ... ``` blocks
        matches = re.findall(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if matches:
            return matches[0].strip()
        # Return as-is
        return text.strip()


def generate_sql(question: str, context: str = "") -> SQLGenerationResult:
    """Convenience function for SQL generation."""
    generator = SQLGenerator()
    return generator.generate(question, context)


# Multi-step investigation helpers
class MultiStepSQLGenerator:
    """Handles multi-step SQL investigations."""

    def __init__(self):
        self.generator = SQLGenerator()
        self.history: list[dict[str, Any]] = []

    def investigate(self, question: str, max_steps: int = 5) -> list[dict[str, Any]]:
        """Run multi-step investigation."""
        self.history = []
        current_question = question
        context = ""

        for step in range(max_steps):
            result = self.generator.generate(current_question, context)

            if not result.sql or result.confidence < 0.3:
                break

            step_result = {
                "step": step + 1,
                "question": current_question,
                "sql": result.sql,
                "explanation": result.explanation,
                "tables_used": result.tables_used,
                "confidence": result.confidence,
            }
            self.history.append(step_result)

            # Generate next question based on results (simplified)
            # In production, this would analyze actual query results
            context += f"\nStep {step + 1}: {result.explanation}"

            # For now, stop after first step
            # Real implementation would analyze results and decide next step
            break

        return self.history
