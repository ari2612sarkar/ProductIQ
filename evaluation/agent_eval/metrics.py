"""
Agent Evaluation Metrics
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from collections import Counter


class AgentTaskType(Enum):
    SQL_INVESTIGATION = "sql_investigation"
    FEEDBACK_ANALYSIS = "feedback_analysis"
    EXPERIMENT_ANALYSIS = "experiment_analysis"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"
    DECISION_MAKING = "decision_making"
    FULL_INVESTIGATION = "full_investigation"


@dataclass
class AgentEvalResult:
    task_type: AgentTaskType
    question: str
    success: bool
    steps_completed: int
    total_steps: int
    tools_used: List[str]
    tools_expected: List[str]
    root_cause_correct: Optional[bool] = None
    recommendation_quality: Optional[float] = None
    hallucination_detected: bool = False
    error_message: str = ""
    execution_time_ms: int = 0


def evaluate_agent(
    task_type: AgentTaskType,
    question: str,
    expected_tools: List[str],
    actual_tools: List[str],
    success: bool,
    steps_completed: int,
    total_steps: int,
    root_cause_correct: Optional[bool] = None,
    recommendation_quality: Optional[float] = None,
    hallucination_detected: bool = False,
    error_message: str = "",
    execution_time_ms: int = 0,
) -> AgentEvalResult:
    """Evaluate a single agent task."""

    # Tool selection accuracy
    tools_used = set(actual_tools)
    tools_expected = set(expected_tools)

    return AgentEvalResult(
        task_type=task_type,
        question=question,
        success=success,
        steps_completed=steps_completed,
        total_steps=total_steps,
        tools_used=actual_tools,
        tools_expected=expected_tools,
        root_cause_correct=root_cause_correct,
        recommendation_quality=recommendation_quality,
        hallucination_detected=hallucination_detected,
        error_message=error_message,
        execution_time_ms=execution_time_ms,
    )


def compute_tool_selection_accuracy(results: List[AgentEvalResult]) -> Dict[str, float]:
    """Compute tool selection metrics."""
    total = len(results)
    if total == 0:
        return {}

    tool_precision = 0.0
    tool_recall = 0.0

    for r in results:
        used = set(r.tools_used)
        expected = set(r.tools_expected)

        if used:
            tool_precision += len(used & expected) / len(used)
        if expected:
            tool_recall += len(used & expected) / len(expected)

    return {
        "tool_precision": tool_precision / total,
        "tool_recall": tool_recall / total,
        "tool_f1": (
            2 * (tool_precision / total) * (tool_recall / total)
            / ((tool_precision + tool_recall) / total)
            if (tool_precision + tool_recall) > 0
            else 0.0
        ),
    }


def compute_task_completion_rate(results: List[AgentEvalResult]) -> float:
    """Compute task completion rate."""
    if not results:
        return 0.0
    return sum(1 for r in results if r.success) / len(results)


def compute_root_cause_accuracy(results: List[AgentEvalResult]) -> Optional[float]:
    """Compute root cause identification accuracy."""
    relevant = [r for r in results if r.root_cause_correct is not None]
    if not relevant:
        return None
    return sum(1 for r in relevant if r.root_cause_correct) / len(relevant)


def compute_recommendation_quality(results: List[AgentEvalResult]) -> Optional[float]:
    """Compute average recommendation quality."""
    relevant = [r for r in results if r.recommendation_quality is not None]
    if not relevant:
        return None
    return sum(r.recommendation_quality for r in relevant) / len(relevant)


def compute_hallucination_rate(results: List[AgentEvalResult]) -> float:
    """Compute hallucination rate."""
    if not results:
        return 0.0
    return sum(1 for r in results if r.hallucination_detected) / len(results)


def compute_agent_metrics(results: List[AgentEvalResult]) -> Dict[str, Any]:
    """Compute aggregate agent evaluation metrics."""
    if not results:
        return {}

    return {
        "task_completion_rate": compute_task_completion_rate(results),
        "tool_selection": compute_tool_selection_accuracy(results),
        "root_cause_accuracy": compute_root_cause_accuracy(results),
        "recommendation_quality": compute_recommendation_quality(results),
        "hallucination_rate": compute_hallucination_rate(results),
        "avg_execution_time_ms": sum(r.execution_time_ms for r in results) / len(results),
        "avg_steps_completed": sum(r.steps_completed for r in results) / len(results),
        "total_evaluated": len(results),
    }