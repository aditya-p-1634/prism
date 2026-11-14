# PRISM Phase 6 — Frontend Snapshot Safety

## Scope

Phase 6 hardens the Next.js operator interface around the backend snapshot and
readiness contracts. It does not duplicate decision logic in the browser.

## Implemented

- Added a frontend API wrapper for `/health/readiness`.
- Snapshot context now tracks readiness separately from liveness/telemetry.
- Unknown fallback snapshots are no longer treated as immutable by default.
- Baseline detection uses snapshot type as well as the canonical baseline ID.
- Authority override submission is disabled on the immutable baseline and gives
  an explicit operator message.
- The command shell displays backend readiness status alongside E1–E6 health.
- Existing API errors and backend safety gates remain authoritative.

## Verification

- TypeScript compilation: passed.
- Next.js production build: passed for all 15 routes.

## Safety boundary

The UI is a presentation and control layer. It cannot make baseline state
mutable, bypass authority validation, or infer scenario state. Every mutating
operation remains enforced by the backend.

## Completion

**100% of the defined Phase 6 frontend snapshot-safety scope is implemented.**
