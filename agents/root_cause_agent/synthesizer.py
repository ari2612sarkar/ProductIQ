"""
Root Cause Agent - Synthesizes evidence from all sources to identify probable root causes.
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import uuid

from agents.base import Evidence, EvidenceType, Hypothesis, RootCause as BaseRootCause


class EvidenceSource(str, Enum):
    SQL = "sql"
    FEEDBACK = "feedback"
    EXPERIMENT = "experiment"
    METRIC = "metric"


@dataclass
class RootCause:
    """A root cause hypothesis with supporting evidence."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    confidence: float = 0.0
    evidence_ids: List[str] = field(default_factory=list)
    
    # Structured evidence classification
    facts: List[str] = field(default_factory=list)        # Directly observed, verifiable
    inferences: List[str] = field(default_factory=list)   # Logical deductions from facts
    hypotheses: List[str] = field(default_factory=list)   # Unverified explanations
    
    # Evidence breakdown by source
    sql_evidence_count: int = 0
    feedback_evidence_count: int = 0
    experiment_evidence_count: int = 0
    metric_evidence_count: int = 0
    
    # Metadata
    affected_metrics: List[str] = field(default_factory=list)
    affected_segments: List[str] = field(default_factory=list)
    time_window: Optional[str] = None
    competing_hypotheses: List[str] = field(default_factory=list)
    ruling_out_reasoning: str = ""


class EvidenceClassifier:
    """Classifies evidence as FACT, INFERENCE, or HYPOTHESIS."""
    
    @staticmethod
    def classify(evidence: Evidence) -> EvidenceType:
        """Classify a single piece of evidence."""
        # Source-based classification
        if evidence.source == EvidenceSource.SQL:
            # SQL results are direct observations
            return EvidenceType.FACT
        elif evidence.source == EvidenceSource.EXPERIMENT:
            # Experiment results are statistical facts
            return EvidenceType.FACT
        elif evidence.source == EvidenceSource.METRIC:
            # Metric values are direct measurements
            return EvidenceType.FACT
        elif evidence.source == EvidenceSource.FEEDBACK:
            # Feedback can be fact (user said X) or inference (pattern suggests Y)
            content = evidence.content.lower()
            if any(kw in content for kw in ["user said", "user reported", "ticket states", "review says"]):
                return EvidenceType.FACT
            elif any(kw in content for kw in ["suggests", "indicates", "pattern shows", "cluster reveals"]):
                return EvidenceType.INFERENCE
            else:
                return EvidenceType.HYPOTHESIS
        return EvidenceType.INFERENCE


class HypothesisScorer:
    """Scores and ranks root cause hypotheses."""
    
    def __init__(self):
        self.source_weights = {
            EvidenceSource.SQL: 1.0,
            EvidenceSource.EXPERIMENT: 0.9,
            EvidenceSource.METRIC: 0.8,
            EvidenceSource.FEEDBACK: 0.7,
        }
        self.type_weights = {
            EvidenceType.FACT: 1.0,
            EvidenceType.INFERENCE: 0.7,
            EvidenceType.HYPOTHESIS: 0.4,
        }
    
    def score_hypothesis(self, hypothesis: RootCause, evidence_map: Dict[str, Evidence]) -> float:
        """Score a hypothesis based on its supporting evidence."""
        if not hypothesis.evidence_ids:
            return 0.0
        
        total_score = 0.0
        total_weight = 0.0
        
        for eid in hypothesis.evidence_ids:
            if eid not in evidence_map:
                continue
            
            ev = evidence_map[eid]
            source_weight = self.source_weights.get(ev.source, 0.5)
            type_weight = self.type_weights.get(ev.type, 0.5)
            confidence = ev.confidence
            
            weight = source_weight * type_weight
            total_score += weight * confidence
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        base_score = total_score / total_weight
        
        # Bonus for multiple evidence sources
        sources = set(evidence_map[eid].source for eid in hypothesis.evidence_ids if eid in evidence_map)
        source_bonus = min(len(sources) * 0.05, 0.15)
        
        # Penalty for competing hypotheses not ruled out
        penalty = len(hypothesis.competing_hypotheses) * 0.02
        
        final_score = min(1.0, base_score + source_bonus - penalty)
        return final_score


class EvidenceSynthesizer:
    """Synthesizes evidence from multiple sources."""
    
    def __init__(self):
        self.classifier = EvidenceClassifier()
        self.scorer = HypothesisScorer()
    
    def synthesize(
        self,
        evidence: List[Evidence],
        metrics: Dict[str, Any],
        anomaly: Optional[Dict[str, Any]] = None,
    ) -> List[RootCause]:
        """Synthesize evidence into root cause hypotheses."""
        
        # Build evidence map
        evidence_map = {e.id: e for e in evidence}
        
        # Classify all evidence
        for ev in evidence:
            ev.type = self.classifier.classify(ev)
        
        # Generate initial hypotheses from evidence patterns
        hypotheses = self._generate_hypotheses(evidence, metrics, anomaly)
        
        # Score each hypothesis
        for hyp in hypotheses:
            hyp.confidence = self.scorer.score_hypothesis(hyp, {e.id: e for e in evidence})
        
        # Sort by confidence
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        
        # Add competing hypotheses info
        for hyp in hypotheses:
            hyp.competing_hypotheses = [
                h.description for h in hypotheses 
                if h.id != hyp.id and h.confidence > 0.3
            ][:3]
        
        return hypotheses
    
    def _generate_hypotheses(
        self,
        evidence: List[Evidence],
        metrics: Dict[str, Any],
        anomaly: Optional[Dict[str, Any]],
    ) -> List[RootCause]:
        """Generate initial hypotheses from evidence patterns."""
        
        hypotheses = []
        
        # Group evidence by source
        by_source = defaultdict(list)
        for ev in evidence:
            by_source[ev.source].append(ev)
        
        # 1. Metric-driven hypotheses
        if anomaly:
            metric_name = anomaly.get("metric", "unknown")
            hypotheses.append(self._create_metric_hypothesis(anomaly, by_source))
        
        # 2. SQL-driven hypotheses
        sql_evidence = by_source.get("sql", [])
        if sql_evidence:
            hypotheses.extend(self._create_sql_hypotheses(sql_evidence, metrics))
        
        # 3. Experiment-driven hypotheses
        exp_evidence = by_source.get("experiment", [])
        if exp_evidence:
            hypotheses.extend(self._create_experiment_hypotheses(exp_evidence))
        
        # 4. Feedback-driven hypotheses
        fb_evidence = by_source.get("feedback", [])
        if fb_evidence:
            hypotheses.extend(self._create_feedback_hypotheses(fb_evidence))
        
        # Filter and deduplicate
        unique_hypotheses = []
        seen = set()
        for h in hypotheses:
            key = h.description.lower()[:100]
            if key not in seen:
                seen.add(key)
                unique_hypotheses.append(h)
        
        return unique_hypotheses
    
    def _create_metric_hypothesis(self, anomaly: Dict, by_source: Dict) -> BaseRootCause:
        """Create hypothesis from metric anomaly."""
        metric = anomaly.get("metric", "metric")
        change = anomaly.get("relative_change", 0)
        direction = "decline" if change < 0 else "increase"
        
        ev_ids = [e.id for e in by_source.get("metric", [])]
        ev_ids += [e.id for e in by_source.get("sql", [])[:3]]
        
        return BaseRootCause(
            description=f"{metric} {direction} ({change:.1%}) - likely due to changes in user behavior or product experience",
            confidence=0.5,
            evidence_ids=ev_ids,
            affected_metrics=[metric],
        )
    
    def _create_sql_hypotheses(self, sql_evidence: List, metrics: Dict) -> List[BaseRootCause]:
        """Create hypotheses from SQL evidence."""
        hypotheses = []
        
        # Group by theme
        themes = defaultdict(list)
        for ev in sql_evidence:
            content = ev.content.lower()
            if "segment" in content or "cohort" in content:
                themes["segmentation"].append(ev)
            elif "funnel" in content or "conversion" in content:
                themes["funnel"].append(ev)
            elif "retention" in content:
                themes["retention"].append(ev)
            elif "revenue" in content or "payment" in content:
                themes["revenue"].append(ev)
            else:
                themes["general"].append(ev)
        
        for theme, ev_list in themes.items():
            if not ev_list:
                continue
            
            ev_ids = [e.id for e in ev_list]
            desc = self._generate_description(theme, ev_list)
            
            hypotheses.append(BaseRootCause(
                description=desc,
                confidence=0.6,
                evidence_ids=ev_ids,
                sql_evidence_count=len(ev_list),
            ))
        
        return hypotheses
    
    def _create_experiment_hypotheses(self, exp_evidence: List) -> List[BaseRootCause]:
        """Create hypotheses from experiment evidence."""
        hypotheses = []
        
        for ev in exp_evidence:
            content = ev.content.lower()
            if "significant" in content and "improvement" in content:
                hypotheses.append(BaseRootCause(
                    description=f"Experiment {ev.citation} shows positive effect - consider launching",
                    confidence=0.85,
                    evidence_ids=[ev.id],
                    experiment_evidence_count=1,
                ))
            elif "significant" in content and "decline" in content:
                hypotheses.append(BaseRootCause(
                    description=f"Experiment {ev.citation} shows negative effect - consider rolling back",
                    confidence=0.85,
                    evidence_ids=[ev.id],
                    experiment_evidence_count=1,
                ))
            elif "not significant" in content or "no significant" in content:
                hypotheses.append(BaseRootCause(
                    description=f"Experiment {ev.citation} shows no significant effect - insufficient evidence for launch",
                    confidence=0.7,
                    evidence_ids=[ev.id],
                    experiment_evidence_count=1,
                ))
        
        return hypotheses
    
    def _create_feedback_hypotheses(self, fb_evidence: List) -> List[BaseRootCause]:
        """Create hypotheses from feedback evidence."""
        hypotheses = []
        
        # Group by theme
        themes = defaultdict(list)
        for ev in fb_evidence:
            content = ev.content.lower()
            if "crash" in content or "bug" in content:
                themes["stability"].append(ev)
            elif "slow" in content or "performance" in content:
                themes["performance"].append(ev)
            elif "ui" in content or "ux" in content or "confusing" in content:
                themes["usability"].append(ev)
            elif "feature" in content or "request" in content:
                themes["feature_request"].append(ev)
            elif "pricing" in content or "price" in content or "expensive" in content:
                themes["pricing"].append(ev)
            else:
                themes["general"].append(ev)
        
        for theme, ev_list in themes.items():
            if len(ev_list) < 2:  # Need at least 2 pieces of feedback
                continue
            
            ev_ids = [e.id for e in ev_list]
            desc = self._generate_description(theme, ev_list)
            
            hypotheses.append(BaseRootCause(
                description=desc,
                confidence=min(0.5 + len(ev_list) * 0.05, 0.8),
                evidence_ids=ev_ids,
                feedback_evidence_count=len(ev_list),
            ))
        
        return hypotheses
    
    def _generate_description(self, theme: str, evidence_list: List) -> str:
        """Generate human-readable description for a theme."""
        theme_descriptions = {
            "segmentation": "Issue concentrated in specific user segment",
            "funnel": "Drop-off in conversion funnel",
            "retention": "Retention decline in user cohorts",
            "revenue": "Revenue impact from user behavior changes",
            "stability": "Application stability issues (crashes, bugs)",
            "performance": "Performance degradation (slow load times)",
            "usability": "Usability issues (confusing UI, poor UX)",
            "feature_request": "Missing or requested features",
            "pricing": "Pricing or billing concerns",
            "general": "General user feedback pattern",
        }
        
        base = theme_descriptions.get(theme, f"Pattern in {theme}")
        count = len(evidence_list)
        return f"{base} (supported by {count} evidence pieces)"


class RootCauseAnalyzer:
    """Main entry point for root cause analysis."""
    
    def __init__(self):
        self.synthesizer = EvidenceSynthesizer()
    
    def analyze(
        self,
        evidence: List,
        metrics: Dict[str, Any] = None,
        anomaly: Optional[Dict] = None,
    ) -> List[BaseRootCause]:
        """Analyze evidence and return ranked root causes."""
        
        # Convert evidence if needed (handle dict format)
        processed_evidence = []
        for i, ev in enumerate(evidence):
            if isinstance(ev, dict):
                from agents.base import Evidence as BaseEvidence, EvidenceType
                processed_evidence.append(BaseEvidence(
                    id=ev.get("id", str(uuid.uuid4())),
                    type=ev.get("type", EvidenceType.FACT),
                    source=ev.get("source", "unknown"),
                    content=ev.get("content", ""),
                    confidence=ev.get("confidence", 0.5),
                    citation=ev.get("citation"),
                    metadata=ev.get("metadata", {}),
                ))
            else:
                processed_evidence.append(ev)
        
        return self.synthesizer.synthesize(processed_evidence, metrics or {}, anomaly)


def analyze_root_causes(
    evidence: List[Dict[str, Any]],
    metrics: Dict[str, Any] = None,
    anomaly: Optional[Dict] = None,
) -> List[Dict[str, Any]]:
    """Convenience function for root cause analysis."""
    analyzer = RootCauseAnalyzer()
    
    # Convert evidence to proper format
    from agents.base import Evidence as BaseEvidence, EvidenceType
    processed = []
    for ev in evidence:
        if isinstance(ev, dict):
            processed.append(BaseEvidence(
                id=ev.get("id", str(uuid.uuid4())),
                type=ev.get("type", EvidenceType.FACT),
                source=ev.get("source", "unknown"),
                content=ev.get("content", ""),
                confidence=ev.get("confidence", 0.5),
                citation=ev.get("citation"),
                metadata=ev.get("metadata", {}),
            ))
        else:
            processed.append(ev)
    
    causes = analyzer.analyze(processed, metrics or {})
    
    return [
        {
            "id": c.id,
            "description": c.description,
            "confidence": c.confidence,
            "evidence_ids": c.evidence_ids,
            "facts": c.facts,
            "inferences": c.inferences,
            "hypotheses": c.hypotheses,
            "evidence_breakdown": {
                "sql": c.sql_evidence_count,
                "feedback": c.feedback_evidence_count,
                "experiment": c.experiment_evidence_count,
                "metric": c.metric_evidence_count,
            },
            "competing_hypotheses": c.competing_hypotheses,
        }
        for c in causes
    ]