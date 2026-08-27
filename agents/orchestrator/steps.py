"""
Orchestrator Steps - Individual investigation step implementations.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime

from agents.base import InvestigationState, InvestigationStatus, Anomaly, MetricValue
from agents.sql_agent import run_sql_investigation
from agents.feedback_agent import run_feedback_investigation
from agents.experiment_agent import run_experiment_investigation
from agents.root_cause_agent import analyze_root_causes
from agents.decision_agent import generate_product_recommendations

from config.settings import settings


async def metrics_analysis_step(state: InvestigationState) -> InvestigationState:
    """Analyze current metrics and compute key indicators."""
    # This would typically query the metric_snapshots table
    # For now, return state with placeholder
    return InvestigationState(
        **state.__dict__,
        metrics_analysis={
            "analyzed_at": datetime.utcnow().isoformat(),
            "metrics_analyzed": list(state.metrics.keys()),
            "summary": "Metrics analysis completed",
        },
        completed_steps=list(state.completed_steps) + ["metrics_analysis"],
        current_step="anomaly_detection",
    )


async def anomaly_detection_step(state: InvestigationState) -> InvestigationState:
    """Detect anomalies in metrics."""
    # Check for anomalies in current metrics
    anomalies = []
    
    for name, metric in state.metrics.items():
        if metric.sample_size and metric.sample_size < 30:
            # Flag small sample size
            state.step_errors.setdefault("anomaly_detection", []).append(
                f"Metric {name} has small sample size: {metric.sample_size}"
            )
    
    # If we have an anomaly from trigger, include it
    if state.anomaly:
        anomalies.append(state.anomaly)
    
    return InvestigationState(
        **state.__dict__,
        anomaly_detection={
            "detected_at": datetime.utcnow().isoformat(),
            "anomalies_found": len(anomalies),
            "anomalies": [a.__dict__ if hasattr(a, '__dict__') else a for a in anomalies],
        },
        completed_steps=list(state.completed_steps) + ["anomaly_detection"],
        current_step="sql_investigation",
    )


async def sql_investigation_step(state: InvestigationState) -> InvestigationState:
    """Run SQL investigation agent."""
    if not state.requires_sql:
        return InvestigationState(
            **state.__dict__,
            sql_investigation={"skipped": True, "reason": "SQL not required"},
            completed_steps=list(state.completed_steps) + ["sql_investigation"],
            current_step="feedback_analysis",
        )
    
    try:
        # Run SQL investigation
        result = run_sql_investigation(
            question=state.question,
            anomaly_id=state.anomaly.id if state.anomaly else None,
        )
        
        # Convert to state format
        sql_queries = result.get("steps", [])
        evidence = []
        for step in sql_queries:
            evidence.append({
                "type": "fact",
                "source": "sql",
                "content": step.get("explanation", ""),
                "confidence": 0.9,
                "citation": step.get("sql", ""),
            })
        
        return InvestigationState(
            **state.__dict__,
            sql_investigation={
                "completed_at": datetime.utcnow().isoformat(),
                "steps": len(sql_queries),
                "evidence_generated": len(evidence),
                "final_answer": result.get("final_answer"),
                "confidence": result.get("confidence"),
            },
            sql_queries=[q.__dict__ for q in state.sql_queries],
            sql_results=[r.__dict__ for r in state.sql_results],
            evidence=state.evidence + evidence,
            sql_agent_output=result,
            completed_steps=list(state.completed_steps) + ["sql_investigation"],
            current_step="feedback_analysis",
        )
    except Exception as e:
        state.step_errors.setdefault("sql_investigation", []).append(str(e))
        state.retry_count["sql_investigation"] = state.retry_count.get("sql_investigation", 0) + 1
        
        if state.retry_count["sql_investigation"] >= state.max_retries:
            return InvestigationState(
                **state.__dict__,
                status=InvestigationStatus.FAILED,
                error=f"SQL investigation failed after {state.max_retries} retries: {e}",
            )
        
        # Return state to retry
        return state


async def feedback_analysis_step(state: InvestigationState) -> InvestigationState:
    """Run feedback analysis agent."""
    if state.skip_feedback:
        return InvestigationState(
            **state.__dict__,
            feedback_analysis={"skipped": True},
            completed_steps=list(state.completed_steps) + ["feedback_analysis"],
            current_step="experiment_analysis",
        )
    
    try:
        result = run_feedback_investigation(
            question=state.question,
        )
        
        # Convert to evidence
        evidence = []
        for theme in result.get("themes", []):
            evidence.append({
                "type": "inference",
                "source": "feedback",
                "content": f"Theme '{theme['theme']}' from {theme['size']} feedback items. Sentiment: {theme['sentiment']}",
                "confidence": 0.7,
                "citation": f"feedback_theme_{theme['theme']}",
            })
        
        for ev in result.get("evidence", []):
            evidence.append(ev)
        
        return InvestigationState(
            **state.__dict__,
            feedback_analysis={
                "completed_at": datetime.utcnow().isoformat(),
                "themes_found": len(result.get("themes", [])),
                "evidence_generated": len(evidence),
            },
            feedback_evidence=state.feedback_evidence + evidence,
            feedback_agent_output=result,
            completed_steps=list(state.completed_steps) + ["feedback_analysis"],
            current_step="experiment_analysis",
        )
    except Exception as e:
        state.step_errors.setdefault("feedback_analysis", []).append(str(e))
        state.retry_count["feedback_analysis"] = state.retry_count.get("feedback_analysis", 0) + 1
        
        if state.retry_count["feedback_analysis"] >= state.max_retries:
            return InvestigationState(
                **state.__dict__,
                status=InvestigationStatus.FAILED,
                error=f"Feedback analysis failed: {e}",
            )
        
        return state


async def experiment_analysis_step(state: InvestigationState) -> InvestigationState:
    """Run experiment analysis agent."""
    if state.skip_experiment:
        return InvestigationState(
            **state.__dict__,
            experiment_analysis={"skipped": True},
            completed_steps=list(state.completed_steps) + ["experiment_analysis"],
            current_step="evidence_aggregation",
        )
    
    try:
        result = run_experiment_investigation(
            question=state.question,
        )
        
        evidence = []
        for ev in result.get("evidence", []):
            evidence.append(ev)
        
        return InvestigationState(
            **state.__dict__,
            experiment_analysis={
                "completed_at": datetime.utcnow().isoformat(),
                "experiment_analyzed": result.get("experiment_id"),
                "evidence_generated": len(evidence),
            },
            experiment_results=state.experiment_results + evidence,
            experiment_agent_output=result,
            completed_steps=list(state.completed_steps) + ["experiment_analysis"],
            current_step="evidence_aggregation",
        )
    except Exception as e:
        state.step_errors.setdefault("experiment_analysis", []).append(str(e))
        state.retry_count["experiment_analysis"] = state.retry_count.get("experiment_analysis", 0) + 1
        
        if state.retry_count["experiment_analysis"] >= state.max_retries:
            return InvestigationState(
                **state.__dict__,
                status=InvestigationStatus.FAILED,
                error=f"Experiment analysis failed: {e}",
            )
        
        return state


async def evidence_aggregation_step(state: InvestigationState) -> InvestigationState:
    """Aggregate all evidence from all agents."""
    all_evidence = []
    all_evidence.extend(state.evidence)
    all_evidence.extend(state.feedback_evidence)
    all_evidence.extend(state.experiment_results)
    
    # Add SQL evidence
    for q, r in zip(state.sql_queries, state.sql_results):
        if r.get("success"):
            all_evidence.append({
                "type": "fact",
                "source": "sql",
                "content": f"Query: {q.get('explanation', '')}. Result: {r.get('row_count', 0)} rows",
                "confidence": 0.9,
                "citation": q.get("sql"),
            })
    
    # Deduplicate evidence
    seen = set()
    unique_evidence = []
    for ev in all_evidence:
        key = f"{ev.get('source')}:{ev.get('content', '')[:100]}"
        if key not in seen:
            seen.add(key)
            unique_evidence.append(ev)
    
    return InvestigationState(
        **state.__dict__,
        evidence=unique_evidence,
        completed_steps=list(state.completed_steps) + ["evidence_aggregation"],
        current_step="root_cause_analysis",
    )


async def root_cause_analysis_step(state: InvestigationState) -> InvestigationState:
    """Run root cause analysis."""
    try:
        result = analyze_root_causes(
            evidence=state.evidence,
            metrics={k: v.__dict__ if hasattr(v, '__dict__') else v for k, v in state.metrics.items()},
            anomaly=state.anomaly.__dict__ if state.anomaly else None,
        )
        
        return InvestigationState(
            **state.__dict__,
            root_causes=[c.__dict__ if hasattr(c, '__dict__') else c for c in result],
            root_cause_agent_output={"causes": result},
            completed_steps=list(state.completed_steps) + ["root_cause_analysis"],
            current_step="decision_making",
        )
    except Exception as e:
        state.step_errors.setdefault("root_cause_analysis", []).append(str(e))
        return InvestigationState(
            **state.__dict__,
            status=InvestigationStatus.FAILED,
            error=f"Root cause analysis failed: {e}",
        )


async def decision_making_step(state: InvestigationState) -> InvestigationState:
    """Run decision agent to generate recommendations."""
    try:
        result = generate_product_recommendations(
            root_causes=[c if isinstance(c, dict) else c.__dict__ for c in state.root_causes],
            evidence=state.evidence,
            metrics={k: v.__dict__ if hasattr(v, '__dict__') else v for k, v in state.metrics.items()},
        )
        
        return InvestigationState(
            **state.__dict__,
            recommendations=[r if isinstance(r, dict) else r.__dict__ for r in result],
            decision_agent_output={"recommendations": result},
            completed_steps=list(state.completed_steps) + ["decision_making"],
            current_step="finalization",
        )
    except Exception as e:
        state.step_errors.setdefault("decision_making", []).append(str(e))
        return InvestigationState(
            **state.__dict__,
            status=InvestigationStatus.FAILED,
            error=f"Decision making failed: {e}",
        )


async def finalization_step(state: InvestigationState) -> InvestigationState:
    """Finalize investigation and create final report."""
    # Calculate overall confidence
    confidence_factors = []
    
    if state.sql_agent_output:
        confidence_factors.append(state.sql_agent_output.get("confidence", 0.5))
    if state.feedback_agent_output:
        confidence_factors.append(0.7)  # Default feedback confidence
    if state.experiment_agent_output:
        confidence_factors.append(0.8)
    if state.root_cause_agent_output:
        root_causes = state.root_cause_agent_output.get("causes", [])
        if root_causes:
            confidence_factors.append(max(c.get("confidence", 0) for c in root_causes))
    
    overall_confidence = sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0.5
    
    # Generate execution trace
    trace = []
    for step in state.completed_steps:
        trace.append({
            "step": step,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "completed",
        })
    
    for step, errors in state.step_errors.items():
        for err in errors:
            trace.append({
                "step": step,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "error",
                "error": err,
            })
    
    return InvestigationState(
        **state.__dict__,
        status=InvestigationStatus.COMPLETED,
        confidence=overall_confidence,
        completed_at=datetime.utcnow(),
        execution_trace=trace,
        completed_steps=list(state.completed_steps) + ["finalization"],
        current_step="complete",
    )


async def error_handling_step(state: InvestigationState) -> InvestigationState:
    """Handle errors and determine recovery."""
    # This is called when a step fails
    return InvestigationState(
        **state.__dict__,
        status=InvestigationStatus.FAILED,
        error="Step failed and max retries exceeded",
    )