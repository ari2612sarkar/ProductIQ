"""
Experiment Analyzer - Loads experiment data and runs statistical analysis.
"""
from typing import Dict, List, Any, Optional, Literal
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from db.schema.models import Experiment, ExperimentAssignment, Event, User
from agents.experiment_agent.statistics import (
    analyze_experiment,
    calculate_sample_size,
    power_analysis,
    ExperimentResult,
    ProportionTestResult,
    MeanTestResult,
    RatioTestResult,
)

from config.settings import settings


@dataclass
class ExperimentData:
    """Prepared experiment data for analysis."""
    experiment_id: str
    experiment_name: str
    metric: str
    metric_type: Literal["proportion", "mean", "ratio"]
    control_data: Dict[str, Any]
    treatment_data: Dict[str, Any]
    sample_sizes: Dict[str, int]


class ExperimentAnalyzer:
    """Analyzes A/B experiments with deterministic statistical methods."""
    
    def __init__(self, session: Session):
        self.session = session
        self.min_sample_size = settings.experiment_min_sample_size
        self.significance_level = settings.experiment_significance_level
        self.correction_method = settings.experiment_multiple_comparison_correction
    
    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get experiment by ID."""
        return self.session.get(Experiment, experiment_id)
    
    def get_experiment_assignments(self, experiment_id: str) -> List[ExperimentAssignment]:
        """Get all assignments for an experiment."""
        return self.session.execute(
            select(ExperimentAssignment).where(
                ExperimentAssignment.experiment_id == experiment_id
            )
        ).scalars().all()
    
    def prepare_experiment_data(
        self,
        experiment_id: str,
        metric: str,
        metric_type: Literal["proportion", "mean", "ratio"],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ExperimentData:
        """Prepare experiment data for analysis."""
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        assignments = self.get_experiment_assignments(experiment_id)
        
        # Split into control and treatment
        control_users = [a.user_id for a in assignments if a.variant == experiment.control_variant]
        treatment_users = [a.user_id for a in assignments if a.variant == experiment.treatment_variant]
        
        # Build date filters
        date_filters = []
        if start_date:
            date_filters.append(Event.timestamp >= start_date)
        if end_date:
            date_filters.append(Event.timestamp <= end_date)
        
        if metric_type == "proportion":
            return self._prepare_proportion_data(
                experiment, metric, control_users, treatment_users, date_filters
            )
        elif metric_type == "mean":
            return self._prepare_mean_data(
                experiment, metric, control_users, treatment_users, date_filters
            )
        elif metric_type == "ratio":
            return self._prepare_ratio_data(
                experiment, metric, control_users, treatment_users, date_filters
            )
        else:
            raise ValueError(f"Unknown metric type: {metric_type}")
    
    def _prepare_proportion_data(
        self,
        experiment: Experiment,
        metric: str,
        control_users: List[str],
        treatment_users: List[str],
        date_filters: List,
    ) -> ExperimentData:
        """Prepare data for proportion test (conversion, retention)."""
        
        # Define event names for common metrics
        metric_events = {
            "conversion": ["purchase", "signup_complete", "trial_start"],
            "activation": ["onboarding_complete", "first_value_event"],
            "retention": ["return_visit", "session_start"],
        }
        
        target_events = metric_events.get(metric, [metric])
        
        # Get conversions for control
        control_query = (
            select(func.count(func.distinct(Event.user_id)))
            .where(Event.user_id.in_(control_users))
            .where(Event.event_name.in_(target_events))
        )
        for f in date_filters:
            control_query = control_query.where(f)
        
        control_conversions = self.session.execute(control_query).scalar() or 0
        
        # Get conversions for treatment
        treatment_query = (
            select(func.count(func.distinct(Event.user_id)))
            .where(Event.user_id.in_(treatment_users))
            .where(Event.event_name.in_(target_events))
        )
        for f in date_filters:
            treatment_query = treatment_query.where(f)
        
        treatment_conversions = self.session.execute(treatment_query).scalar() or 0
        
        return ExperimentData(
            experiment_id=str(experiment.id),
            experiment_name=experiment.name,
            metric=metric,
            metric_type="proportion",
            control_data={"conversions": control_conversions, "total": len(control_users)},
            treatment_data={"conversions": treatment_conversions, "total": len(treatment_users)},
            sample_sizes={"control": len(control_users), "treatment": len(treatment_users)},
        )
    
    def _prepare_mean_data(
        self,
        experiment: Experiment,
        metric: str,
        control_users: List[str],
        treatment_users: List[str],
        date_filters: List,
    ) -> ExperimentData:
        """Prepare data for mean test (revenue, duration)."""
        
        # Get numeric values for metric
        metric_values = {
            "revenue": lambda e: e.event_properties.get("price", 0),
            "session_duration": lambda e: e.event_properties.get("duration_seconds", 0),
            "arpu": lambda e: e.event_properties.get("revenue", 0),
        }
        
        value_extractor = metric_values.get(metric, lambda e: 0)
        
        # Get control values
        control_query = (
            select(Event.user_id, Event.event_properties)
            .where(Event.user_id.in_(control_users))
            .where(Event.event_name == "purchase")  # Revenue events
        )
        for f in date_filters:
            control_query = control_query.where(f)
        
        control_results = self.session.execute(control_query).all()
        control_values = [value_extractor(r[1]) for r in control_results if value_extractor(r[1]) > 0]
        
        # Get treatment values
        treatment_query = (
            select(Event.user_id, Event.event_properties)
            .where(Event.user_id.in_(treatment_users))
            .where(Event.event_name == "purchase")
        )
        for f in date_filters:
            treatment_query = treatment_query.where(f)
        
        treatment_results = self.session.execute(treatment_query).all()
        treatment_values = [value_extractor(r[1]) for r in treatment_results if value_extractor(r[1]) > 0]
        
        # If no revenue events, include zeros for all users
        if not control_values:
            control_values = [0] * len(control_users)
        if not treatment_values:
            treatment_values = [0] * len(treatment_users)
        
        return ExperimentData(
            experiment_id=str(experiment.id),
            experiment_name=experiment.name,
            metric=metric,
            metric_type="mean",
            control_data={"values": control_values},
            treatment_data={"values": treatment_values},
            sample_sizes={"control": len(control_users), "treatment": len(treatment_users)},
        )
    
    def _prepare_ratio_data(
        self,
        experiment: Experiment,
        metric: str,
        control_users: List[str],
        treatment_users: List[str],
        date_filters: List,
    ) -> ExperimentData:
        """Prepare data for ratio test (ARPU, revenue per user)."""
        
        # Total revenue for control
        control_revenue_query = (
            select(func.sum(Event.event_properties["price"].astext.cast(float)))
            .where(Event.user_id.in_(control_users))
            .where(Event.event_name == "purchase")
        )
        for f in date_filters:
            control_revenue_query = control_revenue_query.where(f)
        
        control_revenue = self.session.execute(control_revenue_query).scalar() or 0
        
        # Total revenue for treatment
        treatment_revenue_query = (
            select(func.sum(Event.event_properties["price"].astext.cast(float)))
            .where(Event.user_id.in_(treatment_users))
            .where(Event.event_name == "purchase")
        )
        for f in date_filters:
            treatment_revenue_query = treatment_revenue_query.where(f)
        
        treatment_revenue = self.session.execute(treatment_revenue_query).scalar() or 0
        
        return ExperimentData(
            experiment_id=str(experiment.id),
            experiment_name=experiment.name,
            metric=metric,
            metric_type="ratio",
            control_data={"numerator": float(control_revenue), "denominator": len(control_users)},
            treatment_data={"numerator": float(treatment_revenue), "denominator": len(treatment_users)},
            sample_sizes={"control": len(control_users), "treatment": len(treatment_users)},
        )
    
    def analyze(
        self,
        experiment_id: str,
        metric: str,
        metric_type: Literal["proportion", "mean", "ratio"] = "proportion",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        confidence_level: float = 0.95,
    ) -> Dict[str, Any]:
        """Analyze an experiment and return statistical results."""
        
        # Prepare data
        data = self.prepare_experiment_data(
            experiment_id, metric, metric_type, start_date, end_date
        )
        
        # Check sample sizes
        pre_warnings: List[str] = []
        if data.sample_sizes["control"] < self.min_sample_size:
            pre_warnings.append(
                f"Control group below recommended size: {data.sample_sizes['control']} < {self.min_sample_size}"
            )

        if data.sample_sizes["treatment"] < self.min_sample_size:
            pre_warnings.append(
                f"Treatment group below recommended size: {data.sample_sizes['treatment']} < {self.min_sample_size}"
            )
        
        # Run analysis
        result = analyze_experiment(
            control_data=data.control_data,
            treatment_data=data.treatment_data,
            metric_type=data.metric_type,
            metric_name=data.metric,
            confidence_level=0.95,
            multiple_comparison_correction=self.correction_method,
        )
        
        # Add power analysis
        achieved_power = power_analysis(
            data.control_data, data.treatment_data, data.metric_type
        )
        
        # Format result
        formatted = {
            "experiment_id": str(experiment_id),
            "experiment_name": data.experiment_name,
            "metric": data.metric,
            "metric_type": data.metric_type,
            "sample_sizes": data.sample_sizes,
            "control": {
                "sample_size": data.sample_sizes["control"],
                **data.control_data,
            },
            "treatment": {
                "sample_size": data.sample_sizes["treatment"],
                **data.treatment_data,
            },
            "effect_size": result.effect_size,
            "effect_size_ci": result.effect_size_ci,
            "p_value": result.p_value,
            "statistically_significant": result.statistically_significant,
            "confidence_level": result.confidence_level,
            "test_used": result.test_used,
            "interpretation": result.interpretation,
            "assumptions_met": result.assumptions_met,
            "warnings": result.warnings,
            "achieved_power": achieved_power,
            "analyzed_at": datetime.utcnow().isoformat(),
        }

        if pre_warnings:
            formatted["warnings"] = pre_warnings + formatted.get("warnings", [])

        return formatted
    
    def analyze_multiple_metrics(
        self,
        experiment_id: str,
        metrics: List[Dict[str, Any]],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Analyze multiple metrics for an experiment with correction."""
        
        results = []
        p_values = []
        
        for metric_config in metrics:
            metric = metric_config["metric"]
            metric_type = metric_config.get("metric_type", "proportion")
            
            result = self.analyze(
                experiment_id=experiment_id,
                metric=metric,
                metric_type=metric_type,
                start_date=start_date,
                end_date=end_date,
            )
            
            if "error" not in result:
                p_values.append(result["p_value"])
            results.append(result)
        
        # Apply multiple comparison correction
        if len(p_values) > 1:
            from agents.experiment_agent.statistics import apply_multiple_comparison_correction
            rejected, corrected_p = apply_multiple_comparison_correction(
                p_values, method=self.correction_method, alpha=0.05
            )
            
            for i, result in enumerate(results):
                if "p_value" in result:
                    result["p_value_corrected"] = corrected_p[i]
                    result["significant_after_correction"] = rejected[i]
        
        return results
    
    def calculate_required_sample_size(
        self,
        baseline_rate: float,
        min_effect: float,
        alpha: float = 0.05,
        power: float = 0.8,
    ) -> int:
        """Calculate required sample size for an experiment."""
        return calculate_sample_size(baseline_rate, min_effect, alpha=alpha, power=power)
    
    def get_recommended_metrics(self, experiment: Experiment) -> List[Dict[str, Any]]:
        """Get recommended metrics to analyze based on experiment type."""
        # Default metrics based on experiment target
        base_metrics = [
            {"metric": "conversion", "metric_type": "proportion"},
            {"metric": "activation", "metric_type": "proportion"},
            {"metric": "retention", "metric_type": "proportion"},
            {"metric": "revenue", "metric_type": "mean"},
            {"metric": "arpu", "metric_type": "ratio"},
        ]
        
        # Customize based on target metric
        if experiment.target_metric:
            # Move target metric to front
            base_metrics.sort(key=lambda x: x["metric"] != experiment.target_metric)
        
        return base_metrics


def analyze_experiment_simple(
    session: Session,
    experiment_id: str,
    metric: str = "conversion",
    metric_type: Literal["proportion", "mean", "ratio"] = "proportion",
) -> Dict[str, Any]:
    """Simple interface for experiment analysis."""
    analyzer = ExperimentAnalyzer(session)
    return analyzer.analyze(experiment_id, metric, metric_type)
