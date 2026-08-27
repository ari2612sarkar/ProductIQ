"""
Investigation State - Strongly typed state for the orchestration workflow.
"""
from typing import Dict, List, Any, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid

from agents.base import (
    InvestigationState as BaseInvestigationState,
    Evidence,
    EvidenceType,
    Hypothesis,
    RootCause,
    Recommendation,
    InvestigationStatus,
    TriggerType,
    Anomaly,
    MetricValue,
    SQLQuery,
    SQLResult,
    FeedbackEvidence,
    FeedbackCluster,
    ExperimentResult,
    InvestigationError,
    ExecutionStep,
)


class InvestigationStep(str, Enum):
    """Steps in the investigation workflow."""
    INIT = "init"
    METRICS_ANALYSIS = "metrics_analysis"
    ANOMALY_DETECTION = "anomaly_detection"
    SQL_INVESTIGATION = "sql_investigation"
    FEEDBACK_ANALYSIS = "feedback_analysis"
    EXPERIMENT_ANALYSIS = "experiment_analysis"
    EVIDENCE_AGGREGATION = "evidence_aggregation"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"
    DECISION_MAKING = "decision_making"
    FINALIZATION = "finalization"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class InvestigationState(BaseInvestigationState):
    """Extended investigation state for orchestrator."""
    
    # Workflow control
    current_step: InvestigationStep = InvestigationStep.INIT
    completed_steps: List[InvestigationStep] = field(default_factory=list)
    pending_steps: List[InvestigationStep] = field(default_factory=list)
    max_iterations: int = 10
    iteration: int = 0
    
    # Step-specific data
    metrics_analysis: Dict[str, Any] = field(default_factory=dict)
    anomaly_detection: Dict[str, Any] = field(default_factory=dict)
    sql_investigation: Dict[str, Any] = field(default_factory=dict)
    feedback_analysis: Dict[str, Any] = field(default_factory=dict)
    experiment_analysis: Dict[str, Any] = field(default_factory=dict)
    
    # Agent outputs
    sql_agent_output: Dict[str, Any] = field(default_factory=dict)
    feedback_agent_output: Dict[str, Any] = field(default_factory=dict)
    experiment_agent_output: Dict[str, Any] = field(default_factory=dict)
    root_cause_agent_output: Dict[str, Any] = field(default_factory=dict)
    decision_agent_output: Dict[str, Any] = field(default_factory=dict)
    
    # Control flags
    requires_sql: bool = True
    requires_feedback: bool = True
    requires_experiment: bool = True
    skip_feedback: bool = False
    skip_experiment: bool = False
    
    # Error handling
    step_errors: Dict[str, List[str]] = field(default_factory=dict)
    retry_count: Dict[str, int] = field(default_factory=dict)
    max_retries: int = 3
    
    def add_step(self, step: InvestigationStep):
        """Mark a step as completed."""
        if step not in self.completed_steps:
            self.completed_steps.append(step)
        self.current_step = step
    
    def is_step_completed(self, step: InvestigationStep) -> bool:
        return step in self.completed_steps
    
    def get_next_step(self) -> Optional[InvestigationStep]:
        """Get the next required step."""
        required_steps = [
            InvestigationStep.METRICS_ANALYSIS,
            InvestigationStep.ANOMALY_DETECTION,
        ]
        
        if self.requires_sql:
            required_steps.append(InvestigationStep.SQL_INVESTIGATION)
        if self.requires_feedback and not self.skip_feedback:
            required_steps.append(InvestigationStep.FEEDBACK_ANALYSIS)
        if self.requires_experiment and not self.skip_experiment:
            required_steps.append(InvestigationStep.EXPERIMENT_ANALYSIS)
        
        required_steps.extend([
            InvestigationStep.EVIDENCE_AGGREGATION,
            InvestigationStep.ROOT_CAUSE_ANALYSIS,
            InvestigationStep.DECISION_MAKING,
            InvestigationStep.FINALIZATION,
        ])
        
        for step in required_steps:
            if not self.is_step_completed(step):
                return step
        
        return InvestigationStep.COMPLETE
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize state for checkpointing."""
        return {
            "investigation_id": str(self.investigation_id),
            "question": self.question,
            "trigger": self.trigger,
            "status": self.status,
            "current_step": self.current_step.value,
            "completed_steps": [s.value for s in self.completed_steps],
            "iteration": self.iteration,
            "metrics": {k: v.__dict__ if hasattr(v, '__dict__') else v for k, v in self.metrics.items()},
            "anomaly": self.anomaly.__dict__ if self.anomaly else None,
            "hypotheses": [h.__dict__ for h in self.hypotheses],
            "sql_queries": [q.__dict__ for q in self.sql_queries],
            "sql_results": [r.__dict__ for r in self.sql_results],
            "feedback_evidence": [e.__dict__ for e in self.feedback_evidence],
            "feedback_clusters": [c.__dict__ for c in self.feedback_clusters],
            "experiment_results": [r.__dict__ for r in self.experiment_results],
            "root_causes": [r.__dict__ for r in self.root_causes],
            "recommendations": [r.__dict__ for r in self.recommendations],
            "confidence": self.confidence,
            "evidence": [e.__dict__ for e in self.evidence],
            "errors": [e.__dict__ for e in self.errors],
            "execution_trace": [t.__dict__ for t in self.execution_trace],
        }


def create_initial_state(
    question: str,
    trigger: TriggerType = TriggerType.MANUAL,
    anomaly: Optional[Anomaly] = None,
    metrics: Optional[Dict[str, MetricValue]] = None,
) -> BaseInvestigationState:
    """Create initial investigation state."""
    return BaseInvestigationState(
        investigation_id=uuid.uuid4(),
        question=question,
        trigger=trigger,
        status=InvestigationStatus.PENDING,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        metrics=metrics or {},
        anomaly=anomaly,
    )