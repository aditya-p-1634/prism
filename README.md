# PRISM — Predictive Relocation & Infrastructure Safety Matrix

**Problem Statement**: SIH 26191 — *Intelligent Identification of Hazard-Based Red Zones, Carrying Capacity Assessment, and Immediate Relocation Needs for Vulnerable Habitations*  
**Architecture**: Software-First Modular Monolith | Python/FastAPI Backend | Next.js/React Frontend | PostgreSQL/PostGIS / Embedded Spatial SQLite

---

## 1. System Overview & The Core Causal Loop

PRISM bridges the operational divide between disaster forecasting and actionable evacuation by executing the automated causal chain:

$$\text{HAZARD} \longrightarrow \text{HUMAN} \longrightarrow \text{PRIORITY} \longrightarrow \text{CAPACITY} \longrightarrow \text{RELOCATION} \longrightarrow \text{ACTION}$$

When emergency conditions deteriorate, consequences propagate deterministically across the engines:

$$\Delta \text{Hazard} \implies \Delta \text{Red Zones} \implies \Delta \text{Exposure} \implies \Delta \text{Priority} \implies \Delta \text{Capacity} \implies \Delta \text{Route Validity} \implies \Delta \text{Relocation Reallocation}$$

### Engine Responsibilities
- **Engine 1 (Multi-Hazard Intelligence)**: Inundation polygons, planar buffer spatial expansion, operational Red Zone classification, and confidence scoring.
- **Engine 2 (People & Vulnerability Priority)**: Habitation exposure intersection, demographic vulnerability ($P$-score: $0.35E + 0.25V + 0.20U + 0.10A_{\text{risk}} + 0.10\text{Ast}$), and explainable reason codes.
- **Engine 3 (Destination & Carrying Capacity)**: Hard safety filtering, multi-resource carrying capacity (shelter, water, food, healthcare, sanitation), dynamic bottleneck detection, and remaining capacity calculation.
- **Engine 4 (Safe Route Intelligence & Optimization)**: Road network graph, flooded edge pruning, multi-criteria A* routing, and Google OR-Tools CP-SAT integer programming solver for group-to-site allocation.
- **Engine 5 (Predictive Simulation & Adaptation)**: Scenario controller, dependency cascade resolution, and baseline-isolated causal delta reporting.
- **Engine 6 (Data/GIS/System Backbone)**: Canonical repositories, dual-CRS transformations, immutable snapshots, event delivery, and tamper-evident audit logging.

---

## 2. Hard Safety Invariants

1. **Safety Default**: $\text{UNKNOWN} \neq \text{SAFE}$, $\text{STALE} \neq \text{SAFE}$.
2. **Unsafe Destination Exclusion**: Any destination intersecting an active or predicted Red Zone is assigned `CLOSED` and excluded.
3. **Unsafe Route Exclusion**: Submerged road segments are pruned; route traversal across flooded edges is strictly prohibited.
4. **Baseline Immutability**: `SNAP_BASE_001` is strictly read-only; scenarios write to isolated snapshots.
5. **Non-Registration Invariant**: Missing household registration does not imply absence of vulnerability; conservative default vulnerability is assigned.
6. **Household Indivisibility**: Households and predefined groups are treated as atomic units (no arbitrary splitting).
7. **Non-Negative Capacity**: $\text{RemainingCapacity} = \max(\text{EffectiveCapacity} - \text{OccupiedCapacity}, 0) \ge 0$.
8. **Explicit Infeasibility**: Overcapacity or unreachable sites yield explicit `NO_VIABLE_ALLOCATION` (`UNMET` demand) with structured reason codes. Unsafe allocations are never forced.
9. **Audited Authority Override**: Overrides record actor ID, timestamp, prior state, new state, and mandatory operational justification in `audit_events`.
10. **Decision Support**: PRISM is a decision-support platform, not an autonomous emergency authority. Human authorities maintain ultimate operational command.

---

## 3. Quickstart & Local Development

### Prerequisites
- Python 3.11+ (Python 3.13 / 3.14 verified)
- Node.js 20+ (Node.js 24 LTS verified)

### Step 1: Install Backend Dependencies & Initialize Database
```bash
# In repository root:
python -m pip install -e "apps/api[dev]"

# Seed the canonical Vayu River Basin demo world:
python scripts/seed_demo.py

# Run automated system invariant validation:
python scripts/validate_demo.py
```

### Step 2: Run the Backend API Server
```bash
cd apps/api
python -m uvicorn app.main:app --reload --port 8000
# API docs available at http://localhost:8000/docs
```

### Step 3: Run the Frontend Command Center
```bash
cd apps/web
npm run dev
# Command Dashboard available at http://localhost:3000
```

---

## 4. SIH Canonical Scenario Walkthrough (`MONSOON_SURGE_01`)

You can execute the compound disaster scenario via CLI or directly in the UI dashboard:

```bash
python scripts/run_scenario.py MONSOON_SURGE_01
```

### What Happens in the Causal Cascade:
1. **Hazard Surge**: River stage rises $+0.50\text{m}$, rainfall surge increases by $+20\%$.
2. **Red Zone Expansion**: E1 expands flood polygons, swallowing low-lying settlements.
3. **Priority Elevation**: Riverside Lowlands households are upgraded to `IMMEDIATE` evacuation priority ($P \ge 75$).
4. **Infrastructure Failure**: `BRIDGE_01` collapses and is marked `CLOSED`.
5. **Resource Bottleneck**: Destination 2 suffers a $-25\%$ drop in water purification capacity, reducing its effective capacity from 60 to 45 persons.
6. **Adaptive Re-routing**: E4 invalidates bridge routes and re-routes convoys across the elevated bypass corridor.
7. **CP-SAT Re-optimization**: Groups are reallocated to Destination 1 and Destination 3; remaining unaccommodated demand is explicitly output as `UNMET` demand rather than forcing unsafe assignments.
8. **Authority Review**: Commander reviews the causal delta report and logs an audited override with mandatory justification.

---

## 5. Automated Test Suite

To run the complete automated test suite (including mathematical invariants, priority monotonicity, capacity bottlenecks, CP-SAT solver constraints, and API contracts):

```bash
cd apps/api
python -m pytest tests/ -v
```
