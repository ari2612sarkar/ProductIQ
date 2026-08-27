"""
Base agent classes and shared state definitions.
"""
from typing import Dict, List, Any, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
import uuid


class EvidenceType(str, Enum):
    FACT = "fact"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"


class InvestigationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TriggerType(str, Enum):
    MANUAL = "manual"
    ANOMALY = "anomaly"
    SCHEDULED = "scheduled"


@dataclass
class MetricValue:
    name: str
    value: float
    period_start: datetime
    period_end: datetime
    sample_size: Optional[int] = None
    dimensions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Anomaly:
    id: uuid.UUID
    metric_name: str
    baseline_value: float
    current_value: float
    absolute_change: float
    relative_change: float
    detection_method: str
    severity: str
    confidence: Optional[float] = None
    detected_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Hypothesis:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    description: str = ""
    confidence: float = 0.0
    evidence_ids: List[uuid.UUID] = field(default_factory=list)
    status: Literal["active", "ruled_out", "confirmed"] = "active"


@dataclass
class SQLQuery:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    step_number: int = 0
    question: str = ""
    sql: str = ""
    explanation: str = ""
    tables_used: List[str] = field(default_factory=list)
    confidence: float = 0.0
    validation: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SQLResult:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    query_id: uuid.UUID = field(default_factory=uuid.uuid4)
    success: bool = False
    columns: List[str] = field(default_factory=list)
    data: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    execution_time_ms: int = 0
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Evidence:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    type: EvidenceType = EvidenceType.FACT
    source: Literal["sql", "feedback", "experiment", "metric"] = "sql"
    content: str = ""
    confidence: float = 0.0
    citation: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FeedbackEvidence:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    source: str = ""
    text: str = ""
    sentiment: str = ""
    product_area: str = ""
    rating: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    cluster_id: Optional[uuid.UUID] = None


@dataclass
class FeedbackCluster:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    theme: str = ""
    evidence_ids: List[uuid.UUID] = field(default_factory=list)
    count: int = 0
    representative_quotes: List[str] = field(default_factory=list)
    sentiment: str = ""


@dataclass
class ExperimentResult:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    experiment_id: uuid.UUID = field(default_factory=uuid.uuid4)
    metric: str = ""
    control_mean: float = 0.0
    treatment_mean: float = 0.0
    effect_size: float = 0.0
    confidence_interval: List[float] = field(default_factory=list)
    p_value: float = 1.0
    statistically_significant: bool = False
    interpretation: str = ""


@dataclass
class RootCause:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    description: str = ""
    confidence: float = 0.0
    evidence_ids: List[uuid.UUID] = field(default_factory=list)
    facts: List[str] = field(default_factory=list)
    inferences: List[str] = field(default_factory=list)
    hypotheses: List[str] = field(default_factory=list)


@dataclass
class Recommendation:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    title: str = ""
    description: str = ""
    priority: str = ""
    rice_score: Optional[float] = None
    reach: Optional[int] = None
    impact: Optional[float] = None
    confidence: Optional[float] = None
    effort: Optional[int] = None
    revenue_impact: Optional[float] = None
    strategic_alignment: Optional[int] = None
    risk: Optional[int] = None
    evidence_summary: str = ""


@dataclass
class InvestigationError:
    step: str = ""
    error: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    recoverable: bool = True


@dataclass
class ExecutionStep:
    agent: str = ""
    action: str = ""
    input: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    success: bool = True
    error: Optional[str] = None


@dataclass
class InvestigationState:
    investigation_id: uuid.UUID = field(default_factory=uuid.uuid4)
    question: str = ""
    trigger: TriggerType = TriggerType.MANUAL
    status: InvestigationStatus = InvestigationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Metrics & Anomaly
    metrics: Dict[str, MetricValue] = field(default_factory=dict)
    anomaly: Optional[Anomaly] = None
    
    # Hypotheses
    hypotheses: List[Hypothesis] = field(default_factory=list)
    
    # SQL Investigation
    sql_queries: List[SQLQuery] = field(default_factory=list)
    sql_results: List[SQLResult] = field(default_factory=list)
    
    # Feedback Evidence
    feedback_evidence: List[FeedbackEvidence] = field(default_factory=list)
    feedback_clusters: List[FeedbackCluster] = field(default_factory=list)
    
    # Experiment Results
    experiment_results: List[ExperimentResult] = field(default_factory=list)
    
    # Root Cause
    root_causes: List[RootCause] = field(default_factory=list)
    
    # Recommendations
    recommendations: List[Recommendation] = field(default_factory=list)
    
    # Meta
    confidence: float = 0.0
    evidence: List[Evidence] = field(default_factory=list)
    errors: List[InvestigationError] = field(default_factory=list)
    execution_trace: List[ExecutionStep] = field(default_factory=list)