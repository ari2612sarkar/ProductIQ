# Autonomous Product Intelligence & Decision Engine

> An agentic AI system that autonomously investigates product performance, identifies root causes, analyzes customer feedback and experiments, and produces evidence-backed product decisions.

## Overview

Modern product teams collect product telemetry, customer feedback, support tickets, revenue data, and experimentation results. The difficult part is turning this information into reliable product decisions.

This project builds an **Agentic Product Intelligence & Decision Engine** capable of performing multi-step product investigations.

Instead of simply answering questions, the system can:

- Detect abnormal product metrics
- Investigate anomalies using SQL
- Analyze cohorts and funnels
- Retrieve relevant customer feedback
- Investigate experiments
- Identify probable root causes
- Quantify business impact
- Prioritize potential product actions
- Generate evidence-backed recommendations

The goal is to simulate an internal **AI Product Analyst / Product Intelligence team**.

---

## Core Problem

A traditional analytics workflow looks like:

```text
Product Manager
      ↓
Dashboard
      ↓
Find anomaly
      ↓
Ask Data Analyst
      ↓
Write SQL
      ↓
Analyze feedback
      ↓
Check experiments
      ↓
Form hypothesis
      ↓
Make decision
```

This system automates the investigation loop:

```text
                 Product Data
                      │
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
     Events       Customer Data   Feedback
        │             │             │
        └─────────────┼─────────────┘
                      ↓
                Metric Engine
                      ↓
              Anomaly Detection
                      ↓
             Investigation Agent
                 /    |     \
                ↓     ↓      ↓
              SQL    RAG   Experiments
                \     |      /
                 \    |     /
                  ↓   ↓    ↓
                 Root Cause
                      ↓
               Decision Engine
                      ↓
            Product Recommendation
```

## Key Capabilities

### 1. Product Health Monitoring

Tracks:

- DAU / WAU / MAU
- Activation
- Retention
- Churn
- Conversion
- Revenue
- ARPU
- Feature adoption
- Customer health

### 2. Autonomous SQL Investigation

The SQL Agent can:

1. Understand the business question
2. Retrieve relevant database schema
3. Identify required metrics
4. Generate SQL
5. Validate the query
6. Execute read-only SQL
7. Analyze results
8. Continue the investigation when necessary

Example:

```text
Why did retention fall this month?
              ↓
Check overall retention
              ↓
Segment by plan
              ↓
Segment by acquisition channel
              ↓
Analyze signup cohorts
              ↓
Analyze onboarding completion
              ↓
Identify affected segment
```

### 3. Customer Feedback Intelligence

The system processes:

- Support tickets
- Product reviews
- Feature requests
- NPS responses
- User feedback

The RAG agent retrieves evidence related to identified product problems.

### 4. Experiment Analysis

The system can investigate A/B tests:

```text
Hypothesis
    ↓
Experiment
    ↓
Control vs Treatment
    ↓
Statistical Analysis
    ↓
Confidence / Significance
    ↓
Product Decision
```

Statistical calculations are performed with deterministic statistical tooling rather than asking the LLM to perform the mathematics.

### 5. Product Prioritization

Potential product actions are evaluated using:

- Impact
- Reach
- Confidence
- Effort
- Revenue impact
- Strategic alignment
- Risk

Example:

```text
Feature: Bulk Export

Reach:          42,000 users
Impact:         2.8
Confidence:     86%
Engineering:    13 engineer-weeks

Priority:       P1
```

---

## Agent Architecture

```text
                    Orchestrator
                         │
          ┌──────────────┼──────────────┐
          ↓              ↓              ↓
     SQL Agent      Feedback Agent   Experiment Agent
          │              │              │
          ↓              ↓              ↓
     PostgreSQL         Vector DB      Experiment DB
          │              │              │
          └──────────────┼──────────────┘
                         ↓
                  Root Cause Agent
                         ↓
                  Decision Agent
                         ↓
              Product Recommendation
```

---

## Technology Stack

### Backend

- Python
- FastAPI
- PostgreSQL
- Redis

### Agentic AI

- LangGraph
- LLM
- Tool Calling
- Structured Outputs

### Retrieval

- Embeddings
- Vector Database
- RAG

### Analytics

- SQL
- Pandas
- NumPy
- SciPy

### Observability

- OpenTelemetry
- Prometheus
- Grafana

### Engineering

- Docker
- pytest
- GitHub Actions

---

## Evaluation

### SQL Evaluation

Measures:

- SQL correctness
- Execution success
- Metric correctness
- Schema grounding
- Read-only safety

### RAG Evaluation

Measures:

- Retrieval relevance
- Context precision
- Context recall
- Answer faithfulness

### Agent Evaluation

Measures:

- Tool selection
- Investigation completion
- Root-cause accuracy
- Decision quality
- Hallucination rate

---

## Example Investigation

```text
ALERT

30-day retention decreased:

32.4% → 27.1%

Change:
-5.3 percentage points
```

The system investigates:

```text
Step 1
Identify affected cohorts

Step 2
Segment by subscription plan

Step 3
Analyze onboarding completion

Step 4
Inspect recent experiments

Step 5
Retrieve related support tickets

Step 6
Compare evidence

Step 7
Generate root-cause hypothesis
```

Example output:

```text
ROOT CAUSE

The onboarding V3 experiment is strongly associated
with the retention decline among newly registered users.

Evidence:
✓ Cohort retention analysis
✓ Activation funnel analysis
✓ Experiment statistics
✓ Customer feedback

Confidence:
0.91

Recommendation:
Roll back onboarding V3 and re-run the experiment
with a corrected onboarding flow.
```

---

## Suggested Repository Structure

```text
product-intelligence/
├── agents/
│   ├── investigator/
│   ├── sql_agent/
│   ├── feedback_agent/
│   ├── experiment_agent/
│   └── decision_agent/
├── analytics/
│   ├── cohorts/
│   ├── funnels/
│   ├── retention/
│   └── metrics/
├── db/
│   ├── schema/
│   ├── migrations/
│   └── seeds/
├── evaluation/
│   ├── agent_eval/
│   ├── sql_eval/
│   └── retrieval_eval/
├── api/
├── tests/
├── observability/
├── docker/
├── docs/
└── README.md
```

## Project Goals

- Build production-oriented agentic workflows
- Demonstrate SQL + AI integration
- Implement reliable tool-calling agents
- Ground decisions in measurable evidence
- Evaluate agent behavior systematically
- Separate deterministic computation from LLM reasoning
- Build an end-to-end AI product intelligence system

## Future Improvements

- Real-time event ingestion
- Automated experiment creation
- Predictive churn modeling
- Natural-language product planning
- Slack / Teams integration
- Automated Jira ticket creation
- Multi-tenant architecture
- Human-in-the-loop approval workflows

---

## Author

**Aritra Sarkar**

AI/ML • Agentic AI • Data Analytics • Backend Engineering
