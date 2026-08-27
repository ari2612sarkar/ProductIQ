"""
SQL Executor for SQL Agent.
Executes validated read-only SQL queries with safety controls.
"""
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Result

from agents.sql_agent.validator import validate_sql
from config.settings import settings
from db.connection import get_readonly_session


@dataclass
class ExecutionResult:
    success: bool
    columns: list[str]
    data: list[dict[str, Any]]
    row_count: int
    truncated: bool
    execution_time_ms: int
    error: str | None = None
    query: str | None = None


class SQLExecutor:
    """Executes SQL queries with safety controls."""

    def __init__(self):
        self.timeout = settings.sql_query_timeout * 1000  # milliseconds
        self.max_rows = settings.sql_max_rows

    def execute(self, sql: str, validate: bool = True) -> ExecutionResult:
        """Execute a SQL query."""
        start_time = time.time()

        # Validate first
        if validate:
            validation = validate_sql(sql)
            if not validation.is_valid:
                return ExecutionResult(
                    success=False,
                    columns=[],
                    data=[],
                    row_count=0,
                    truncated=False,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error="; ".join(validation.errors),
                    query=sql,
                )

        # Execute with read-only session
        try:
            with get_readonly_session() as session:
                # Set statement timeout
                session.execute(text(f"SET LOCAL statement_timeout = {self.timeout}"))

                # Execute query
                result: Result = session.execute(text(sql))

                # Get columns
                columns = list(result.keys()) if result.keys() else []

                # Fetch rows with limit
                rows = result.fetchmany(self.max_rows + 1)  # +1 to detect truncation

                # Check if truncated
                truncated = len(rows) > self.max_rows
                if truncated:
                    rows = rows[:self.max_rows]

                # Convert to list of dicts
                data = [dict(zip(columns, row)) for row in rows]

                execution_time = int((time.time() - start_time) * 1000)

                return ExecutionResult(
                    success=True,
                    columns=columns,
                    data=data,
                    row_count=len(data),
                    truncated=truncated,
                    execution_time_ms=execution_time,
                    query=sql,
                )

        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            error_msg = str(e)

            # Sanitize error message
            if "statement_timeout" in error_msg.lower():
                error_msg = f"Query timeout ({settings.sql_query_timeout}s)"
            elif "permission denied" in error_msg.lower():
                error_msg = "Read-only violation"

            return ExecutionResult(
                success=False,
                columns=[],
                data=[],
                row_count=0,
                truncated=False,
                execution_time_ms=execution_time,
                error=error_msg,
                query=sql,
            )

    def execute_batch(self, queries: list[str]) -> list[ExecutionResult]:
        """Execute multiple queries."""
        return [self.execute(q) for q in queries]

    def explain(self, sql: str) -> ExecutionResult:
        """Run EXPLAIN on a query."""
        explain_sql = f"EXPLAIN (FORMAT JSON, ANALYZE FALSE) {sql}"
        return self.execute(explain_sql, validate=False)

    def get_table_stats(self, table_name: str) -> dict[str, Any]:
        """Get table statistics."""
        with get_readonly_session() as session:
            result = session.execute(text("""
                SELECT 
                    reltuples::bigint as row_estimate,
                    relpages,
                    pg_size_pretty(pg_total_relation_size(:table)) as total_size,
                    pg_size_pretty(pg_relation_size(:table)) as table_size
                FROM pg_class 
                WHERE relname = :table
            """), {"table": table_name})
            row = result.first()
            return dict(row._mapping) if row else {}


def execute_sql(sql: str) -> ExecutionResult:
    """Convenience function for SQL execution."""
    executor = SQLExecutor()
    return executor.execute(sql)
