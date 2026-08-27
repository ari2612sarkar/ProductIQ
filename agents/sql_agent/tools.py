"""
SQL Agent Tools for LangChain integration.
"""
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from agents.sql_agent.agent import run_sql_investigation
from agents.sql_agent.executor import ExecutionResult, execute_sql
from agents.sql_agent.generator import SQLGenerationResult, generate_sql
from agents.sql_agent.schema import (
    get_column_stats,
    get_relevant_schema,
    get_table_info,
    get_table_sample,
)
from agents.sql_agent.validator import ValidationResult, validate_sql


class ValidateSQLInput(BaseModel):
    sql: str = Field(..., description="SQL query to validate")


@tool("validate_sql", args_schema=ValidateSQLInput, return_direct=False)
def validate_sql_tool(sql: str) -> dict[str, Any]:
    """Validate a SQL query for safety and correctness."""
    result: ValidationResult = validate_sql(sql)
    return {
        "is_valid": result.is_valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "tables_referenced": list(result.tables_referenced) if result.tables_referenced else [],
        "columns_referenced": list(result.columns_referenced) if result.columns_referenced else [],
        "complexity_score": result.complexity_score,
    }


class GenerateSQLInput(BaseModel):
    question: str = Field(..., description="Analytical question to answer with SQL")
    context: str = Field(default="", description="Additional context from previous steps")


@tool("generate_sql", args_schema=GenerateSQLInput, return_direct=False)
def generate_sql_tool(question: str, context: str = "") -> dict[str, Any]:
    """Generate SQL from a natural language question."""
    result: SQLGenerationResult = generate_sql(question, context)
    return {
        "sql": result.sql,
        "explanation": result.explanation,
        "tables_used": result.tables_used,
        "confidence": result.confidence,
    }


class ExecuteSQLInput(BaseModel):
    sql: str = Field(..., description="Validated SQL query to execute")
    validate: bool = Field(default=True, description="Whether to validate before execution")


@tool("execute_sql", args_schema=ExecuteSQLInput, return_direct=False)
def execute_sql_tool(sql: str, validate: bool = True) -> dict[str, Any]:
    """Execute a validated read-only SQL query."""
    result: ExecutionResult = execute_sql(sql, validate)
    return {
        "success": result.success,
        "columns": result.columns,
        "data": result.data,
        "row_count": result.row_count,
        "truncated": result.truncated,
        "execution_time_ms": result.execution_time_ms,
        "error": result.error,
    }


class GetSchemaInput(BaseModel):
    question: str = Field(..., description="Question to find relevant schema for")
    max_tables: int = Field(default=10, description="Maximum tables to return")


@tool("get_relevant_schema", args_schema=GetSchemaInput, return_direct=False)
def get_relevant_schema_tool(question: str, max_tables: int = 10) -> dict[str, Any]:
    """Get database schema relevant to a question."""
    return get_relevant_schema(question, max_tables)


class GetTableInfoInput(BaseModel):
    table_name: str = Field(..., description="Name of the table")
    schema: str = Field(default="public", description="Schema name")


@tool("get_table_info", args_schema=GetTableInfoInput, return_direct=False)
def get_table_info_tool(table_name: str, schema: str = "public") -> dict[str, Any]:
    """Get detailed information about a table."""
    table_info = get_table_info(table_name, schema)
    if not table_info:
        return {"error": f"Table {table_name} not found"}

    return {
        "name": table_info.name,
        "schema": table_info.schema,
        "row_count": table_info.row_count,
        "columns": [
            {
                "name": c.name,
                "type": c.type,
                "nullable": c.nullable,
                "default": c.default,
                "primary_key": c.primary_key,
                "foreign_key": c.foreign_key,
                "comment": c.comment,
            }
            for c in table_info.columns
        ],
        "indexes": table_info.indexes or [],
    }


class GetTableSampleInput(BaseModel):
    table_name: str = Field(..., description="Name of the table")
    schema: str = Field(default="public", description="Schema name")
    limit: int = Field(default=5, description="Number of rows to return")


@tool("get_table_sample", args_schema=GetTableSampleInput, return_direct=False)
def get_table_sample_tool(table_name: str, schema: str = "public", limit: int = 5) -> list[dict[str, Any]]:
    """Get sample rows from a table."""
    return get_table_sample(table_name, schema, limit)


class GetColumnStatsInput(BaseModel):
    table_name: str = Field(..., description="Name of the table")
    column_name: str = Field(..., description="Name of the column")
    schema: str = Field(default="public", description="Schema name")


@tool("get_column_stats", args_schema=GetColumnStatsInput, return_direct=False)
def get_column_stats_tool(table_name: str, column_name: str, schema: str = "public") -> dict[str, Any]:
    """Get statistics for a column."""
    return get_column_stats(table_name, column_name, schema)


class RunInvestigationInput(BaseModel):
    question: str = Field(..., description="Analytical question to investigate")


@tool("run_sql_investigation", args_schema=RunInvestigationInput, return_direct=False)
def run_sql_investigation_tool(question: str) -> dict[str, Any]:
    """Run a full multi-step SQL investigation."""
    return run_sql_investigation(question)


# Export all tools
SQL_AGENT_TOOLS = [
    validate_sql_tool,
    generate_sql_tool,
    execute_sql_tool,
    get_relevant_schema_tool,
    get_table_info_tool,
    get_table_sample_tool,
    get_column_stats_tool,
    run_sql_investigation_tool,
]


def get_sql_agent_tools() -> list:
    """Get all SQL agent tools."""
    return SQL_AGENT_TOOLS
