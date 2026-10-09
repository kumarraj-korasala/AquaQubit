# Gap Analysis — Official Problem Statement vs Our Approach

## Official Statement (word by word)

> *"Allocating limited water across **canals, reservoirs and crops** under **competing demands** and **variable inflows** is a complex optimisation problem."*
>
> *"Quantum and quantum-inspired optimisation **schedule releases and allocations** to maximise productive use under **hydrological constraints**."*
>
> *"More **equitable, efficient** water use; reduced **conflict and waste**."*
>
> *"Applies to: Water Resources Dept; **CWC/KGBO coordination**; irrigation boards."*

---

## Gap Table

| Keyword | What the problem requires | What we built | Status |
|---------|--------------------------|---------------|--------|
| **canals, reservoirs AND crops** | Allocation to canals + reservoir storage + crop fields | Only canals + crops; 1 reservoir (source only) | ⚠️ Partial |
| **competing demands** | Multiple stakeholder types (agriculture, municipal, industrial) competing for same water | Only agricultural canals | ❌ Missing |
| **variable inflows** | Dynamic inflow variability | Dry/Normal/Wet scenarios | ✅ Covered |
| **schedule releases** | Temporal scheduling of water releases | One-shot static allocation | ⚠️ Framing only |
| **hydrological constraints** | Min ecological flow, canal capacity, seepage | Only supply upper bound | ❌ Missing |
| **equitable** | Fair distribution across head/tail and across stakeholder types | Equity term between canals | ✅ Covered |
| **reduced conflict** | Stakeholder priority (municipal > agriculture) enforced | Not modelled | ❌ Missing |
| **reduced waste** | Minimise over/under-allocation | waste_pct metric | ✅ Covered |
| **CWC/KGBO** | Data applicable to those bodies | Labeled in output | ✅ Covered |

---

## Proposed Changes (practical, beginner-friendly)

### Change 1 — Add Stakeholder Types (`data.py`)
**Why:** "competing demands" = agriculture AND municipal water users competing for same reservoir.  
**What:** Add `'municipal'` as a canal type alongside crop types. Municipal canals get a higher benefit weight (drinking water > agriculture in priority).

```python
STAKEHOLDER_TYPES  = ['agriculture', 'municipal']
MIN_FLOW_BY_TYPE   = {'agriculture': 1, 'municipal': 2}   # min units (Low/Med/High)
```

### Change 2 — Minimum Ecological Flow Constraint (`qubo.py`)
**Why:** "hydrological constraints" — every canal must receive at least a minimum flow  
(ecological flow for agriculture; drinking water floor for municipal).  
**What:** Add QUBO Term 5: penalise selecting any release level below `min_flow[c]`.

```
Term 5:  D * sum_c  sum_{l: units[l] < min_flow[c]}  x[c,l]
```
This is purely diagonal — just adds a penalty for under-allocation. D = 50 (below A=100, B=100 — it's a soft floor, not a hard ban).

### Change 3 — Scenario Display Labels (`data.py`)
**Why:** "variable inflows" — the three scenarios should be labelled clearly for stakeholders.  
**What:** Add display names alongside internal keys.

```python
SCENARIO_DISPLAY = {
    'Dry':    'Deficit Year (Drought Inflow)',
    'Normal': 'Normal Year (Seasonal Inflow)',
    'Wet':    'Surplus Year (Flood / Surplus Inflow)',
}
```

### Change 4 — Output Framing: "Release Schedule" (`data.py`, `app.py`)
**Why:** "schedule releases" — language matters for the jury and Water Dept officials.  
**What:** Rename "Allocation Table" → "Kharif Season Release Schedule" in output; add `season` field to API response.

### Change 5 — Multi-reservoir Framing (README + walkthrough)
**Why:** Problem says "reservoirs" (plural) — Godavari + Krishna are two basin systems.  
**What:** Add a note that N canals can represent **two zones** (Godavari basin / Krishna basin). In a real deployment, run the solver once per zone with its own supply. Code unchanged; just framing.

---

## What We Are NOT Changing

| Item | Why not |
|------|---------|
| Temporal scheduling (multi-period) | N=4, T=2, 3 levels = 24 qubits → statevector crashes; upgrade path noted |
| Full multi-reservoir cascade model | Would redesign the QUBO entirely; too complex for beginners |
| Real CWC/KGBO data | Illustrative data is explicit; swap is a one-function change |
| Industrial stakeholder | 3rd stakeholder type adds complexity without changing the algorithm |

---

## Files to Update

| File | Change |
|------|--------|
| `backend/data.py` | Add stakeholder types, `MIN_FLOW_BY_TYPE`, `SCENARIO_DISPLAY`, `'municipal'` benefit curve, update `make_instance()` + `allocation_to_dict()` |
| `backend/qubo.py` | Add Term 5 (min flow), `D` penalty, update `build_qubo()` signature |
| `backend/solvers.py` | Pass `min_flows` from `make_instance()` to `build_qubo()` via `run_all_solvers()` |
| `backend/app.py` | Unpack new `make_instance()` returns; add `stakeholders`, `season`, `scenario_label` to response |
| `README.md` | Add multi-reservoir framing note; update problem formulation section |
