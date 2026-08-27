# EXPERIMENTATION.md

## Experimentation Guide

This document describes the experimentation framework, statistical tests, and best practices for A/B testing in the Autonomous Product Intelligence & Decision Engine.

---

## Overview

The experimentation module provides deterministic statistical analysis for A/B tests. All statistical calculations are performed using SciPy and statsmodels - **no LLM-based mathematical calculations**.

---

## Supported Experiment Types

### 1. Proportion Tests (Binary Metrics)
- **Conversion Rate**: Purchase, signup, trial start
- **Retention**: D1, D7, D30 retention
- **Activation**: Onboarding completion, first value event
- **Binary Outcomes**: Any yes/no metric

**Statistical Test**: Two-proportion Z-test (statsmodels)

### 2. Mean Tests (Continuous Metrics)
- **Revenue**: ARPU, average order value
- **Engagement**: Session duration, pages per session
- **Performance**: Page load time, API latency

**Statistical Test**: Welch's t-test (SciPy) - doesn't assume equal variances

### 3. Ratio Tests (Rate Metrics)
- **ARPU**: Revenue per user
- **Revenue per Session**: Revenue / sessions
- **Conversion per User**: Conversions / users

**Statistical Test**: Delta method (statsmodels)

---

## Statistical Test Selection Guide

| Metric Type | Example Metrics | Test | Library |
|-------------|----------------|------|---------|
| Proportion | Conversion, Retention, Activation | Two-proportion Z-test | statsmodels |
| Mean (Normal) | Revenue, Session Duration | Welch's t-test | SciPy |
| Mean (Non-normal) | Revenue (skewed) | Mann-Whitney U | SciPy |
| Ratio | ARPU, Revenue/User | Delta method | statsmodels |
| Count | Events per User | Poisson test | statsmodels |

---

## Experiment Analysis Workflow

### 1. Define Experiment
```python
experiment = {
    "name": "Onboarding V3",
    "hypothesis": "New onboarding flow increases activation",
    "control_variant": "original",
    "treatment_variant": "v3",
    "target_metric": "activation",
    "metric_type": "proportion",
    "minimum_detectable_effect": 0.05,  # 5% relative lift
    "traffic_allocation": 0.5
}
```

### 2. Prepare Data
The analyzer automatically:
- Retrieves experiment assignments
- Identifies control/treatment users
- Extracts metric events within experiment period
- Handles missing data

### 3. Run Analysis
```python
from agents.experiment_agent.analyzer import ExperimentAnalyzer

analyzer = ExperimentAnalyzer(session)
result = analyzer.analyze(
    experiment_id="exp-123",
    metric="activation",
    metric_type="proportion",
    start_date=experiment_start,
    end_date=experiment_end,
    confidence_level=0.95
)
```

### 4. Interpret Results
The analyzer returns:
- **Effect Size**: Magnitude of difference
- **Confidence Interval**: Range of true effect
- **P-value**: Statistical significance
- **Power**: Probability of detecting effect
- **Interpretation**: Plain English summary

---

## Statistical Assumptions & Validation

### Proportion Tests (Z-test)
**Assumptions**:
1. Independent samples
2. Random assignment
3. Sample size: np ≥ 5 and n(1-p) ≥ 5 for both groups
4. Binary outcomes

**Validation**: Automatic check of expected cell counts

### Mean Tests (t-test)
**Assumptions**:
1. Independent samples
2. Random assignment
3. Approximately normal distribution (or large n)
3. Welch's test: No equal variance assumption

**Validation**: 
- Shapiro-Wilk for normality (n < 50)
- Levene's test for equal variances
- Sample size warnings

### Ratio Tests (Delta Method)
**Assumptions**:
1. Large sample sizes
2. Independent numerator/denominator
3. Denominator not near zero

---

## Multiple Comparison Correction

When testing multiple metrics, apply correction:

### Methods Available
| Method | Use Case | Power |
|--------|----------|-------|
| Bonferroni | Few comparisons, strict control | Low |
| Benjamini-Hochberg | Many metrics, FDR control | Higher |
| Holm-Bonferroni | Step-down, more power than Bonferroni | Medium |

**Default**: Benjamini-Hochberg (FDR = 0.05)

```python
result = analyzer.analyze_multiple_metrics(
    experiment_id="exp-123",
    metrics=[
        {"metric": "conversion", "metric_type": "proportion"},
        {"metric": "retention", "metric_type": "proportion"},
        {"metric": "revenue", "metric_type": "mean"},
    ],
    multiple_comparison_correction="benjamini-hochberg"
)
```

---

## Power Analysis

### Pre-Experiment Sample Size
```python
from agents.experiment_agent.statistics import calculate_sample_size

n = calculate_sample_size(
    baseline_rate=0.10,           # 10% baseline conversion
    minimum_detectable_effect=0.10, # 10% relative lift
    alpha=0.05,                   # Significance level
    power=0.80,                   # 80% power
    ratio=1.0                     # Equal group sizes
)
# Returns: n per group
```

### Post-Experiment Power
```python
power = power_analysis(
    control_data={"conversions": 100, "total": 1000},
    treatment_data={"conversions": 120, "total": 1000},
    metric_type="proportion",
    alpha=0.05
)
# Returns achieved power (0-1)
```

---

## Sequential Testing (Optional)

For continuous monitoring:
```python
result = sequential_test(
    control_conversions=100,
    control_total=1000,
    treatment_conversions=120,
    treatment_total=1000,
    alpha=0.05,
    beta=0.2
)
# Returns: continue / reject_null / accept_null
```

---

## Experiment Result Interpretation

### Result Fields
| Field | Description |
|-------|-------------|
| `effect_size` | Standardized magnitude (Cohen's d, Cohen's h) |
| `effect_size_ci` | 95% CI for effect size |
| `p_value` | Two-sided p-value |
| `statistically_significant` | p < alpha |
| `confidence_level` | 0.95 default |
| `test_used` | "Two-proportion Z-test" etc. |
| `interpretation` | Plain English summary |
| `assumptions_met` | Boolean |
| `warnings` | List of assumption violations |
| `achieved_power` | Post-hoc power |

### Effect Size Guidelines (Cohen's d)
| Effect Size | Interpretation |
|-------------|----------------|
| 0.2 | Small |
| 0.5 | Medium |
| 0.8 | Large |

### Effect Size Guidelines (Cohen's h for proportions)
| Effect Size | Interpretation |
|-------------|----------------|
| 0.2 | Small |
| 0.5 | Medium |
| 0.8 | Large |

---

## Common Pitfalls

### 1. Peeking at Results
**Problem**: Checking results early inflates Type I error
**Solution**: Use sequential testing or pre-register analysis plan

### 2. Underpowered Experiments
**Problem**: Too small sample to detect realistic effects
**Solution**: Run power analysis before launch

### 3. Multiple Metrics Without Correction
**Problem**: Inflated false positive rate
**Solution**: Apply multiple comparison correction

### 4. Violation of Assumptions
**Problem**: Non-normal data, unequal variances
**Solution**: Use robust tests (Welch's t-test, Mann-Whitney)

### 5. Novelty/Priming Effects
**Problem**: Early users behave differently
**Solution**: Exclude first week, monitor stability

### 6. Sample Ratio Mismatch (SRM)
**Problem**: Uneven traffic allocation
**Solution**: Monitor assignment ratios, alert on deviation > 1%

---

## Best Practices

### Experiment Design
1. **Pre-register**: Define hypothesis, metrics, sample size before launch
2. **Randomization**: Use consistent hashing for assignment
3. **Stratification**: Balance on key covariates (plan, geography)
4. **Minimum Duration**: Run at least 1-2 business cycles

### Analysis
1. **Intention-to-Treat (ITT)**: Analyze by assigned group
2. **Per-Protocol**: Secondary analysis for compliance
3. **Subgroup Analysis**: Pre-specify, adjust for multiplicity
4. **Sensitivity**: Test robustness to outliers

### Reporting
1. **Effect Size + CI**: Always report, not just p-values
2. **Absolute + Relative**: Both perspectives
3. **Assumptions**: Report checks and violations
3. **Power**: Report achieved power
4. **Limitations**: Acknowledge constraints

---

## Integration with Agents

### Experiment Agent
The `ExperimentAgent` automates:
1. Experiment discovery (relevant experiments for question)
2. Data preparation (assignments + outcomes)
3. Statistical analysis (deterministic)
4. Interpretation (LLM-based natural language)
5. Evidence generation (for root cause agent)

### Usage in Investigations
```python
# In orchestrator workflow
experiment_result = run_experiment_investigation(
    question="Why did conversion drop?",
    experiment_id="onboarding-v3",
    metric="conversion"
)
# Returns evidence for root cause agent
```

---

## Configuration

### Environment Variables
```env
EXPERIMENT_MIN_SAMPLE_SIZE=100
EXPERIMENT_SIGNIFICANCE_LEVEL=0.05
EXPERIMENT_MULTIPLE_COMPARISON_CORRECTION=benjamini-hochberg
```

### Agent Configuration
```python
# In config/settings.py
experiment_min_sample_size: int = 100
experiment_significance_level: float = 0.05
experiment_multiple_comparison_correction: str = "benjamini-hochberg"
```