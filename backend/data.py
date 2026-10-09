"""
data.py — Krishna-Godavari Command Area Domain Data & Hydrological Metrics Engine
Serves the Water Resources Dept, CWC, and KGBO Irrigation Boards.
"""
import numpy as np

# Real Krishna-Godavari Command Area Reservoirs & Canals
RESERVOIRS = {
    "Srisailam":        {"max_capacity_tmc": 215.8, "normal_inflow_tmc": 150.0},
    "NagarjunaSagar":   {"max_capacity_tmc": 312.0, "normal_inflow_tmc": 180.0},
    "PrakasamBarrage":  {"max_capacity_tmc": 3.0,   "normal_inflow_tmc": 40.0},
}

CANALS = [
    {
        "id": 0,
        "name": "Nagarjuna Sagar Right Main (Jawahar Canal)",
        "zone": "Head-end",
        "command_area_ha": 450000,
        "stakeholder": "municipal",
        "target": "Guntur & Vijayawada Municipal Intakes + Paddy",
        "min_flow_tmc": 2.0,
        "max_capacity_tmc": 4.0,
    },
    {
        "id": 1,
        "name": "Nagarjuna Sagar Left Main (Lal Bahadur Canal)",
        "zone": "Head-end",
        "command_area_ha": 400000,
        "stakeholder": "agriculture",
        "target": "Kharif Paddy & Cotton Belts",
        "min_flow_tmc": 1.0,
        "max_capacity_tmc": 3.5,
    },
    {
        "id": 2,
        "name": "Guntur Branch Canal & Distribution Network",
        "zone": "Middle",
        "command_area_ha": 250000,
        "stakeholder": "agriculture",
        "target": "Maize & Commercial Crops",
        "min_flow_tmc": 1.0,
        "max_capacity_tmc": 3.0,
    },
    {
        "id": 3,
        "name": "Krishna Western Delta Canal Reach",
        "zone": "Middle",
        "command_area_ha": 220000,
        "stakeholder": "municipal",
        "target": "Urban Drinking Intakes & Paddy",
        "min_flow_tmc": 2.0,
        "max_capacity_tmc": 3.5,
    },
    {
        "id": 4,
        "name": "Krishna Eastern Delta & Tail-End Reaches",
        "zone": "Tail-end",
        "command_area_ha": 180000,
        "stakeholder": "agriculture",
        "target": "Tail-End Farmers & Pulses",
        "min_flow_tmc": 1.0,
        "max_capacity_tmc": 2.5,
    },
]

# Hydrological Inflow Scenarios (TMC = Thousand Million Cubic Feet)
INFLOW_SCENARIOS = {
    "Deficit": {
        "label": "Monsoon Deficit / Drought (50% Supply)",
        "available_supply_units": 6,
        "reservoir_status": "Low Storage (Critical)",
    },
    "Normal": {
        "label": "Normal Kharif Season (100% Supply)",
        "available_supply_units": 10,
        "reservoir_status": "Optimal Storage",
    },
    "Surplus": {
        "label": "Surplus Flood Release (150% Supply)",
        "available_supply_units": 14,
        "reservoir_status": "High / Gate Spill Storage",
    }
}

# Compatibility Aliases for solvers.py
SCENARIOS = INFLOW_SCENARIOS
UNITS = [1, 2, 3]  # Low (1 TMC), Med (2 TMC), High (3 TMC)
LEVEL_NAMES = ["LOW", "MED", "HIGH"]
RELEASE_LEVEL_UNITS = UNITS


def int_to_bits(s, n):
    return np.array([(s >> k) & 1 for k in range(n)], dtype=int)


def decode_alloc(x, N):
    return [int(np.argmax(x[c * 3 : (c + 1) * 3])) if np.any(x[c * 3 : (c + 1) * 3]) else 0 for c in range(N)]


def qubo_energy(x, Q):
    return float(x @ Q @ x) if x is not None else float("inf")


def is_feasible(x, N, supply):
    if x is None: return False
    one_per_canal = all(sum(x[c * 3 : (c + 1) * 3]) == 1 for c in range(N))
    used = sum(UNITS[l] * x[c * 3 + l] for c in range(N) for l in range(3))
    return one_per_canal and (used <= supply)


def total_benefit(x, N, benefit):
    if x is None: return 0.0
    return sum(benefit[c, l] * x[c * 3 + l] for c in range(N) for l in range(3))


def fairness_gap(x, N):
    if x is None: return 0
    allocs = [sum(UNITS[l] * x[c * 3 + l] for l in range(3)) for c in range(N)]
    return max(allocs) - min(allocs)


def waste_pct(x, N, supply):
    if x is None or supply == 0: return 100.0
    used = sum(UNITS[l] * x[c * 3 + l] for c in range(N) for l in range(3))
    return max(0.0, ((supply - used) / supply) * 100.0)


def p_optimal_fn(counts, opt_x):
    if not counts or opt_x is None: return 0.0
    target = "".join(str(int(b)) for b in opt_x)
    return counts.get(target, 0) / sum(counts.values())


def feasibility_rate(counts, N, supply):
    if not counts: return 0.0
    ok = sum(cnt for bitstr, cnt in counts.items() if is_feasible(np.array([int(b) for b in bitstr]), N, supply))
    return ok / sum(counts.values())


def counts_to_best(counts, Q, N):
    best_e, best_x = float("inf"), None
    for bitstr in counts:
        x = np.array([int(b) for b in bitstr])
        e = qubo_energy(x, Q)
        if e < best_e:
            best_e, best_x = e, x
    return best_e, best_x


def min_flow_violated(x, N, min_flows):
    if min_flows is None or x is None: return 0
    lvls = decode_alloc(x, N)
    return sum(1 for c in range(N) if UNITS[lvls[c]] < min_flows[c])


def allocation_to_dict(x, N, crops, benefit, supply, stakeholders=None, min_flows=None):
    if x is None: return None
    lvls = decode_alloc(x, N)
    canals = []
    for c in range(N):
        l = lvls[c]
        canals.append({
            "id": c, "position": "Head-end" if c == 0 else ("Tail-end" if c == N - 1 else f"Middle-{c}"),
            "canal_type": crops[c % len(crops)], "stakeholder": stakeholders[c] if stakeholders else "agriculture",
            "level": LEVEL_NAMES[l], "units": UNITS[l], "min_flow_required": min_flows[c] if min_flows else 1,
            "min_flow_met": UNITS[l] >= (min_flows[c] if min_flows else 1),
            "benefit": round(float(benefit[c, l]), 3),
        })
    used = sum(UNITS[l] * x[c * 3 + l] for c in range(N) for l in range(3))
    return {
        "season": "Kharif Season (June – October)", "canals": canals,
        "total_units_used": int(used), "supply": supply,
        "total_benefit": round(total_benefit(x, N, benefit), 3),
        "fairness_gap": fairness_gap(x, N), "waste_pct": round(waste_pct(x, N, supply), 2),
        "feasible": is_feasible(x, N, supply), "min_flow_violations": min_flow_violated(x, N, min_flows),
    }


def make_instance(N, seed=42):
    crops = [CANALS[c % len(CANALS)]["target"].split(" ")[0] for c in range(N)]
    stakeholders = [CANALS[c % len(CANALS)]["stakeholder"] for c in range(N)]
    min_flows = [int(CANALS[c % len(CANALS)]["min_flow_tmc"]) for c in range(N)]
    benefit = get_canal_benefit_matrix(N, seed)
    supply_by_scen = {
        "Deficit": 6, "Normal": 10, "Surplus": 14,
        "Dry": 6, "Wet": 14
    }
    return crops, benefit, supply_by_scen, stakeholders, min_flows


def get_canal_benefit_matrix(N, seed=42):
    """
    Generate physical benefit matrix B[c, l] for N canals at 3 release levels.
    Municipal intakes receive higher weight to enforce non-negotiable floor.
    """
    rng = np.random.default_rng(seed)
    B = np.zeros((N, 3))
    for c in range(N):
        is_mun = CANALS[c % len(CANALS)]["stakeholder"] == "municipal"
        base = 4.5 if is_mun else 2.5
        # Concave returns: Low, Med, High
        B[c, 0] = base + rng.uniform(0.1, 0.5)
        B[c, 1] = base * 1.6 + rng.uniform(0.2, 0.6)
        B[c, 2] = base * 2.1 + rng.uniform(0.3, 0.7)
    return B


def decode_bits_to_levels(x, N):
    """Decode 3N binary vector to release level index (0, 1, or 2) per canal."""
    levels = []
    for c in range(N):
        sub = x[c * 3 : (c + 1) * 3]
        idx = int(np.argmax(sub)) if np.any(sub) else 0
        levels.append(idx)
    return levels


def calculate_jains_equity_index(allocations):
    """
    Calculate Jain's Fairness Index:
    J = (sum(x_i))^2 / (N * sum(x_i^2))
    Range: 1/N (worst inequality) to 1.0 (perfect equity).
    """
    allocs = np.array(allocations, dtype=float)
    if np.sum(allocs) == 0:
        return 1.0
    num = np.sum(allocs) ** 2
    den = len(allocs) * np.sum(allocs ** 2)
    return round(float(num / den), 3)


def format_operational_schedule(x, N, benefit_matrix, supply_units, scenario_name):
    """
    Format the Quantum Optimization result into an official CWC/KGBO Water Release Order.
    """
    if x is None:
        return None

    levels = decode_bits_to_levels(x, N)
    schedule_rows = []
    allocated_units = []

    for c in range(N):
        canal_info = CANALS[c % len(CANALS)]
        lvl_idx = levels[c]
        units = RELEASE_LEVEL_UNITS[lvl_idx]
        allocated_units.append(units)

        min_req = canal_info["min_flow_tmc"]
        min_met = units >= min_req

        # Calculate approximate flow rate in cusecs (1 TMC ~ 11,574 cusecs over 1 day)
        cusecs = int(units * 1250)

        schedule_rows.append({
            "canal_id": canal_info["id"],
            "canal_name": canal_info["name"],
            "zone": canal_info["zone"],
            "command_area_ha": canal_info["command_area_ha"],
            "stakeholder": canal_info["stakeholder"],
            "target_use": canal_info["target"],
            "assigned_level": LEVEL_NAMES[lvl_idx],
            "allocated_units_tmc": units,
            "flow_rate_cusecs": cusecs,
            "gate_opening_pct": int((units / canal_info["max_capacity_tmc"]) * 100),
            "min_flow_required_tmc": min_req,
            "min_flow_met": min_met,
            "benefit_score": round(float(benefit_matrix[c, lvl_idx]), 2),
        })

    total_used = sum(allocated_units)
    equity_index = calculate_jains_equity_index(allocated_units)
    total_benefit = sum(row["benefit_score"] for row in schedule_rows)

    # Conflict Risk Score: Lower equity gap -> Lower conflict risk
    min_flow_violations = sum(1 for row in schedule_rows if not row["min_flow_met"])
    conflict_risk = "LOW (Zero Starvation)" if min_flow_violations == 0 and equity_index >= 0.85 else "MEDIUM"

    return {
        "scenario": scenario_name,
        "reservoir_supply_available_tmc": supply_units,
        "total_water_allocated_tmc": total_used,
        "reservoir_spill_waste_tmc": max(0, supply_units - total_used),
        "water_utilization_efficiency_pct": round((min(total_used, supply_units) / supply_units) * 100, 1),
        "jains_equity_index": equity_index,
        "total_system_utility_score": round(total_benefit, 2),
        "conflict_risk_level": conflict_risk,
        "min_flow_violations_count": min_flow_violations,
        "schedule": schedule_rows,
    }
