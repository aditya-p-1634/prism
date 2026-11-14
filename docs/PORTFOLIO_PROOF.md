# PRISM Portfolio Proof

## One-line description

PRISM is a human-supervised disaster decision-support platform that converts
hazard evidence into explainable, capacity-constrained relocation plans and
time-aware evacuation simulations.

## Evidence a reviewer can verify

- FastAPI backend with E1–E6 modular engine boundaries.
- Next.js operator console with a focused Operator Briefing workflow.
- NetworkX routing and OR-Tools CP-SAT allocation.
- Snapshot immutability and explicit unmet-demand safeguards.
- Chronological, leakage-safe ML validation with baseline comparisons.
- Route validity windows and explicit assisted-evacuation demand.
- Provenance-preserving field observations and conflict reconciliation.
- Focused regression tests and CI checks.
- Docker Compose reproducible demonstration deployment.

## Real-data research evidence (bounded)

- Phase 14 audits the repository's supplied telemetry, DEM, KML, and report assets with hashes and explicit provenance limitations.
- Phase 15 normalizes the supplied Nandambakkam telemetry to UTC without changing raw source files.
- Phase 16 benchmarks persistence, trend, and Ridge on the irregular historical stage series. Ridge has the best RMSE (2.0925), while persistence has the best MAE (0.3425); the validation-derived interval covers 65.95% of the held-out test observations and is therefore **not calibrated**.
- Phase 17 records that the available 2015 spatial event layers cannot be temporally joined to telemetry beginning in 2021. They remain contextual reference evidence, not flood labels.
- Phase 18 exposes this evidence in the operator workflow as read-only and `NON-OPERATIONAL`.

## Honest limitations

The demonstration uses synthetic Vayu Basin data. The ML model is not claimed
to be operationally accurate, the physics layer is not a validated hydraulic
solver, and rescue dispatch is not implemented. Those are deliberate safety
boundaries, not hidden capabilities.

The supplied historical telemetry and spatial assets strengthen the research
prototype, but do not remove those boundaries: licensing, gauge datum,
temporally aligned rainfall/discharge, calibrated hydraulic parameters, and
operational live-feed access remain unverified.

## Suggested demonstration path

1. Start the Compose demo.
2. Open Operator Briefing.
3. Review current hazard, evidence warnings, priority groups, and next actions.
4. Inspect capacity and route constraints.
5. Run the synthetic monsoon scenario.
6. Open simulation and observe route invalidation/replanning.
7. Review the audit trail and explain what remains human-controlled.
