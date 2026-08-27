"""
Orchestrator Agent - Main coordinator for the investigation workflow.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from agents.orchestrator.state import (
    InvestigationState,
    InvestigationStep,
    create_initial_state,
)
from agents.orchestrator.steps import (
    metrics_analysis_step,
    anomaly_detection_step,
    sql_investigation_step,
    feedback_analysis_step,
    experiment_analysis_step,
    evidence_aggregation_step,
    root_cause_analysis_step,
    decision_making_step,
    finalization_step,
    error_handling_step,
)
from agents.base import InvestigationStatus, TriggerType

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


class OrchestratorAgent:
    
    def __init__(self):
        self.llm = _create_llm()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(dict)  # Using dict for flexibility with our state
        
        # Add nodes
        workflow.add_node("metrics_analysis", metrics_analysis_step)
        workflow.add_node("anomaly_detection", anomaly_detection_step)
        workflow.add_node("sql_investigation", sql_investigation_step)
        workflow.add_node("feedback_analysis", feedback_analysis_step)
        workflow.add_node("experiment_analysis", experiment_analysis_step)
        workflow.add_node("evidence_aggregation", evidence_aggregation_step)
        workflow.add_node("root_cause_analysis", root_cause_analysis_step)
        workflow.add_node("decision_making", decision_making_step)
        workflow.add_node("finalization", finalization_step)
        workflow.add_node("error_handling", error_handling_step)
        
        # Define edges
        workflow.set_entry_point("metrics_analysis")
        
        workflow.add_edge("metrics_analysis", "anomaly_detection")
        workflow.add_edge("anomaly_detection", "sql_investigation")
        workflow.add_edge("sql_investigation", "feedback_analysis")
        workflow.add_edge("feedback_analysis", "experiment_analysis")
        workflow.add_edge("experiment_analysis", "evidence_aggregation")
        workflow.add_edge("evidence_aggregation", "root_cause_analysis")
        workflow.add_edge("root_cause_analysis", "decision_making")
        workflow.add_edge("decision_making", "finalization")
        workflow.add_edge("finalization", END)
        
        # Error handling edges (simplified - in production use conditional edges)
        workflow.add_edge("error_handling", END)
        
        return workflow.compile()
    
    def investigate(
        self,
        question: str,
        trigger: str = "manual",
        anomaly_id: Optional[str] = None,
        anomaly_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Run a full investigation."""
        # Create initial state
        trigger_enum = TriggerType.MANUAL
        if trigger == "anomaly":
            trigger_enum = TriggerType.ANOMALY
        elif trigger == "scheduled":
            trigger_enum = TriggerType.SCHEDULED
        
        initial_state = create_initial_state(
            question=question,
            trigger=trigger_enum,
        )
        
        # Add anomaly data if provided
        if anomaly_data:
            from agents.base import Anomaly
            anomaly = Anomaly(
                id=anomaly_data.get("id", ""),
                metric_name=anomaly_data.get("metric_name", ""),
                baseline_value=anomaly_data.get("baseline_value", 0),
                current_value=anomaly_data.get("current_value", 0),
                absolute_change=anomaly_data.get("absolute_change", 0),
                relative_change=anomaly_data.get("relative_change", 0),
                detection_method=anomaly_data.get("detection_method", ""),
                severity=anomaly_data.get("severity", "medium"),
                detected_at=datetime.utcnow(),
            )
            # Note: In real implementation, pass anomaly to state
        
        # Run the workflow
        config = {"configurable": {"thread_id": f"investigation_{datetime.utcnow().timestamp()}"}}
        
        try:
            result = self.graph.invoke(initial_state, config=config)
            
            # Extract final results
            return {
                "investigation_id": result.get("investigation_id"),
                "question": question,
                "status": result.get("status"),
                "confidence": result.get("confidence", 0),
                "completed_steps": result.get("completed_steps", []),
                "root_causes": result.get("root_causes", []),
                "recommendations": result.get("recommendations", []),
                "evidence_count": len(result.get("evidence", [])),
                "sql_queries": len(result.get("sql_queries", [])),
                "execution_time_ms": (datetime.utcnow() - result.get("created_at", datetime.utcnow())).total_seconds() * 1000,
                "final_package": result.get("final_package", {}),
                "errors": result.get("step_errors", {}),
            }
        except Exception as e:
            return {
                "question": question,
                "status": "failed",
                "error": str(e),
            }
    
    def investigate_async(
        self,
        question: str,
        trigger: str = "manual",
    ) -> Dict[str, Any]:
        """Run investigation asynchronously (returns immediately with investigation_id)."""
        # In production, this would queue the investigation for background processing
        # For now, run synchronously
        return self.investigate(question, trigger)
    
    def get_investigation_status(self, investigation_id: str) -> Dict[str, Any]:
        """Get status of an investigation."""
        # In production, query database
        return {
            "investigation_id": investigation_id,
            "status": "unknown",
        }


def run_investigation(
    question: str,
    trigger: str = "manual",
    anomaly_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a full investigation."""
    orchestrator = OrchestratorAgent()
    return orchestrator.investigate(question, trigger, anomaly_id)


def create_investigation(
    question: str,
    trigger: str = "manual",
) -> Dict[str, Any]:
    """Create a new investigation (async)."""
    orchestrator = OrchestratorAgent()
    return orchestrator.investigate_async(question, trigger)