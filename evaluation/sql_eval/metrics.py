"""
SQL Evaluation Metrics
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class SQLErrorType(Enum):
    SYNTAX_ERROR = "syntax_error"
    SEMANTIC_ERROR = "semantic_error"
    SCHEMA_VIOLATION = "schema_violation"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    RESOURCE_LIMIT = "resource_limit"


@dataclass
class SQLEvalResult:
    question: str
    expected_sql: str
    generated_sql: str
    execution_success: bool
    result_matches: bool
    schema_grounded: bool
    read_only_safe: bool
    error_type: Optional[SQLErrorType] = None
    error_message: str = ""
    execution_time_ms: int = 0
    rows_returned: int = 0


def evaluate_sql(
    question: str,
    expected_sql: str,
    generated_sql: str,
    execution_success: bool,
    actual_result: List[Dict],
    expected_result: List[Dict],
    tables_used: List[str],
    allowed_tables: List[str],
    forbidden_keywords: List[str],
    execution_time_ms: int,
    error_message: str = "",
) -> SQLEvalResult:
    """Evaluate a single SQL query against ground truth."""

    # Check execution success
    if not execution_success:
        return SQLEvalResult(
            question=question,
            expected_sql=expected_sql,
            generated_sql=generated_sql,
            execution_success=False,
            result_matches=False,
            schema_grounded=False,
            read_only_safe=False,
            error_type=_classify_error(error_message),
            error_message=error_message,
            execution_time_ms=0,
        )

    # Check result correctness
    result_matches = _compare_results(actual_result, expected_result)

    # Check schema grounding
    schema_grounded = _check_schema_grounding(tables_used, allowed_tables)

    # Check read-only safety
    read_only_safe = _check_read_only_safety(generated_sql, forbidden_keywords)

    return SQLEvalResult(
        question=question,
        expected_sql=expected_sql,
        generated_sql=generated_sql,
        execution_success=True,
        result_matches=result_matches,
        schema_grounded=schema_grounded,
        read_only_safe=read_only_safe,
        execution_time_ms=execution_time_ms,
        rows_returned=len(actual_result),
    )


def _classify_error(error_message: str) -> SQLErrorType:
    error_lower = error_message.lower()
    if "syntax" in error_lower or "parse" in error_lower:
        return SQLErrorType.SYNTAX_ERROR
    elif "permission" in error_lower or "denied" in error_lower:
        return SQLErrorType.PERMISSION_DENIED
    elif "timeout" in error_lower:
        return SQLErrorType.TIMEOUT
    elif "resource" in error_lower or "limit" in error_lower:
        return SQLErrorType.RESOURCE_LIMIT
    else:
        return SQLErrorType.SEMANTIC_ERROR


def _compare_results(actual: List[Dict], expected: List[Dict]) -> bool:
    """Compare two result sets (order-independent)."""
    if len(actual) != len(expected):
        return False

    # Normalize: sort by all keys
    def normalize(row: Dict) -> tuple:
        return tuple(sorted(row.items()))

    actual_norm = sorted([normalize(r) for r in actual])
    expected_norm = sorted([normalize(r) for r in expected])

    return actual_norm == expected_norm


def _check_schema_grounding(tables_used: List[str], allowed_tables: List[str]) -> bool:
    """Check if all tables used are in allowed list."""
    return all(table in allowed_tables for table in tables_used)


def _check_read_only_safety(sql: str, forbidden_keywords: List[str]) -> bool:
    """Check if SQL contains forbidden operations."""
    sql_upper = sql.upper()
    for keyword in forbidden_keywords:
        if keyword in sql_upper:
            return False
    return True


def compute_metrics(results: List[SQLEvalResult]) -> Dict[str, float]:
    """Compute aggregate metrics from evaluation results."""
    total = len(results)
    if total == 0:
        return {}

    execution_success = sum(1 for r in results if r.execution_success) / total
    result_correctness = sum(1 for r in results if r.result_matches) / total
    schema_grounding = sum(1 for r in results if r.schema_grounded) / total
    read_only_safety = sum(1 for r in results if r.read_only_safe) / total

    avg_execution_time = sum(r.execution_time_ms for r in results) / total
    avg_rows = sum(r.rows_returned for r in results) / total

    error_types = {}
    for r in results:
        if r.error_type:
            error_types[r.error_type.value] = error_types.get(r.error_type.value, 0) + 1

    return {
        "execution_success_rate": execution_success,
        "result_correctness_rate": result_correctness,
        "schema_grounding_rate": schema_grounding,
        "read_only_safety_rate": read_only_safety,
        "avg_execution_time_ms": avg_execution_time,
        "avg_rows_returned": avg_rows,
        "error_distribution": error_types,
        "total_evaluated": total,
    }