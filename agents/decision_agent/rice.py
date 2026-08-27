"""
RICE Scoring Framework for Product Prioritization.
Reach × Impact × Confidence / Effort
"""
from typing import Dict, List, Any, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid


class PriorityLevel(str, Enum):
    P0 = "P0"  # Critical - do immediately
    P1 = "P1"  # High - do this sprint
    P2 = "P2"  # Medium - do next sprint
    P3 = "P3"  # Low - backlog
    ICEBOX = "ICEBOX"  # Not planned


@dataclass
class RICEScore:
    """RICE scoring components."""
    reach: int                    # Users affected per period
    impact: float                 # 0.25 (minimal) to 3 (massive)
    confidence: float             # 0.0 to 1.0
    effort: int                   # Person-weeks
    
    # Extended factors
    revenue_impact: Optional[float] = None      # Estimated $ impact
    strategic_alignment: Optional[int] = None   # 1-5 scale
    risk: Optional[int] = None                  # 1-5 scale (1=low, 5=high)
    
    @property
    def rice_score(self) -> float:
        """Calculate RICE score: (Reach × Impact × Confidence) / Effort"""
        if self.effort <= 0:
            return 0.0
        return (self.reach * self.impact * self.confidence) / self.effort
    
    @property
    def extended_score(self) -> float:
        """Extended score with revenue and strategic factors."""
        base = self.rice_score
        
        # Revenue factor (normalized to $1M baseline)
        revenue_factor = 1.0
        if self.revenue_impact:
            revenue_factor = 1.0 + min(self.revenue_impact / 1_000_000, 0.5)
        
        # Strategic alignment factor
        strategic_factor = 1.0
        if self.strategic_alignment:
            strategic_factor = 1.0 + (self.strategic_alignment - 3) * 0.1
        
        # Risk penalty
        risk_factor = 1.0
        if self.risk:
            risk_factor = 1.0 - (self.risk - 1) * 0.1
        
        return base * revenue_factor * strategic_factor * risk_factor


@dataclass
class Recommendation:
    """Product recommendation with RICE scoring."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    
    # RICE components
    rice: RICEScore = field(default_factory=RICEScore)
    
    # Derived
    rice_score: float = 0.0
    extended_score: float = 0.0
    priority: PriorityLevel = PriorityLevel.P3
    
    # Evidence
    evidence_summary: str = ""
    root_cause_ids: List[str] = field(default_factory=list)
    supporting_evidence: List[str] = field(default_factory=list)
    
    # Metadata
    status: Literal["proposed", "approved", "in_progress", "done", "rejected"] = "proposed"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        self.rice_score = self.rice.rice_score
        self.extended_score = self.rice.extended_score
        self.priority = self._calculate_priority()
    
    def _calculate_priority(self) -> PriorityLevel:
        """Calculate priority level from extended score."""
        score = self.extended_score
        if score >= 1000:
            return PriorityLevel.P0
        elif score >= 300:
            return PriorityLevel.P1
        elif score >= 100:
            return PriorityLevel.P2
        elif score >= 30:
            return PriorityLevel.P3
        else:
            return PriorityLevel.ICEBOX


class RICEEstimator:
    """Estimates RICE components from root causes and evidence."""
    
    def __init__(self):
        # Default impact values by problem type
        self.impact_defaults = {
            "stability": 2.0,      # Crashes/bugs - high impact
            "performance": 1.5,    # Speed issues - medium-high
            "usability": 1.0,      # UX issues - medium
            "feature_request": 0.75, # New features - medium-low
            "pricing": 1.25,       # Pricing - medium-high
            "conversion": 2.0,     # Conversion drops - high
            "retention": 2.5,      # Retention drops - very high
            "revenue": 3.0,        # Direct revenue impact - massive
        }
    
    def estimate_reach(self, root_cause: Dict, metrics: Dict) -> int:
        """Estimate number of users affected."""
        # Use affected segments from root cause
        affected_segments = root_cause.get("affected_segments", [])
        affected_metrics = root_cause.get("affected_metrics", [])
        
        if not affected_segments and not affected_metrics:
            # Default to total user base * estimated % affected
            total_users = metrics.get("total_users", 100000)
            return int(total_users * 0.1)  # 10% default
        
        # Sum users in affected segments
        total = 0
        for segment in affected_segments:
            segment_size = metrics.get(f"segment_{segment}_size", 0)
            total += segment_size
        
        if total > 0:
            return total
        
        # Fallback: use metrics
        for metric in affected_metrics:
            metric_users = metrics.get(f"{metric}_users", 0)
            total += metric_users
        
        return max(total, 1)
    
    def estimate_impact(self, root_cause: Dict) -> float:
        """Estimate impact (0.25 to 3)."""
        # Get impact from root cause type
        description = root_cause.get("description", "").lower()
        
        # Check for high-impact keywords
        high_impact_keywords = ["retention", "churn", "revenue", "conversion", "crash"]
        for kw in high_impact_keywords:
            if kw in description:
                return 2.5
        
        medium_keywords = ["performance", "slow", "conversion", "activation"]
        for kw in medium_keywords:
            if kw in description:
                return 1.5
        
        low_keywords = ["ui", "ux", "feature", "usability", "cosmetic"]
        for kw in low_keywords:
            if kw in description:
                return 0.75
        
        return 1.0  # Default medium
    
    def estimate_confidence(self, root_cause: Dict) -> float:
        """Estimate confidence from root cause."""
        return root_cause.get("confidence", 0.5)
    
    def estimate_effort(self, root_cause: Dict, evidence: List[Dict]) -> int:
        """Estimate engineering effort in person-weeks."""
        description = root_cause.get("description", "").lower()
        
        # Base effort by problem type
        if any(kw in description for kw in ["crash", "bug", "stability"]):
            base_effort = 2  # Bug fixes usually 1-4 weeks
        elif any(kw in description for kw in ["performance", "slow", "speed"]):
            base_effort = 4  # Performance work
        elif any(kw in description for kw in ["feature", "new", "add"]):
            base_effort = 6  # New features
        elif any(kw in description for kw in ["ui", "ux", "design", "usability"]):
            base_effort = 3  # UI/UX changes
        elif any(kw in description for kw in ["pricing", "billing", "subscription"]):
            base_effort = 2  # Config changes
        else:
            base_effort = 4  # Default
        
        # Adjust based on evidence
        evidence_count = len(evidence)
        if evidence_count > 10:
            base_effort = int(base_effort * 0.8)  # Well-understood problems are easier
        elif evidence_count < 3:
            base_effort = int(base_effort * 1.3)  # Less evidence = more uncertainty
        
        # Cap effort
        return max(1, min(base_effort, 20))


class RevenueEstimator:
    """Estimates revenue impact of recommendations."""
    
    def __init__(self, metrics: Dict):
        self.metrics = metrics
        self.avg_revenue_per_user = metrics.get("arpu", 50)  # Monthly ARPU
        self.monthly_users = metrics.get("mau", 100000)
    
    def estimate(self, root_cause: Dict, recommendation: Dict) -> float:
        """Estimate monthly revenue impact in dollars."""
        description = root_cause.get("description", "").lower()
        reach = recommendation.get("reach", 0)
        
        # Impact multipliers by problem type
        if "retention" in root_cause.get("description", "").lower():
            # Retention improvement: reduce churn
            churn_rate = self.metrics.get("churn_rate", 0.05)
            improvement = 0.1  # Assume 10% relative improvement
            retained_users = reach * churn_rate * improvement
            return retained_users * self.avg_revenue_per_user * 12  # Annual
        
        elif "conversion" in root_cause.get("description", "").lower():
            # Conversion improvement
            conversion_rate = self.metrics.get("conversion_rate", 0.03)
            improvement = 0.05  # 5% relative improvement
            new_conversions = reach * improvement
            return new_conversions * self.avg_revenue_per_user * 12
        
        elif "revenue" in root_cause.get("description", "").lower():
            # Direct revenue impact
            return reach * self.avg_revenue_per_user * 0.1  # 10% lift
        
        elif "performance" in root_cause.get("description", "").lower() or "slow" in root_cause.get("description", "").lower():
            # Performance improvement -> conversion/retention lift
            return reach * self.avg_revenue_per_user * 0.05
        
        # Default small impact
        return reach * self.avg_revenue_per_user * 0.02


class StrategicAlignmentScorer:
    """Scores strategic alignment (1-5)."""
    
    STRATEGIC_GOALS = {
        "growth": ["growth", "acquisition", "conversion", "activation", "signup"],
        "retention": ["retention", "churn", "engagement", "loyalty"],
        "monetization": ["revenue", "arpu", "pricing", "upsell", "expansion"],
        "stability": ["stability", "reliability", "performance", "bugs", "crash"],
        "user_experience": ["ux", "ui", "usability", "onboarding", "satisfaction"],
    }
    
    def score(self, root_cause: Dict, recommendation: Dict) -> int:
        """Score strategic alignment 1-5."""
        description = (root_cause.get("description", "") + " " + 
                      recommendation.get("description", "")).lower()
        
        scores = {}
        for goal, keywords in self.STRATEGIC_GOALS.items():
            matches = sum(1 for kw in keywords if kw in description)
            scores[goal] = min(matches * 0.5 + 1, 5)
        
        # Return max alignment
        return max(scores.values())


class RiskAssessor:
    """Assesses implementation risk (1-5, where 1=low risk)."""
    
    def assess(self, root_cause: Dict, evidence: List[Dict]) -> int:
        """Assess risk 1-5 (1=low, 5=high)."""
        description = root_cause.get("description", "").lower()
        evidence_count = len(evidence)
        
        # Base risk
        risk = 3  # Medium default
        
        # High risk indicators
        if any(kw in description for kw in ["database", "migration", "schema", "infrastructure"]):
            risk += 2
        elif any(kw in description for kw in ["payment", "billing", "security", "auth"]):
            risk += 1
        elif any(kw in description for kw in ["mobile", "ios", "android", "native"]):
            risk += 1
        
        # Evidence reduces risk
        if len(evidence) > 10:
            risk -= 1
        elif len(evidence) < 3:
            risk += 1
        
        # Cap at 1-5
        return max(1, min(risk, 5))


class RecommendationBuilder:
    """Builds recommendations from root causes."""
    
    def __init__(self, metrics: Dict):
        self.metrics = metrics
        self.rice_estimator = RICEEstimator()
        self.revenue_estimator = RevenueEstimator(metrics)
        self.strategic_scorer = StrategicAlignmentScorer()
        self.risk_assessor = RiskAssessor()
    
    def build_recommendations(
        self,
        root_causes: List[Dict],
        evidence: List[Dict],
    ) -> List[Dict]:
        """Build recommendations from root causes."""
        
        recommendations = []
        
        for i, cause in enumerate(root_causes):
            if cause.get("confidence", 0) < 0.3:
                continue  # Skip low confidence causes
            
            # Generate recommendation action
            action = self._generate_action(cause)
            
            # Estimate RICE components
            reach = self.rice_estimator.estimate_reach(cause, self.metrics)
            impact = self.rice_estimator.estimate_impact(cause)
            confidence = self.rice_estimator.estimate_confidence(cause)
            effort = self.rice_estimator.estimate_effort(cause, [])
            
            rice = RICEScore(
                reach=reach,
                impact=impact,
                confidence=confidence,
                effort=effort,
            )
            
            # Extended factors
            revenue_impact = self.revenue_estimator.estimate(cause, {})
            strategic_alignment = self.strategic_scorer.score(cause, {})
            risk = self.risk_assessor.assess(cause, [])
            
            rice.revenue_impact = revenue_impact
            rice.strategic_alignment = strategic_alignment
            rice.risk = risk
            
            # Create recommendation
            rec = Recommendation(
                title=f"Fix: {cause['description'][:80]}",
                description=self._generate_description(cause, action),
                rice=rice,
                evidence_summary=self._generate_evidence_summary(cause),
                root_cause_ids=[cause.get("id", "")],
                supporting_evidence=cause.get("evidence_ids", []),
            )
            
            recommendations.append({
                "id": str(uuid.uuid4()),
                "title": rec.title,
                "description": rec.description,
                "rice_score": rec.rice_score,
                "extended_score": rec.extended_score,
                "priority": rec.priority.value,
                "rice": {
                    "reach": rec.rice.reach,
                    "impact": rec.rice.impact,
                    "confidence": rec.rice.confidence,
                    "effort": rec.rice.effort,
                    "revenue_impact": rec.rice.revenue_impact,
                    "strategic_alignment": rec.rice.strategic_alignment,
                    "risk": rec.rice.risk,
                },
                "evidence_summary": rec.evidence_summary,
                "root_cause_ids": rec.root_cause_ids,
                "supporting_evidence": rec.supporting_evidence,
                "status": "proposed",
                "action": action,
            })
        
        # Sort by extended score
        recommendations.sort(key=lambda r: r["extended_score"], reverse=True)
        
        return recommendations
    
    def _generate_action(self, cause: Dict) -> str:
        """Generate specific action from root cause."""
        desc = cause.get("description", "").lower()
        
        if "retention" in cause.get("description", "").lower():
            return "Implement retention improvements: improve onboarding, add engagement hooks, reduce friction"
        elif "conversion" in desc or "funnel" in desc:
            return "Optimize conversion funnel: A/B test key pages, reduce friction, improve messaging"
        elif "retention" in desc or "churn" in desc:
            return "Reduce churn: improve onboarding, add re-engagement campaigns, fix pain points"
        elif "performance" in desc or "slow" in desc:
            return "Improve performance: optimize queries, add caching, upgrade infrastructure"
        elif "stability" in desc or "crash" in desc or "bug" in desc:
            return "Fix stability issues: prioritize crash fixes, add monitoring, improve error handling"
        elif "pricing" in desc:
            return "Optimize pricing: test price points, adjust plans, improve value communication"
        elif "feature" in desc or "request" in desc:
            return "Implement requested features: prioritize by user demand and effort"
        else:
            return "Investigate and address root cause based on evidence"
    
    def _generate_description(self, cause: Dict, action: str) -> str:
        return f"{cause['description']}. Recommended action: {action}"
    
    def _generate_evidence_summary(self, cause: Dict) -> str:
        breakdown = cause.get("evidence_breakdown", {})
        parts = []
        if breakdown.get("sql", 0) > 0:
            parts.append(f"{breakdown['sql']} SQL queries")
        if breakdown.get("feedback", 0) > 0:
            parts.append(f"{breakdown['feedback']} feedback items")
        if breakdown.get("experiment", 0) > 0:
            parts.append(f"{breakdown['experiment']} experiments")
        if breakdown.get("metric", 0) > 0:
            parts.append(f"{breakdown['metric']} metrics")
        return f"Supported by: {', '.join(parts)}"


def generate_recommendations(
    root_causes: List[Dict],
    evidence: List[Dict],
    metrics: Dict,
) -> List[Dict]:
    """Generate prioritized recommendations from root causes."""
    builder = RecommendationBuilder(metrics)
    return builder.build_recommendations(root_causes, evidence)


def calculate_rice(
    reach: int,
    impact: float,
    confidence: float,
    effort: int,
    revenue_impact: float = None,
    strategic_alignment: int = None,
    risk: int = None,
) -> Dict[str, Any]:
    """Calculate RICE score with extended factors."""
    rice = RICEScore(
        reach=reach,
        impact=impact,
        confidence=confidence,
        effort=effort,
        revenue_impact=revenue_impact,
        strategic_alignment=strategic_alignment,
        risk=risk,
    )
    
    return {
        "rice_score": rice.rice_score,
        "extended_score": rice.extended_score,
        "priority": PriorityLevel.P0 if rice.extended_score >= 1000 else 
                     PriorityLevel.P1 if rice.extended_score >= 300 else
                     PriorityLevel.P2 if rice.extended_score >= 100 else
                     PriorityLevel.P3 if rice.extended_score >= 30 else
                     PriorityLevel.ICEBOX,
        "components": {
            "reach": reach,
            "impact": impact,
            "confidence": confidence,
            "effort": effort,
            "revenue_impact": revenue_impact,
            "strategic_alignment": strategic_alignment,
            "risk": risk,
        },
    }