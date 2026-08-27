"""
Decision Agent - Converts root causes into prioritized product recommendations.
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from agents.decision_agent.rice import (
    generate_recommendations,
    calculate_rice,
    RICEScore,
    Recommendation,
    RICEEstimator,
    RevenueEstimator,
    StrategicAlignmentScorer,
    RiskAssessor,
    RecommendationBuilder,
    PriorityLevel,
)
from agents.base import Evidence, EvidenceType
from config.settings import settings


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
class DecisionAgentState:
    """State for Decision Agent."""
    question: str
    root_causes: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    prioritized_recommendations: List[Dict[str, Any]] = field(default_factory=list)
    final_package: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    done: bool = False


class DecisionAgent:
    """Agent for generating prioritized product recommendations."""
    
    def __init__(self):
        self.llm = _create_llm()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(DecisionAgentState)
        
        # Nodes
        workflow.add_node("generate_recommendations", self._generate_recommendations_node)
        workflow.add_node("score_recommendations", self._score_recommendations_node)
        workflow.add_node("prioritize_recommendations", self._prioritize_recommendations_node)
        workflow.add_node("create_final_package", self._create_final_package_node)
        
        # Edges
        workflow.set_entry_point("generate_recommendations")
        workflow.add_edge("generate_recommendations", "score_recommendations")
        workflow.add_edge("score_recommendations", "prioritize_recommendations")
        workflow.add_edge("prioritize_recommendations", "create_final_package")
        workflow.add_edge("create_final_package", END)
        
        return workflow.compile()
    
    def _generate_recommendations_node(self, state: DecisionAgentState) -> DecisionAgentState:
        """Generate initial recommendations from root causes."""
        if not state.root_causes:
            return DecisionAgentState(
                question=state.question,
                root_causes=state.root_causes,
                evidence=state.evidence,
                metrics=state.metrics,
                recommendations=[],
                error="No root causes provided",
            )
        
        # Generate recommendations using RICE framework
        recommendations = generate_recommendations(
            root_causes=state.root_causes,
            evidence=state.evidence,
            metrics=state.metrics,
        )
        
        return DecisionAgentState(
            question=state.question,
            root_causes=state.root_causes,
            evidence=state.evidence,
            metrics=state.metrics,
            recommendations=recommendations,
        )
    
    def _score_recommendations_node(self, state: DecisionAgentState) -> DecisionAgentState:
        """Score recommendations with RICE and extended factors."""
        for rec in state.recommendations:
            rec["llm_assessment"] = self._assess_recommendation(rec)
        
        return state
    
    def _assess_recommendation(self, rec: Dict) -> Dict[str, Any]:
        """LLM-based qualitative assessment of recommendation."""
        prompt = f"""
        Assess this product recommendation:
        
        Title: {rec.get('title', '')}
        Description: {rec.get('description', '')}
        Action: {rec.get('action', '')}
        
        RICE Score: {rec.get('rice_score', 0):.1f}
        Extended Score: {rec.get('extended_score', 0):.1f}
        Priority: {rec.get('priority', 'Unknown')}
        
        RICE Components:
        - Reach: {rec.get('rice', {}).get('reach', 0):,} users
        - Impact: {rec.get('rice', {}).get('impact', 0):.2f}
        - Confidence: {rec.get('rice', {}).get('confidence', 0):.0%}
        - Effort: {rec.get('rice', {}).get('effort', 0)} person-weeks
        - Revenue Impact: ${rec.get('rice', {}).get('revenue_impact', 0):,.0f}
        - Strategic Alignment: {rec.get('rice', {}).get('strategic_alignment', 0)}/5
        - Risk: {rec.get('rice', {}).get('risk', 0)}/5
        
        Provide:
        1. Feasibility assessment (technical, organizational)
        2. Dependencies and prerequisites
        3. Timeline estimate
        4. Success metrics
        5. Risk mitigation suggestions
        
        Return as structured JSON.
        """
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            import json
            return json.loads(response.content)
        except:
            return {
                "feasibility": "medium",
                "dependencies": [],
                "timeline_weeks": rec.get("rice", {}).get("effort", 4),
                "success_metrics": [],
                "risk_mitigation": [],
            }
    
    def _prioritize_recommendations_node(self, state: DecisionAgentState) -> DecisionAgentState:
        """Prioritize recommendations by extended score."""
        prioritized = sorted(
            state.recommendations,
            key=lambda r: r.get("extended_score", 0),
            reverse=True
        )
        
        for i, rec in enumerate(prioritized):
            rec["rank"] = i + 1
            rec["is_top_priority"] = (i == 0)
        
        return DecisionAgentState(
            question=state.question,
            root_causes=state.root_causes,
            evidence=state.evidence,
            metrics=state.metrics,
            recommendations=state.recommendations,
            prioritized_recommendations=prioritized,
        )
    
    def _create_final_package_node(self, state: DecisionAgentState) -> DecisionAgentState:
        """Create final decision package."""
        if not state.prioritized_recommendations:
            return DecisionAgentState(
                question=state.question,
                root_causes=state.root_causes,
                evidence=state.evidence,
                metrics=state.metrics,
                recommendations=state.recommendations,
                prioritized_recommendations=state.prioritized_recommendations,
                final_package={"error": "No recommendations generated"},
                error="No recommendations generated",
                done=True,
            )
        
        top = state.prioritized_recommendations[0]
        
        final_package = {
            "investigation_question": state.question,
            "timestamp": datetime.utcnow().isoformat(),
            "executive_summary": self._generate_executive_summary(state),
            "top_recommendation": {
                "title": top.get("title"),
                "priority": top.get("priority"),
                "rice_score": top.get("rice_score"),
                "extended_score": top.get("extended_score"),
                "action": top.get("action"),
                "estimated_effort_weeks": top.get("rice", {}).get("effort"),
                "estimated_revenue_impact": top.get("rice", {}).get("revenue_impact"),
                "confidence": top.get("rice", {}).get("confidence"),
            },
            "all_recommendations": [
                {
                    "rank": r.get("rank"),
                    "title": r.get("title"),
                    "priority": r.get("priority"),
                    "rice_score": r.get("rice_score"),
                    "extended_score": r.get("extended_score"),
                    "effort_weeks": r.get("rice", {}).get("effort"),
                    "revenue_impact": r.get("rice", {}).get("revenue_impact"),
                }
                for r in state.prioritized_recommendations[:10]
            ],
            "root_cause_summary": [
                {
                    "description": rc.get("description"),
                    "confidence": rc.get("confidence"),
                    "evidence_count": sum(rc.get("evidence_breakdown", {}).values()),
                }
                for rc in state.root_causes[:5]
            ],
            "evidence_summary": {
                "total_pieces": len(state.evidence),
                "by_source": self._count_evidence_by_source(state.evidence),
            },
            "next_steps": self._generate_next_steps(state),
        }
        
        return DecisionAgentState(
            question=state.question,
            root_causes=state.root_causes,
            evidence=state.evidence,
            metrics=state.metrics,
            recommendations=state.recommendations,
            prioritized_recommendations=state.prioritized_recommendations,
            final_package=final_package,
            done=True,
        )
    
    def _generate_executive_summary(self, state: DecisionAgentState) -> str:
        """Generate executive summary."""
        if not state.prioritized_recommendations:
            return "No recommendations generated."
        
        top = state.prioritized_recommendations[0]
        rc_count = len(state.root_causes)
        ev_count = len(state.evidence)
        
        return (
            f"Investigation into '{state.question}' identified {rc_count} root causes "
            f"from {ev_count} pieces of evidence. "
            f"Top recommendation: '{top.get('title')}' (Priority: {top.get('priority')}, "
            f"RICE: {top.get('rice_score', 0):.0f}, Effort: {top.get('rice', {}).get('effort', 0)} weeks). "
            f"Estimated revenue impact: ${top.get('rice', {}).get('revenue_impact', 0):,.0f}/year."
        )
    
    def _count_evidence_by_source(self, evidence: List[Dict]) -> Dict[str, int]:
        counts = {}
        for ev in evidence:
            src = ev.get("source", "unknown")
            counts[src] = counts.get(src, 0) + 1
        return counts
    
    def _generate_next_steps(self, state: DecisionAgentState) -> List[str]:
        steps = []
        
        if state.prioritized_recommendations:
            top = state.prioritized_recommendations[0]
            steps.append(f"1. Review and approve top recommendation: {top.get('title')}")
            steps.append(f"2. Assign engineering team (effort: {top.get('rice', {}).get('effort', 0)} weeks)")
            steps.append("3. Define success metrics and tracking plan")
            steps.append("4. Plan rollout strategy (canary, phased, full)")
            steps.append("5. Set up monitoring and alerting")
        
        steps.append("6. Validate root causes with stakeholders")
        steps.append("7. Schedule follow-up analysis in 30 days")
        
        return steps
    
    def decide(
        self,
        root_causes: List[Dict],
        evidence: List[Dict],
        metrics: Dict,
        question: str = "What should we do?",
    ) -> Dict[str, Any]:
        """Run decision analysis."""
        initial_state = DecisionAgentState(
            question=question,
            root_causes=root_causes,
            evidence=evidence,
            metrics=metrics,
        )
        
        result = self.graph.invoke(initial_state)
        
        return {
            "question": question,
            "recommendations": result.get("prioritized_recommendations", []),
            "final_package": result.get("final_package", {}),
            "error": result.get("error"),
        }


def generate_product_recommendations(
    root_causes: List[Dict],
    evidence: List[Dict],
    metrics: Dict,
) -> List[Dict]:
    """Generate prioritized product recommendations."""
    from agents.decision_agent.rice import generate_recommendations
    return generate_recommendations(root_causes, evidence, metrics)


def score_recommendation(
    reach: int,
    impact: float,
    confidence: float,
    effort: int,
    revenue_impact: float = None,
    strategic_alignment: int = None,
    risk: int = None,
) -> Dict[str, Any]:
    """Calculate RICE score for a recommendation."""
    return calculate_rice(reach, impact, confidence, effort, revenue_impact, strategic_alignment, risk)
