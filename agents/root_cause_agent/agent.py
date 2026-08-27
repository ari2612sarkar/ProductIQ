"""
Root Cause Agent - LangGraph-based agent for synthesizing root causes from evidence.
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from agents.root_cause_agent.synthesizer import (
    RootCauseAnalyzer,
    analyze_root_causes,
    RootCause,
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
class RootCauseAgentState:
    """State for Root Cause Agent."""
    question: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    anomaly: Optional[Dict[str, Any]] = None
    root_causes: List[Dict[str, Any]] = field(default_factory=list)
    classified_evidence: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    done: bool = False


class RootCauseAgent:
    """Agent for synthesizing root causes from multi-source evidence."""
    
    def __init__(self):
        self.llm = _create_llm()
        self.analyzer = RootCauseAnalyzer()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(RootCauseAgentState)
        
        # Nodes
        workflow.add_node("classify_evidence", self._classify_evidence_node)
        workflow.add_node("synthesize_causes", self._synthesize_causes_node)
        workflow.add_node("rank_causes", self._rank_causes_node)
        workflow.add_node("generate_explanation", self._generate_explanation_node)
        
        # Edges
        workflow.set_entry_point("classify_evidence")
        workflow.add_edge("classify_evidence", "synthesize_causes")
        workflow.add_edge("synthesize_causes", "rank_causes")
        workflow.add_edge("rank_causes", "generate_explanation")
        workflow.add_edge("generate_explanation", END)
        
        return workflow.compile()
    
    def _classify_evidence_node(self, state: RootCauseAgentState) -> RootCauseAgentState:
        """Classify evidence as FACT, INFERENCE, or HYPOTHESIS."""
        from agents.root_cause_agent.synthesizer import EvidenceClassifier, EvidenceSource
        
        classifier = EvidenceClassifier()
        classified = []
        
        for ev in state.evidence:
            # Determine source
            source_str = ev.get("source", "unknown")
            source = EvidenceSource(source_str) if source_str in [s.value for s in EvidenceSource] else EvidenceSource.METRIC
            
            # Classify
            ev_obj = type('obj', (object,), {
                'source': source,
                'content': ev.get("content", ""),
            })
            ev_type = EvidenceClassifier.classify(ev_obj)
            
            classified.append({
                **ev,
                "type": ev_type.value,
                "classified_at": datetime.utcnow().isoformat(),
            })
        
        return RootCauseAgentState(
            question=state.question,
            evidence=state.evidence,
            metrics=state.metrics,
            anomaly=state.anomaly,
            root_causes=state.root_causes,
            classified_evidence=classified,
        )
    
    def _synthesize_causes_node(self, state: RootCauseAgentState) -> RootCauseAgentState:
        """Synthesize root causes from classified evidence."""
        # Convert evidence to proper format
        from agents.base import Evidence as BaseEvidence, EvidenceType
        
        processed_evidence = []
        for ev in state.classified_evidence:
            processed_evidence.append(Evidence(
                id=ev.get("id", str(uuid.uuid4())),
                type=EvidenceType(ev.get("type", "fact")),
                source=ev.get("source", "unknown"),
                content=ev.get("content", ""),
                confidence=ev.get("confidence", 0.5),
                citation=ev.get("citation"),
                metadata=ev.get("metadata", {}),
            ))
        
        analyzer = RootCauseAnalyzer()
        causes = analyzer.analyze(
            evidence=processed_evidence,
            metrics=state.metrics,
            anomaly=state.anomaly,
        )
        
        root_causes = [
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
                "ruling_out_reasoning": c.ruling_out_reasoning,
            }
            for c in causes
        ]
        
        return RootCauseAgentState(
            question=state.question,
            evidence=state.evidence,
            metrics=state.metrics,
            anomaly=state.anomaly,
            root_causes=root_causes,
            classified_evidence=state.classified_evidence,
        )
    
    def _rank_causes_node(self, state: RootCauseAgentState) -> RootCauseAgentState:
        """Rank root causes by confidence and evidence quality."""
        # Sort by confidence
        ranked = sorted(state.root_causes, key=lambda c: c.get("confidence", 0), reverse=True)
        
        # Add ranking metadata
        for i, cause in enumerate(ranked):
            cause["rank"] = i + 1
            cause["is_primary"] = (i == 0)
        
        return RootCauseAgentState(
            question=state.question,
            evidence=state.evidence,
            metrics=state.metrics,
            anomaly=state.anomaly,
            root_causes=ranked,
            classified_evidence=state.classified_evidence,
        )
    
    def _generate_explanation_node(self, state: RootCauseAgentState) -> RootCauseAgentState:
        """Generate human-readable explanation of root cause analysis."""
        if not state.root_causes:
            return RootCauseAgentState(
                question=state.question,
                evidence=state.evidence,
                metrics=state.metrics,
                anomaly=state.anomaly,
                root_causes=state.root_causes,
                error="No root causes identified",
            )
        
        primary = state.root_causes[0]
        
        prompt = f"""
        Provide a clear, executive summary of the root cause analysis.
        
        Primary Root Cause: {state.root_causes[0].get('description', 'Unknown')}
        Confidence: {state.root_causes[0].get('confidence', 0):.1%}
        
        Evidence Breakdown:
        - SQL Evidence: {state.root_causes[0].get('evidence_breakdown', {}).get('sql', 0)}
        - Feedback: {state.root_causes[0].get('evidence_breakdown', {}).get('feedback', 0)}
        - Experiment: {state.root_causes[0].get('evidence_breakdown', {}).get('experiment', 0)}
        - Metric: {state.root_causes[0].get('evidence_breakdown', {}).get('metric', 0)}
        
        Competing Hypotheses: {state.root_causes[0].get('competing_hypotheses', [])}
        
        All Root Causes (ranked):
        """
        
        for i, cause in enumerate(state.root_causes[:5]):
            prompt += f"\n{i+1}. {cause['description']} (confidence: {cause['confidence']:.1%})"
        
        prompt += """

Provide:
1. Executive summary (2-3 sentences)
2. Key evidence supporting primary cause
3. Why competing hypotheses are less likely
4. Confidence assessment
5. Recommended next steps
"""
        
        response = self.llm.invoke([HumanMessage(content=prompt)])
        
        # Add explanation to primary cause
        for cause in state.root_causes:
            cause["explanation"] = response.content
        
        return RootCauseAgentState(
            question=state.question,
            evidence=state.evidence,
            metrics=state.metrics,
            anomaly=state.anomaly,
            root_causes=state.root_causes,
            classified_evidence=state.classified_evidence,
            done=True,
        )
    
    def analyze(
        self,
        evidence: List[Dict[str, Any]],
        metrics: Dict[str, Any] = None,
        anomaly: Optional[Dict[str, Any]] = None,
        question: str = "What is the root cause?",
    ) -> Dict[str, Any]:
        """Run root cause analysis."""
        initial_state = RootCauseAgentState(
            question=question,
            evidence=evidence,
            metrics=metrics or {},
            anomaly=anomaly,
        )
        
        result = self.graph.invoke(initial_state)
        
        return {
            "question": question,
            "root_causes": result.get("root_causes", []),
            "classified_evidence": result.get("classified_evidence", []),
            "primary_cause": result.get("root_causes", [{}])[0] if result.get("root_causes") else None,
        }


def analyze_root_causes(
    evidence: List[Dict[str, Any]],
    metrics: Dict[str, Any] = None,
    anomaly: Optional[Dict] = None,
    question: str = "What is the root cause?",
) -> Dict[str, Any]:
    """Run root cause analysis."""
    agent = RootCauseAgent()
    return agent.analyze(evidence, metrics, anomaly, question)