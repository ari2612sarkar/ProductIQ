# Project Decisions

This document explains the main engineering choices in this repository.

## 1) Scope Choice

This project targets portfolio credibility for entry-level backend/data roles:

- clear data flow
- practical API design
- testable components
- visible limitations

It is intentionally not positioned as a fully autonomous production platform.

## 2) Data Choice (Real + Derived)

The project uses real public datasets as source material:

- e-commerce events (HuggingFace)
- Upworthy experiment archive (OSF)

To make cross-module demos possible, some layers are derived:

- generated user identities
- transformed/shifted timestamps for recent windows
- synthetic linkage between independent datasets

Tradeoff: better end-to-end demo flow, but lower external validity for business conclusions.

## 3) Why Deterministic Experiment Stats

Experiment hypothesis testing is implemented with SciPy/StatsModels, not LLM math.

Reason:

- reproducible outputs
- auditable methodology
- better signal for engineering interviews

## 4) SQL Safety Design

SQL execution is constrained by:

- parser validation
- forbidden keyword checks
- read-only DB access path
- join/subquery complexity limits

Reason: safer investigation tooling and easier risk discussion during review.

## 5) Frontend Design Choice

Frontend prioritizes observability and status over pixel polish:

- health/state visibility
- warnings for low statistical power
- explicit analysis source labels

Reason: make backend behavior inspectable and reduce ambiguity.

## 6) Current Limits / Next Steps

Current limits:

- incomplete worker orchestration for full autonomous loops
- sample-size sensitivity on experiment analysis
- date-window drift without ongoing ingest automation

Next steps:

1. add scheduled data refresh pipeline
2. improve experiment assignment realism
3. add integration tests for API + UI critical flows
