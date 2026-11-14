# PRISM Faculty Loophole Audit — Final Checklist

Source of requirements: the faculty-facing loophole and future-implementation
document supplied for PRISM review.

## L1 — Planned relocation treated as completed evacuation

**Status: PARTIALLY CLOSED.**

- Allocation plans and evacuation states are separate records.
- Notifications, movement, in-transit, arrival, sheltering, blocked, stuck,
  assistance, and no-response states exist.
- Allocations are not marked sheltered merely because CP-SAT assigned a
  destination.
- Simulation movement advances progress and only transitions to arrival after
  simulated travel time.

Remaining boundary: arrival is currently simulation-confirmed, not verified by
a field observation or authority confirmation. A real observe/verify feedback
layer is still required before claiming physical evacuation.

## L2 — Static rather than recurrent simulation

**Status: SUBSTANTIALLY CLOSED FOR THE PROTOTYPE.**

- Fixed simulation clock, timestep, duration, bounded tick count,
  pause/resume/cancel, replayable event history, hazard updates, movement,
  resource depletion, route invalidation, rerouting, and selective
  reallocation are implemented.
- Simulation branches are snapshot-scoped and failed scenario creation rolls
  back.

Remaining boundary: this is a deterministic discrete prototype, not a live
  continuously scheduled operational loop.

## L3 — Insufficient boundary and extreme-condition handling

**Status: HARDENED.**

- Zero-duration and zero hazard/resource changes are explicit valid cases.
- Timestep, duration, and max-step bounds are validated.
- Declared maximum rainfall delta, river-level delta, resource rates, and
  warning ratios are enforced.
- NaN, Inf, negative, malformed road lists, invalid resource multipliers, and
  impossible ranges are rejected explicitly.
- Prediction input ranges, physical floors/crests, rate limits, domain
  envelopes, and unsupported horizons are gated.
- Unmet demand and failed reroute states remain explicit.

## L4 — Missing rescue/mobility execution layer

**Status: OPEN / NOT IMPLEMENTED.**

The current system records `REQUIRES_ASSISTANCE` or `STUCK`, but does not yet
model rescue teams, vehicles, pickup points, dispatch capacity, special
capabilities, or rescue travel execution. It must not claim rescue dispatch
capability until those entities and workflows exist.

## L5 — Route safety not fully time-dependent

**Status: PARTIALLY CLOSED.**

- In-transit routes are rechecked every simulation step.
- New inundation and closures invalidate routes and trigger rerouting or
  explicit failure.
- Cross-snapshot route mixing is rejected.

Remaining boundary: route plans do not yet carry predicted edge validity
windows or arrival-time feasibility per edge. Future closure prediction is not
silently assumed.

## L6 — Household heterogeneity incompletely operationalized

**Status: PARTIALLY CLOSED.**

- Household vulnerability, mobility impairment, assistance requirement, group
  size, and special-transit flags influence priority and fallback behavior.
- Special-transit groups can escalate to assistance when rerouting fails.

Remaining boundary: self-evacuation, assisted evacuation, and rescue dispatch
are not yet separate operational movement models.

## L7 — Incomplete real-world state feedback

**Status: PARTIALLY CLOSED.**

- Validated hydrometric observations are ingested with timestamp, source,
  quality, freshness, and raw-reference provenance.
- Observation-driven E1 evaluation is snapshot-gated and audited.

Remaining boundary: verified household movement, road reports, shelter reports,
resource replenishment, and authority field confirmations are not yet a
unified feedback loop.

## L8 — Prediction realism and uncertainty

**Status: PROTOTYPE-HARDENED, NOT OPERATIONALLY VALIDATED.**

- Autoregressive Ridge, persistence, and linear-trend baselines exist.
- Chronological leakage-safe splits, domain-of-validity checks, physical
  plausibility checks, residual uncertainty intervals, benchmark comparisons,
  lifecycle states, provenance, and E1 safety gates exist.
- The model explicitly reports when it is degraded or outside its calibration
  envelope.

Remaining boundary: training/evaluation uses synthetic prototype data; the
Ridge model does not currently beat the documented trend baseline; uncertainty
is not field-calibrated; and the terrain/hydrodynamic physics layer is not
available because the required datum, DEM, NRSC metadata, and connectivity
inputs are unverified.

## Final invariant checklist

- [x] Canonical baseline immutability.
- [x] Scenario branch isolation and rollback.
- [x] Allocation plan separate from movement state.
- [x] Explicit unmet demand and failed reroute outcomes.
- [x] Destination effective-capacity and resource non-negativity guards.
- [x] Route/capacity/allocation snapshot consistency.
- [x] Zero, maximum, missing, NaN, Inf, negative, and impossible simulation
      parameter handling.
- [x] Prediction domain, physical, uncertainty, and provenance gates.
- [x] Authority override validation and audit trail.
- [x] Research isolation from operational E1-E6 state.
- [ ] Rescue teams, vehicles, dispatch, and pickup execution.
- [ ] Predicted route validity windows and edge-by-edge time feasibility.
- [ ] Verified household/road/shelter field-feedback loop.
- [ ] Calibrated real-world hybrid ML + physics predictor.

## Honest final assessment

The prototype is substantially stronger and its known failure boundaries are
explicitly enforced. It is not scientifically honest to claim that every PDF
future capability is already implemented. The four unchecked items above are
the remaining material loopholes for an operational system and should remain
visible in the project pitch rather than being implied away.

Focused audit regression suite: **30 passed**.
