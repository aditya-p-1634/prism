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

## Honest limitations

The demonstration uses synthetic Vayu Basin data. The ML model is not claimed
to be operationally accurate, the physics layer is not a validated hydraulic
solver, and rescue dispatch is not implemented. Those are deliberate safety
boundaries, not hidden capabilities.

## Suggested demonstration path

1. Start the Compose demo.
2. Open Operator Briefing.
3. Review current hazard, evidence warnings, priority groups, and next actions.
4. Inspect capacity and route constraints.
5. Run the synthetic monsoon scenario.
6. Open simulation and observe route invalidation/replanning.
7. Review the audit trail and explain what remains human-controlled.
