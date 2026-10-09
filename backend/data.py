"""
data.py — AquaQubit Data Engine & Hydrological Optimization Engine
Provides flexible command area modeling, water release calculations, and equity metrics.
"""
import numpy as np

# Regional Basin Profiles
BASIN_PROFILES = {
    "krishna_godavari": {
        "name": "Krishna-Godavari Command Area",
        "default_supply_tmc": 10.0,
        "canals": [
            {"name": "Right Main Canal (Jawahar)", "zone": "Head-End", "type": "Municipal & Crop", "min_flow": 2.0, "max_cap": 4.0},
            {"name": "Left Main Canal (Lal Bahadur)", "zone": "Head-End", "type": "Agricultural Paddy", "min_flow": 1.0, "max_cap": 3.5},
            {"name": "Central Distribution Branch", "zone": "Middle Reach", "type": "Agricultural Maize", "min_flow": 1.0, "max_cap": 3.0},
            {"name": "Western Delta Extension", "zone": "Middle Reach", "type": "Municipal Drinking", "min_flow": 2.0, "max_cap": 3.5},
            {"name": "Eastern Delta & Tail-End Reaches", "zone": "Tail-End", "type": "Tail-End Pulses", "min_flow": 1.0, "max_cap": 2.5},
        ]
    },
    "kaveri_basin": {
        "name": "Kaveri River Command Basin",
        "default_supply_tmc": 8.0,
        "canals": [
            {"name": "Mettur Upper Canal", "zone": "Head-End", "type": "Municipal Drinking", "min_flow": 2.0, "max_cap": 3.5},
            {"name": "Kalingarayan Canal", "zone": "Head-End", "type": "Paddy & Sugarcane", "min_flow": 1.0, "max_cap": 3.0},
            {"name": "Grand Anicut Main Canal", "zone": "Middle Reach", "type": "Agricultural Paddy", "min_flow": 1.0, "max_cap": 3.0},
            {"name": "Vennar Distributary Reach", "zone": "Tail-End", "type": "Tail-End Delta Crops", "min_flow": 1.0, "max_cap": 2.5},
        ]
    },
    "narmada_command": {
        "name": "Narmada Main Command Area",
        "default_supply_tmc": 12.0,
        "canals": [
            {"name": "Narmada Main Canal Reach 1", "zone": "Head-End", "type": "Municipal & Industrial", "min_flow": 2.0, "max_cap": 4.5},
            {"name": "Saurashtra Branch Canal", "zone": "Middle Reach", "type": "Cotton & Wheat", "min_flow": 1.0, "max_cap": 4.0},
            {"name": "Kutch Branch Canal (Tail Reach)", "zone": "Tail-End", "type": "Arid Agriculture", "min_flow": 1.0, "max_cap": 3.0},
        ]
    },
    "custom": {
        "name": "Custom Command Region",
        "default_supply_tmc": 9.0,
        "canals": [
            {"name": "Zone 1 Main Distributary", "zone": "Head-End", "type": "Municipal Intake", "min_flow": 2.0, "max_cap": 4.0},
            {"name": "Zone 2 Middle Branch", "zone": "Middle Reach", "type": "Primary Crop", "min_flow": 1.0, "max_cap": 3.5},
            {"name": "Zone 3 Tail-End Branch", "zone": "Tail-End", "type": "Secondary Crop", "min_flow": 1.0, "max_cap": 2.5},
        ]
    }
}

RELEASE_LEVEL_UNITS = [1, 2, 3]  # Low (1 TMC), Medium (2 TMC), High (3 TMC)
LEVEL_NAMES = ["Low Release (33%)", "Medium Release (66%)", "Optimal High (100%)"]


def get_canal_benefit_matrix(n_canals, seed=42):
    """
    Construct physical utility matrix B[c, l] for N canals at 3 release levels.
    """
    rng = np.random.default_rng(seed)
    B = np.zeros((n_canals, 3))
    for c in range(n_canals):
        is_municipal = (c % 2 == 0)
        base = 4.5 if is_municipal else 2.5
        B[c, 0] = base + rng.uniform(0.1, 0.4)
        B[c, 1] = base * 1.6 + rng.uniform(0.2, 0.5)
        B[c, 2] = base * 2.1 + rng.uniform(0.3, 0.6)
    return B


def calculate_jains_equity_index(allocations):
    """
    Calculate Jain's Fairness Index: J = (sum(x))^2 / (N * sum(x^2))
    Scale: 0.0 (worst inequality) to 1.0 (perfect equity).
    """
    arr = np.array(allocations, dtype=float)
    if np.sum(arr) == 0:
        return 1.0
    num = np.sum(arr) ** 2
    den = len(arr) * np.sum(arr ** 2)
    return round(float(num / den), 3)


def decode_bits_to_levels(x, n_canals):
    """Decode binary allocation vector to selected level index per canal."""
    levels = []
    for c in range(n_canals):
        sub = x[c * 3 : (c + 1) * 3]
        idx = int(np.argmax(sub)) if np.any(sub) else 0
        levels.append(idx)
    return levels


def generate_release_schedule(x, n_canals, benefit_matrix, supply_tmc, region_key="krishna_godavari"):
    """
    Generate clean, operational water release order schedule.
    """
    profile = BASIN_PROFILES.get(region_key, BASIN_PROFILES["custom"])
    canal_defs = profile["canals"]
    levels = decode_bits_to_levels(x, n_canals)

    schedule_rows = []
    allocated_units = []

    for c in range(n_canals):
        c_info = canal_defs[c % len(canal_defs)]
        lvl_idx = levels[c]
        units = RELEASE_LEVEL_UNITS[lvl_idx]
        allocated_units.append(units)

        min_req = c_info["min_flow"]
        min_met = units >= min_req
        cusecs = int(units * 1150)
        gate_opening = int((units / c_info["max_cap"]) * 100)

        schedule_rows.append({
            "canal_id": c + 1,
            "canal_name": f"{c_info['name']} (Zone {c + 1})",
            "reach_zone": c_info["zone"],
            "target_use": c_info["type"],
            "release_level": LEVEL_NAMES[lvl_idx],
            "allocated_tmc": units,
            "flow_cusecs": cusecs,
            "gate_opening_pct": min(100, gate_opening),
            "min_flow_req_tmc": min_req,
            "min_flow_met": min_met,
            "utility_score": round(float(benefit_matrix[c, lvl_idx]), 2),
        })

    total_allocated = sum(allocated_units)
    equity_index = calculate_jains_equity_index(allocated_units)
    efficiency = round((min(total_allocated, supply_tmc) / supply_tmc) * 100, 1) if supply_tmc > 0 else 0
    violations = sum(1 for r in schedule_rows if not r["min_flow_met"])

    return {
        "region_name": profile["name"],
        "available_supply_tmc": supply_tmc,
        "total_allocated_tmc": total_allocated,
        "unallocated_spill_tmc": max(0, supply_tmc - total_allocated),
        "water_efficiency_pct": efficiency,
        "jains_equity_index": equity_index,
        "total_utility_score": round(sum(r["utility_score"] for r in schedule_rows), 2),
        "min_flow_violations": violations,
        "equity_status": "High Equity" if equity_index >= 0.85 else "Moderate Equity",
        "schedule": schedule_rows
    }


# Legacy aliases for solvers.py compatibility
SCENARIOS = {
    "Deficit": {"available_supply_units": 6},
    "Normal": {"available_supply_units": 10},
    "Surplus": {"available_supply_units": 14}
}
UNITS = RELEASE_LEVEL_UNITS
LEVEL_NAMES_SHORT = ["LOW", "MED", "HIGH"]

def int_to_bits(s, n):
    return np.array([(s >> k) & 1 for k in range(n)], dtype=int)

def decode_alloc(x, N):
    return decode_bits_to_levels(x, N)

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
    lvls = decode_bits_to_levels(x, N)
    return sum(1 for c in range(N) if UNITS[lvls[c]] < min_flows[c])

def allocation_to_dict(x, N, crops, benefit, supply, stakeholders=None, min_flows=None):
    if x is None: return None
    lvls = decode_bits_to_levels(x, N)
    canals = []
    for c in range(N):
        l = lvls[c]
        canals.append({
            "id": c + 1, "position": "Head-End" if c == 0 else ("Tail-End" if c == N - 1 else f"Middle-{c}"),
            "canal_type": crops[c % len(crops)], "stakeholder": stakeholders[c] if stakeholders else "agriculture",
            "level": LEVEL_NAMES_SHORT[l], "units": UNITS[l], "min_flow_required": min_flows[c] if min_flows else 1,
            "min_flow_met": UNITS[l] >= (min_flows[c] if min_flows else 1),
            "benefit": round(float(benefit[c, l]), 3),
        })
    used = sum(UNITS[l] * x[c * 3 + l] for c in range(N) for l in range(3))
    return {
        "season": "Active Operational Allocation", "canals": canals,
        "total_units_used": int(used), "supply": supply,
        "total_benefit": round(total_benefit(x, N, benefit), 3),
        "fairness_gap": fairness_gap(x, N), "waste_pct": round(waste_pct(x, N, supply), 2),
        "feasible": is_feasible(x, N, supply), "min_flow_violations": min_flow_violated(x, N, min_flows),
    }

def make_instance(N, seed=42):
    crops = ["Municipal Intake", "Agricultural Paddy", "Commercial Crops", "Industrial Intake", "Tail-End Reach"]
    stakeholders = ["municipal", "agriculture", "agriculture", "municipal", "agriculture"]
    min_flows = [2, 1, 1, 2, 1]
    benefit = get_canal_benefit_matrix(N, seed)
    supply_by_scen = {"Deficit": 6, "Normal": 10, "Surplus": 14, "Dry": 6, "Wet": 14}
    return crops[:N], benefit, supply_by_scen, stakeholders[:N], min_flows[:N]
