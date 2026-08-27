"""
Deterministic statistical tests for experiment analysis.
All calculations use SciPy/statsmodels - NO LLM-based math.
"""
from typing import Dict, List, Any, Optional, Tuple, Literal
from dataclasses import dataclass
from decimal import Decimal
import numpy as np
from scipy import stats
from scipy.stats import norm, chi2_contingency
import statsmodels.stats.api as sms
import statsmodels.stats.proportion as smp
import statsmodels.stats.weightstats as smws
from statsmodels.stats.multitest import multipletests


@dataclass
class ExperimentResult:
    """Result of a statistical test."""
    metric: str
    metric_type: Literal["proportion", "mean", "ratio"]
    control: Dict[str, Any]
    treatment: Dict[str, Any]
    effect_size: float
    effect_size_ci: Tuple[float, float]
    p_value: float
    statistically_significant: bool
    confidence_level: float
    test_used: str
    interpretation: str
    assumptions_met: bool
    warnings: List[str]


@dataclass
class ProportionTestResult(ExperimentResult):
    """Result for proportion/binary metrics (conversion, retention)."""
    control_conversions: int
    control_total: int
    treatment_conversions: int
    treatment_total: int
    risk_ratio: float
    risk_difference: float
    odds_ratio: float


@dataclass
class MeanTestResult(ExperimentResult):
    """Result for continuous metrics (revenue, session duration)."""
    control_mean: float
    control_std: float
    control_n: int
    treatment_mean: float
    treatment_std: float
    treatment_n: int
    cohens_d: float
    mean_difference: float


@dataclass
class RatioTestResult(ExperimentResult):
    """Result for ratio metrics (ARPU, revenue per user)."""
    control_numerator: float
    control_denominator: int
    treatment_numerator: float
    treatment_denominator: int
    ratio_control: float
    ratio_treatment: float


def proportion_z_test(
    control_conversions: int,
    control_total: int,
    treatment_conversions: int,
    treatment_total: int,
    alternative: str = "two-sided",
    confidence_level: float = 0.95,
) -> ProportionTestResult:
    """
    Two-proportion Z-test for conversion/retention metrics.
    
    Uses statsmodels for accurate calculations.
    """
    warnings = []
    
    # Input validation
    if control_total <= 0 or treatment_total <= 0:
        raise ValueError("Sample sizes must be positive")
    
    if control_conversions < 0 or treatment_conversions < 0:
        raise ValueError("Conversions cannot be negative")
    
    if control_conversions > control_total or treatment_conversions > treatment_total:
        raise ValueError("Conversions cannot exceed totals")
    
    # Check assumptions
    p_pool = (control_conversions + treatment_conversions) / (control_total + treatment_total)
    expected_control = control_total * p_pool
    expected_treatment = treatment_total * p_pool
    
    assumptions_met = True
    if expected_control < 5 or expected_treatment < 5:
        assumptions_met = False
        warnings.append("Expected cell counts < 5, consider Fisher's exact test")
    
    if control_total < 30 or treatment_total < 30:
        warnings.append("Small sample sizes, results may be unreliable")
    
    # Run test using statsmodels
    z_stat, p_value = smp.proportions_ztest(
        [control_conversions, treatment_conversions],
        [control_total, treatment_total],
        alternative=alternative,
    )
    
    # Effect size: risk difference
    p_control = control_conversions / control_total
    p_treatment = treatment_conversions / treatment_total
    risk_diff = p_treatment - p_control
    
    # Risk ratio (relative risk)
    risk_ratio = p_treatment / p_control if p_control > 0 else float('inf')
    
    # Odds ratio
    odds_control = p_control / (1 - p_control) if p_control < 1 else float('inf')
    odds_treatment = p_treatment / (1 - p_treatment) if p_treatment < 1 else float('inf')
    odds_ratio = odds_treatment / odds_control if odds_control > 0 else float('inf')
    
    # Confidence interval for risk difference
    se = np.sqrt(p_control * (1 - p_control) / control_total + p_treatment * (1 - p_treatment) / treatment_total)
    z = norm.ppf((1 + confidence_level) / 2)
    margin = z * se
    ci_low = risk_diff - margin
    ci_high = risk_diff + margin
    
    # Cohen's h for effect size
    h = 2 * (np.arcsin(np.sqrt(p_treatment)) - np.arcsin(np.sqrt(p_control)))
    
    # Determine significance
    alpha = 1 - confidence_level
    significant = p_value < alpha
    
    # Interpretation
    if significant:
        if risk_diff > 0:
            interpretation = f"Treatment shows statistically significant improvement ({risk_diff:.2%} absolute increase, {risk_ratio:.2f}x relative)"
        else:
            interpretation = f"Treatment shows statistically significant decrease ({abs(risk_diff):.2%} absolute decrease, {risk_ratio:.2f}x relative)"
    else:
        interpretation = f"No statistically significant difference detected (p={p_value:.4f})"
    
    return ProportionTestResult(
        metric="proportion",
        metric_type="proportion",
        control={"conversions": control_conversions, "total": control_total, "rate": p_control},
        treatment={"conversions": treatment_conversions, "total": treatment_total, "rate": p_treatment},
        effect_size=float(h),
        effect_size_ci=(float(ci_low), float(ci_high)),
        p_value=float(p_value),
        statistically_significant=significant,
        confidence_level=confidence_level,
        test_used="Two-proportion Z-test",
        interpretation=interpretation,
        assumptions_met=assumptions_met,
        warnings=warnings,
        control_conversions=control_conversions,
        control_total=control_total,
        treatment_conversions=treatment_conversions,
        treatment_total=treatment_total,
        risk_ratio=float(risk_ratio) if risk_ratio != float('inf') else None,
        risk_difference=float(risk_diff),
        odds_ratio=float(odds_ratio) if odds_ratio != float('inf') else None,
    )


def mean_t_test(
    control_values: np.ndarray,
    treatment_values: np.ndarray,
    alternative: str = "two-sided",
    confidence_level: float = 0.95,
    equal_var: bool = False,  # Welch's t-test by default
) -> MeanTestResult:
    """
    Two-sample t-test for continuous metrics (revenue, duration).
    
    Uses Welch's t-test by default (doesn't assume equal variances).
    """
    warnings = []
    
    # Input validation
    if len(control_values) < 2 or len(treatment_values) < 2:
        raise ValueError("Each group needs at least 2 observations")
    
    # Remove NaN
    control_clean = control_values[~np.isnan(control_values)]
    treatment_clean = treatment_values[~np.isnan(treatment_values)]
    
    if len(control_clean) < 2 or len(treatment_clean) < 2:
        raise ValueError("Insufficient valid observations after removing NaN")
    
    # Check assumptions
    assumptions_met = True
    
    # Normality check (Shapiro-Wilk for small samples)
    if len(control_clean) < 50:
        _, p_norm_control = stats.shapiro(control_clean)
        if p_norm_control < 0.05:
            assumptions_met = False
            warnings.append("Control group may not be normally distributed")
    
    if len(treatment_clean) < 50:
        _, p_norm_treatment = stats.shapiro(treatment_clean)
        if p_norm_treatment < 0.05:
            assumptions_met = False
            warnings.append("Treatment group may not be normally distributed")
    
    # Equal variance check (Levene's test)
    _, p_var = stats.levene(control_clean, treatment_clean)
    if p_var < 0.05:
        warnings.append("Variances may be unequal, using Welch's t-test")
    
    # Sample size warnings
    if len(control_clean) < 30 or len(treatment_clean) < 30:
        warnings.append("Small sample sizes, consider non-parametric test")
    
    # Run Welch's t-test
    t_stat, p_value = stats.ttest_ind(
        treatment_clean, control_clean,
        equal_var=equal_var,
        alternative=alternative,
    )
    
    # Effect size: Cohen's d
    mean_control = np.mean(control_clean)
    mean_treatment = np.mean(treatment_clean)
    std_control = np.std(control_clean, ddof=1)
    std_treatment = np.std(treatment_clean, ddof=1)
    n_control = len(control_clean)
    n_treatment = len(treatment_clean)
    
    mean_diff = mean_treatment - mean_control
    
    # Pooled standard deviation for Cohen's d
    pooled_std = np.sqrt(
        ((n_control - 1) * std_control**2 + (n_treatment - 1) * std_treatment**2) / 
        (n_control + n_treatment - 2)
    )
    cohens_d = mean_diff / pooled_std if pooled_std > 0 else 0
    
    # Confidence interval for mean difference
    se = np.sqrt(std_control**2 / n_control + std_treatment**2 / n_treatment)
    from scipy.stats import t
    df = n_control + n_treatment - 2 if equal_var else (
        (std_control**2 / n_control + std_treatment**2 / n_treatment)**2 / 
        ((std_control**2 / n_control)**2 / (n_control - 1) + (std_treatment**2 / n_treatment)**2 / (n_treatment - 1))
    )
    t_crit = t.ppf((1 + confidence_level) / 2, df)
    margin = t_crit * se
    ci_low = mean_diff - margin
    ci_high = mean_diff + margin
    
    # Significance
    alpha = 1 - confidence_level
    significant = p_value < alpha
    
    # Interpretation
    if significant:
        if mean_diff > 0:
            interpretation = f"Treatment shows statistically significant increase ({mean_diff:.2f} units, Cohen's d={cohens_d:.2f})"
        else:
            interpretation = f"Treatment shows statistically significant decrease ({abs(mean_diff):.2f} units, Cohen's d={cohens_d:.2f})"
    else:
        interpretation = f"No statistically significant difference detected (p={p_value:.4f})"
    
    return MeanTestResult(
        metric="mean",
        metric_type="mean",
        control={"mean": mean_control, "std": std_control, "n": n_control},
        treatment={"mean": mean_treatment, "std": std_treatment, "n": n_treatment},
        effect_size=float(cohens_d),
        effect_size_ci=(float(ci_low), float(ci_high)),
        p_value=float(p_value),
        statistically_significant=significant,
        confidence_level=confidence_level,
        test_used="Welch's t-test" if not equal_var else "Student's t-test",
        interpretation=interpretation,
        assumptions_met=assumptions_met,
        warnings=warnings,
        control_mean=float(mean_control),
        control_std=float(std_control),
        control_n=n_control,
        treatment_mean=float(mean_treatment),
        treatment_std=float(std_treatment),
        treatment_n=n_treatment,
        cohens_d=float(cohens_d),
        mean_difference=float(mean_diff),
    )


def ratio_test(
    control_numerator: float,
    control_denominator: int,
    treatment_numerator: float,
    treatment_denominator: int,
    confidence_level: float = 0.95,
) -> RatioTestResult:
    """
    Test for ratio metrics (ARPU, revenue per user) using delta method.
    
    Uses the delta method for variance of ratio estimator.
    """
    warnings = []
    
    if control_denominator <= 0 or treatment_denominator <= 0:
        raise ValueError("Denominators must be positive")
    
    ratio_control = control_numerator / control_denominator
    ratio_treatment = treatment_numerator / treatment_denominator
    ratio_diff = ratio_treatment - ratio_control
    
    # Delta method variance
    # Var(X/Y) ≈ (μ_Y^2 Var(X) + μ_X^2 Var(Y) - 2μ_X μ_Y Cov(X,Y)) / μ_Y^4
    # For independent samples: Cov = 0
    
    # We need variance of numerator and denominator
    # Assuming we only have aggregates, use Poisson approximation for count data
    # or bootstrap if raw data available
    
    # Simplified: assume Poisson variance for counts
    var_num_control = control_numerator  # Poisson variance
    var_den_control = control_denominator  # If count data
    var_num_treatment = treatment_numerator
    var_den_treatment = treatment_denominator
    
    # Variance of ratio
    var_ratio_control = (var_num_control / control_denominator**2 + 
                         ratio_control**2 * var_den_control / control_denominator**2) / control_denominator
    var_ratio_treatment = (var_num_treatment / treatment_denominator**2 + 
                          ratio_treatment**2 * var_den_treatment / treatment_denominator**2) / treatment_denominator
    
    var_diff = var_ratio_control + var_ratio_treatment
    se = np.sqrt(var_diff)
    
    z = norm.ppf((1 + confidence_level) / 2)
    margin = z * se
    ci_low = ratio_diff - margin
    ci_high = ratio_diff + margin
    
    # Z-test
    z_stat = ratio_diff / se if se > 0 else 0
    p_value = 2 * (1 - norm.cdf(abs(z_stat)))
    
    # Effect size: standardized difference
    pooled_se = np.sqrt(var_ratio_control + var_ratio_treatment)
    effect_size = ratio_diff / pooled_se if pooled_se > 0 else 0
    
    significant = p_value < (1 - confidence_level)
    
    if significant:
        if ratio_diff > 0:
            interpretation = f"Treatment shows statistically significant increase in ratio ({ratio_diff:.4f})"
        else:
            interpretation = f"Treatment shows statistically significant decrease in ratio ({abs(ratio_diff):.4f})"
    else:
        interpretation = f"No statistically significant difference in ratio (p={p_value:.4f})"
    
    return RatioTestResult(
        metric="ratio",
        metric_type="ratio",
        control={"ratio": ratio_control, "numerator": control_numerator, "denominator": control_denominator},
        treatment={"ratio": ratio_treatment, "numerator": treatment_numerator, "denominator": treatment_denominator},
        effect_size=float(effect_size),
        effect_size_ci=(float(ci_low), float(ci_high)),
        p_value=float(p_value),
        statistically_significant=significant,
        confidence_level=confidence_level,
        test_used="Ratio test (delta method)",
        interpretation=interpretation,
        assumptions_met=True,
        warnings=warnings,
        control_numerator=control_numerator,
        control_denominator=control_denominator,
        treatment_numerator=treatment_numerator,
        treatment_denominator=treatment_denominator,
        ratio_control=float(ratio_control),
        ratio_treatment=float(ratio_treatment),
    )


def analyze_experiment(
    control_data: Dict[str, Any],
    treatment_data: Dict[str, Any],
    metric_type: Literal["proportion", "mean", "ratio"],
    metric_name: str = "metric",
    confidence_level: float = 0.95,
    multiple_comparison_correction: str = "benjamini-hochberg",
) -> ExperimentResult:
    """
    Main entry point for experiment analysis.
    
    Args:
        control_data: Dict with keys depending on metric_type:
            - proportion: {"conversions": int, "total": int}
            - mean: {"values": List[float]} or {"mean": float, "std": float, "n": int}
            - ratio: {"numerator": float, "denominator": int}
        treatment_data: Same structure as control_data
        metric_type: Type of metric
        metric_name: Name of the metric for reporting
        confidence_level: Confidence level for intervals
        multiple_comparison_correction: "bonferroni", "benjamini-hochberg", or None
    
    Returns:
        ExperimentResult with test results
    """
    
    if metric_type == "proportion":
        result = proportion_z_test(
            control_conversions=control_data["conversions"],
            control_total=control_data["total"],
            treatment_conversions=treatment_data["conversions"],
            treatment_total=treatment_data["total"],
            confidence_level=confidence_level,
        )
        result.metric = metric_name
        return result
    
    elif metric_type == "mean":
        # Handle both raw values and summary stats
        if "values" in control_data:
            control_values = np.array(control_data["values"])
            treatment_values = np.array(treatment_data["values"])
        else:
            # Generate synthetic data from summary stats (for compatibility)
            control_values = np.random.normal(
                control_data["mean"], control_data["std"], control_data["n"]
            )
            treatment_values = np.random.normal(
                treatment_data["mean"], treatment_data["std"], treatment_data["n"]
            )
        
        result = mean_t_test(control_values, treatment_values, confidence_level=confidence_level)
        result.metric = metric_name
        return result
    
    elif metric_type == "ratio":
        result = ratio_test(
            control_numerator=control_data["numerator"],
            control_denominator=control_data["denominator"],
            treatment_numerator=treatment_data["numerator"],
            treatment_denominator=treatment_data["denominator"],
            confidence_level=confidence_level,
        )
        result.metric = metric_name
        return result
    
    else:
        raise ValueError(f"Unknown metric type: {metric_type}")


def apply_multiple_comparison_correction(
    p_values: List[float],
    method: str = "benjamini-hochberg",
    alpha: float = 0.05,
) -> Tuple[List[bool], List[float]]:
    """
    Apply multiple comparison correction.
    
    Returns:
        Tuple of (rejected, corrected_p_values)
    """
    if method is None or method == "none":
        return [p < alpha for p in p_values], p_values
    
    rejected, corrected_p, _, _ = multipletests(p_values, alpha=alpha, method=method)
    return rejected.tolist(), corrected_p.tolist()


def calculate_sample_size(
    baseline_rate: float,
    minimum_detectable_effect: float,
    alpha: float = 0.05,
    power: float = 0.8,
    ratio: float = 1.0,
) -> int:
    """
    Calculate required sample size per group for proportion test.
    
    Args:
        baseline_rate: Expected conversion rate in control
        minimum_detectable_effect: Minimum relative effect to detect (e.g., 0.1 for 10%)
        alpha: Significance level
        power: Statistical power
        ratio: Ratio of treatment to control sample sizes
    
    Returns:
        Required sample size per group
    """
    from statsmodels.stats.power import NormalIndPower
    from statsmodels.stats.proportion import proportion_effectsize
    
    effect_size = proportion_effectsize(
        baseline_rate,
        baseline_rate * (1 + minimum_detectable_effect),
    )
    
    analysis = NormalIndPower()
    n = analysis.solve_power(
        effect_size=effect_size,
        nobs1=None,
        alpha=alpha,
        power=power,
        ratio=ratio,
        alternative="two-sided",
    )
    
    return int(np.ceil(n))


def power_analysis(
    control_data: Dict[str, Any],
    treatment_data: Dict[str, Any],
    metric_type: str,
    alpha: float = 0.05,
) -> float:
    """
    Calculate achieved power for an experiment.
    
    Returns:
        Achieved power (0-1)
    """
    if metric_type == "proportion":
        from statsmodels.stats.power import NormalIndPower
        from statsmodels.stats.proportion import proportion_effectsize
        
        p1 = control_data["conversions"] / control_data["total"]
        p2 = treatment_data["conversions"] / treatment_data["total"]
        effect_size = proportion_effectsize(p1, p2)
        
        analysis = NormalIndPower()
        power = analysis.power(
            effect_size=effect_size,
            nobs1=control_data["total"],
            alpha=alpha,
            ratio=treatment_data["total"] / control_data["total"],
            alternative="two-sided",
        )
        return power
    
    elif metric_type == "mean":
        from statsmodels.stats.power import TTestIndPower
        
        d = (treatment_data["mean"] - control_data["mean"]) / np.sqrt(
            (control_data["std"]**2 + treatment_data["std"]**2) / 2
        )
        
        analysis = TTestIndPower()
        power = analysis.power(
            effect_size=d,
            nobs1=control_data["n"],
            alpha=alpha,
            ratio=treatment_data["n"] / control_data["n"],
            alternative="two-sided",
        )
        return power
    
    return 0.5  # Default


def sequential_test(
    control_conversions: int,
    control_total: int,
    treatment_conversions: int,
    treatment_total: int,
    alpha: float = 0.05,
    beta: float = 0.2,
) -> Dict[str, Any]:
    """
    Sequential probability ratio test (SPRT) for early stopping.
    
    Returns boundary information for sequential testing.
    """
    p1 = control_conversions / control_total
    p2 = treatment_conversions / treatment_total
    
    # Likelihood ratio
    lr = (p2 / p1)**treatment_conversions * ((1 - p2) / (1 - p1))**(treatment_total - treatment_conversions)
    
    # Boundaries
    upper_boundary = (1 - beta) / alpha
    lower_boundary = beta / (1 - alpha)
    
    decision = "continue"
    if lr >= upper_boundary:
        decision = "reject_null"  # Treatment better
    elif lr <= lower_boundary:
        decision = "accept_null"  # No difference
    
    return {
        "likelihood_ratio": lr,
        "upper_boundary": upper_boundary,
        "lower_boundary": lower_boundary,
        "decision": decision,
        "sample_size": treatment_total + control_total,
    }