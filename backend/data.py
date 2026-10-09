"""
data.py — crop constants, instance generation, and metric helpers.
All functions are pure Python / numpy; no Qiskit dependency here.
"""
import numpy as np

CROPS       = ["paddy", "maize", "pulses", "cotton"]
UNITS       = [1, 2, 3]           # Low=1, Med=2, High=3 water units
LEVEL_NAMES = ["LOW", "MED", "HIGH"]
SCENARIOS   = {"Dry": 0.7, "Normal": 1.0, "Wet": 1.3}

# Human-readable inflow scenario labels for the Water Resources Dept UI.
# The keys (Dry/Normal/Wet) remain the internal API identifiers.
SCENARIO_DISPLAY = {
    "Dry":    "Deficit Year (Drought Inflow)",
    "Normal": "Normal Year (Seasonal Inflow)",
    "Wet":    "Surplus Year (Flood / Excess Inflow)",
}

# Season label — water allocation is for one crop season at a time.
# ponytail: single season (Kharif); upgrade: multi-season / multi-period QUBO.
SEASON_LABEL = "Kharif Season (June – October)"

# Stakeholder types present in the command area.
# agriculture: crop irrigation (paddy, maize, pulses, cotton)
# municipal:   drinking-water supply canals — higher priority, cannot go to Low
STAKEHOLDER_TYPES = ["agriculture", "municipal"]

# Minimum release level (in UNITS) each stakeholder type must receive.
# This enforces the "hydrological constraint" from the problem statement.
# agriculture min=1 (Low is OK), municipal min=2 (must get at least Med).
MIN_FLOW_BY_TYPE = {
    "agriculture": 1,   # ecological/irrigation floor
    "municipal":   2,   # drinking-water floor — cannot be starved
}

# Concave benefit curves per canal type at [Low, Med, High] release levels.
# municipal gets higher absolute benefit to reflect priority over agriculture.
# ponytail: illustrative data; upgrade: real CWC/KGBO hydrological curves.
BASE_BENEFITS = {
    "paddy":     [3.0, 5.5, 7.5],
    "maize":     [2.5, 4.0, 5.0],
    "pulses":    [2.0, 3.0, 3.5],
    "cotton":    [1.5, 2.5, 3.0],
    "municipal": [4.5, 7.5, 9.5],   # drinking water: highest priority benefit
}


def make_instance(N, seed=42):
    """
    Generate one random problem instance.

    Returns
    -------
    crops              : list[str]   canal type (crop or 'municipal')
    benefit            : (N, 3) array
    supply_by_scenario : dict {scenario_key: supply_units}
    stakeholders       : list[str]  'agriculture' or 'municipal' per canal
    min_flows          : list[int]  minimum water units required per canal

    ponytail: single reservoir (Godavari or Krishna zone);
      upgrade: run once per zone, link via inter-basin transfer constraint.
    """
    rng = np.random.default_rng(seed)

    # Assign stakeholder types: mostly agriculture, at least one municipal
    # for realism (drinking-water supply is always present in command areas).
    stakeholders = rng.choice(
        STAKEHOLDER_TYPES, size=N, p=[0.75, 0.25]
    ).tolist()
    # Guarantee at least one municipal canal when N >= 2
    if N >= 2 and "municipal" not in stakeholders:
        stakeholders[rng.integers(0, N)] = "municipal"

    # Assign canal types: agricultural canals get a crop, municipal get 'municipal'
    crops = []
    for st in stakeholders:
        if st == "agriculture":
            crops.append(str(rng.choice(CROPS)))
        else:
            crops.append("municipal")

    # Build benefit matrix with ±10 % noise
    benefit = np.zeros((N, 3))
    for c, canal_type in enumerate(crops):
        noise = rng.uniform(0.9, 1.1, size=3)
        benefit[c] = np.array(BASE_BENEFITS[canal_type]) * noise

    # Min flow per canal driven by stakeholder type
    min_flows = [MIN_FLOW_BY_TYPE[s] for s in stakeholders]

    # Supply scenarios — scaled from "all canals at medium" baseline
    med_total = N * 2
    supply_by_scenario = {
        name: max(N, int(round(med_total * mult)))
        for name, mult in SCENARIOS.items()
    }
    return crops, benefit, supply_by_scenario, stakeholders, min_flows


def int_to_bits(s, n):
    """Integer s -> length-n binary array (bit 0 = index 0)."""
    return np.array([(s >> k) & 1 for k in range(n)], dtype=float)


def decode_alloc(x, N):
    """Bitstring x -> level index (0/1/2) per canal."""
    levels = []
    for c in range(N):
        bits = x[c * 3: c * 3 + 3]
        levels.append(int(np.argmax(bits)) if bits.sum() == 1 else 0)
    return np.array(levels, dtype=int)


def qubo_energy(x, Q):
    """QUBO energy E = x^T Q x."""
    return float(x @ Q @ x)


def total_benefit(x, N, benefit):
    lvls = decode_alloc(x, N)
    return float(sum(benefit[c, lvls[c]] for c in range(N)))


def is_feasible(x, N, supply):
    for c in range(N):
        if x[c * 3: c * 3 + 3].sum() != 1:
            return False
    used = sum(UNITS[l] * x[c * 3 + l] for c in range(N) for l in range(3))
    return float(used) <= supply


def fairness_gap(x, N):
    lvls = decode_alloc(x, N)
    return int(UNITS[lvls.max()] - UNITS[lvls.min()])


def waste_pct(x, N, supply):
    used = sum(UNITS[l] * x[c * 3 + l] for c in range(N) for l in range(3))
    return abs(float(used) - supply) / supply * 100.0


def counts_to_best(counts, Q, N):
    """Return (energy, bitstring) of best sampled QAOA bitstring."""
    best_e, best_x = float("inf"), None
    for bitstr in counts:
        x = np.array([int(b) for b in reversed(bitstr)], dtype=float)
        if len(x) > N * 3:
            x = x[: N * 3]
        e = qubo_energy(x, Q)
        if e < best_e:
            best_e, best_x = e, x.copy()
    return best_e, best_x


def p_optimal_fn(counts, opt_x):
    opt_str = "".join(str(int(b)) for b in reversed(opt_x))
    total   = sum(counts.values())
    return counts.get(opt_str, 0) / total


def feasibility_rate(counts, N, supply):
    total = sum(counts.values())
    ok = 0
    for bitstr, cnt in counts.items():
        x = np.array([int(b) for b in reversed(bitstr)], dtype=float)
        if len(x) > N * 3:
            x = x[: N * 3]
        if is_feasible(x, N, supply):
            ok += cnt
    return ok / total


def min_flow_violated(x, N, min_flows):
    """
    Count how many canals receive less than their required minimum flow.
    min_flows: list of ints (one per canal, in UNITS).
    """
    if min_flows is None:
        return 0
    lvls = decode_alloc(x, N)
    return sum(
        1 for c in range(N) if UNITS[lvls[c]] < min_flows[c]
    )


def allocation_to_dict(x, N, crops, benefit, supply,
                        stakeholders=None, min_flows=None):
    """
    Convert bitstring allocation to a JSON-serialisable release schedule dict.
    Now includes stakeholder type and min-flow compliance per canal.
    """
    if x is None:
        return None
    lvls = decode_alloc(x, N)
    canals = []
    for c in range(N):
        l   = lvls[c]
        pos = "Head-end" if c == 0 else ("Tail-end" if c == N - 1 else f"Middle-{c}")
        st  = stakeholders[c] if stakeholders else "agriculture"
        mf  = min_flows[c]    if min_flows    else 1
        canals.append({
            "id":                c,
            "position":          pos,
            "canal_type":        crops[c],          # crop name or 'municipal'
            "stakeholder":       st,                # 'agriculture' or 'municipal'
            "level":             LEVEL_NAMES[l],
            "units":             UNITS[l],
            "min_flow_required": mf,
            "min_flow_met":      UNITS[l] >= mf,    # hydrological constraint check
            "benefit":           round(float(benefit[c, l]), 3),
        })
    used = sum(UNITS[l] * x[c * 3 + l] for c in range(N) for l in range(3))
    mfv  = min_flow_violated(x, N, min_flows) if min_flows else 0
    return {
        "season":               SEASON_LABEL,
        "canals":               canals,
        "total_units_used":     int(used),
        "supply":               supply,
        "total_benefit":        round(total_benefit(x, N, benefit), 3),
        "fairness_gap":         fairness_gap(x, N),
        "waste_pct":            round(waste_pct(x, N, supply), 2),
        "feasible":             is_feasible(x, N, supply),
        "min_flow_violations":  mfv,   # number of canals below hydrological min
    }
