"""
solvers.py — Brute force, Greedy, Simulated Annealing, and QAOA solvers.
All four operate on the same QUBO matrix for fair comparison.
"""
import numpy as np
import time
from scipy.optimize import minimize
from qiskit.circuit.library import QAOAAnsatz
from qiskit.primitives import StatevectorEstimator, StatevectorSampler

from data import (UNITS, int_to_bits, qubo_energy, is_feasible,
                  counts_to_best, p_optimal_fn, feasibility_rate,
                  total_benefit, fairness_gap, waste_pct, allocation_to_dict,
                  min_flow_violated)
from qubo import build_qubo, qubo_to_ising, ising_to_sparse_pauli

COBYLA_MAXITER = 150    # optimizer budget per QAOA run
SEED_BASE      = 42


# ── Shared utility ────────────────────────────────────────────────────────────
def all_qubo_energies(Q):
    """Compute QUBO energy for every bitstring. Returns (2^n,) array."""
    n = Q.shape[0]
    states = np.array(
        [[(s >> k) & 1 for k in range(n)] for s in range(2 ** n)],
        dtype=float,
    )
    return np.einsum("si,ij,sj->s", states, Q, states)  # E = x^T Q x


# ── Solver 1: Brute Force ─────────────────────────────────────────────────────
# ponytail: limited to ~20 qubits (2^20 ~ 1M states);
#   upgrade: quantum branch-and-bound or Grover search.
def brute_force(Q, N, supply):
    n = Q.shape[0]
    t0 = time.time()
    energies = all_qubo_energies(Q)
    best_e, best_x = float("inf"), None
    for s in np.argsort(energies):
        x = int_to_bits(int(s), n)
        if is_feasible(x, N, supply):
            best_e, best_x = float(energies[s]), x
            break
    return best_e, best_x, time.time() - t0


# ── Solver 2: Greedy ──────────────────────────────────────────────────────────
def greedy(N, benefit, supply):
    """Start every canal at Low; repeatedly upgrade the canal with the best
    benefit gain while supply allows. Classical baseline."""
    t0 = time.time()
    levels = [0] * N
    used   = N * UNITS[0]
    improved = True
    while improved:
        improved = False
        best_gain, best_c, best_l = -1, -1, -1
        for c in range(N):
            for nl in range(levels[c] + 1, 3):
                extra = UNITS[nl] - UNITS[levels[c]]
                if used + extra > supply:
                    continue
                gain = benefit[c, nl] - benefit[c, levels[c]]
                if gain > best_gain:
                    best_gain, best_c, best_l = gain, c, nl
        if best_c >= 0:
            used += UNITS[best_l] - UNITS[levels[best_c]]
            levels[best_c] = best_l
            improved = True
    x = np.zeros(N * 3, dtype=float)
    for c in range(N):
        x[c * 3 + levels[c]] = 1.0
    return x, time.time() - t0


# ── Solver 3: Simulated Annealing ─────────────────────────────────────────────
# Quantum-inspired: mimics tunnelling via stochastic hill-climbing.
# ponytail: ~30 lines, numpy only, no SA library.
def simulated_annealing(Q, N, n_iter=5000, seed=0):
    rng = np.random.default_rng(seed)
    n   = Q.shape[0]
    t0  = time.time()
    # Random feasible start (one level per canal)
    x = np.zeros(n, dtype=float)
    for c in range(N):
        x[c * 3 + rng.integers(0, 3)] = 1.0
    cur_e  = float(x @ Q @ x)
    best_x = x.copy()
    best_e = cur_e
    T_init, T_final = 50.0, 0.01
    for i in range(n_iter):
        T = T_init * (T_final / T_init) ** (i / n_iter)   # exponential cooling
        c_    = rng.integers(0, N)
        cur_l = int(np.argmax(x[c_ * 3: c_ * 3 + 3]))
        new_l = rng.choice([l for l in range(3) if l != cur_l])
        nx = x.copy()
        nx[c_ * 3 + cur_l] = 0.0
        nx[c_ * 3 + new_l] = 1.0
        ne    = float(nx @ Q @ nx)
        delta = ne - cur_e
        if delta < 0 or rng.random() < np.exp(-delta / max(T, 1e-10)):
            x, cur_e = nx, ne
        if cur_e < best_e:
            best_e, best_x = cur_e, x.copy()
    return best_e, best_x, time.time() - t0


# ── Solver 4: QAOA ────────────────────────────────────────────────────────────
# Accelerated with direct Statevector expectation evaluation; replaces slow
# StatevectorEstimator matrix exponentials for fast web responses (<1s).
from qiskit import QuantumCircuit
from qiskit.circuit import ParameterVector
from qiskit.quantum_info import Statevector

def run_qaoa(cost_op, Q, N, supply, p, x0=None, seed=SEED_BASE, shots=1024):
    """
    Run QAOA at depth p using vectorized Statevector evaluation.
    x0: initial params; if len(x0) < 2p, warm-start extends with small noise.
    """
    n        = Q.shape[0]   # N * 3 qubits
    rng      = np.random.default_rng(seed)
    t0       = time.time()
    energies = all_qubo_energies(Q)

    n_params = 2 * p
    if x0 is None:
        x0 = rng.uniform(-np.pi, np.pi, n_params)
    elif len(x0) < n_params:
        n_new = n_params - len(x0)
        x0    = np.concatenate([x0, rng.uniform(-0.3, 0.3, n_new)])

    # Construct parameterized QAOA ansatz circuit
    gammas = ParameterVector('g', p)
    betas  = ParameterVector('b', p)
    qc     = QuantumCircuit(n)
    qc.h(range(n))

    for layer in range(p):
        g = gammas[layer]
        b = betas[layer]
        # Cost Hamiltonian evolution e^(-i gamma H_C)
        for i in range(n):
            if abs(Q[i, i]) > 1e-6:
                qc.rz(2 * g * Q[i, i], i)
        for i in range(n):
            for j in range(i + 1, n):
                if abs(Q[i, j]) > 1e-6:
                    qc.rzz(2 * g * Q[i, j], i, j)
        # Mixer Hamiltonian evolution e^(-i beta H_M)
        for i in range(n):
            qc.rx(2 * b, i)

    call_count = [0]

    def cost_func(params):
        call_count[0] += 1
        param_dict = {}
        for layer in range(p):
            param_dict[gammas[layer]] = params[layer]
            param_dict[betas[layer]]  = params[p + layer]
        bound_qc = qc.assign_parameters(param_dict)
        sv = Statevector.from_instruction(bound_qc)
        probs = np.abs(sv.data) ** 2
        return float(np.sum(probs * energies))

    opt = minimize(cost_func, x0, method="COBYLA",
                   options={"maxiter": COBYLA_MAXITER, "rhobeg": 0.5})
    opt_params = opt.x

    # Sample counts from final statevector
    opt_param_dict = {}
    for layer in range(p):
        opt_param_dict[gammas[layer]] = opt_params[layer]
        opt_param_dict[betas[layer]]  = opt_params[p + layer]
    opt_qc = qc.assign_parameters(opt_param_dict)
    final_sv = Statevector.from_instruction(opt_qc)

    # Convert statevector probabilities to shot counts
    probs = np.abs(final_sv.data) ** 2
    sampled_indices = rng.choice(2**n, size=shots, p=probs)
    counts = {}
    for idx in sampled_indices:
        bitstr = format(idx, f'0{n}b')
        counts[bitstr] = counts.get(bitstr, 0) + 1

    best_e, best_x = counts_to_best(counts, Q, N)
    return {
        "opt_params": opt_params,
        "best_e":     best_e,
        "best_x":     best_x,
        "counts":     counts,
        "runtime":    time.time() - t0,
        "ncalls":     call_count[0],
    }


# ── run_all_solvers — main entry point for the API ────────────────────────────
def run_all_solvers(N, benefit, supply, crops, p_list=None, seed=SEED_BASE,
                    stakeholders=None, min_flows=None):
    """
    Run BruteForce, Greedy, SimAnneal, and QAOA on one instance.
    Returns a JSON-serialisable dict.
    """
    if p_list is None:
        p_list = [1, 2, 3]

    Q       = build_qubo(N, benefit, supply, min_flows=min_flows)
    h, J    = qubo_to_ising(Q)
    cost_op = ising_to_sparse_pauli(h, J, N * 3)

    # ── Ground truth ────────────────────────────────────────────────────────
    bf_e, bf_x, bf_rt = brute_force(Q, N, supply)
    bf_ben = total_benefit(bf_x, N, benefit)

    def make_row(e, x, rt, cnts=None):
        """Build a standard result row."""
        ben  = total_benefit(x, N, benefit) if x is not None else 0.0
        feas = is_feasible(x, N, supply)    if x is not None else False
        return {
            "energy":           round(float(e), 4)  if e is not None else None,
            "benefit":          round(ben, 3),
            "runtime_s":        round(rt, 4),
            "opt_gap":          round(float(e) - bf_e, 4) if e is not None else None,
            "approx_ratio":     round(ben / bf_ben, 4)    if bf_ben > 0 else None,
            "feasible":         feas,
            "fairness_gap":     fairness_gap(x, N) if x is not None else None,
            "waste_pct":        round(waste_pct(x, N, supply), 2) if x is not None else None,
            "p_optimal":        round(p_optimal_fn(cnts, bf_x), 4) if cnts else None,
            "feasibility_rate": round(feasibility_rate(cnts, N, supply), 4) if cnts else (1.0 if feas else 0.0),
            "allocation":       allocation_to_dict(x, N, crops, benefit, supply,
                                                   stakeholders=stakeholders, min_flows=min_flows),
        }

    out = {
        "brute_force": make_row(bf_e, bf_x, bf_rt),
        "greedy":      None,
        "sim_anneal":  None,
        "qaoa":        {},
        "meta": {
            "N":          N,
            "n_qubits":    N * 3,
            "supply":     supply,
            "bf_energy":  round(bf_e, 4),
            "bf_benefit": round(bf_ben, 3),
        },
    }

    # ── Greedy ───────────────────────────────────────────────────────────────
    gr_x, gr_rt = greedy(N, benefit, supply)
    gr_e = qubo_energy(gr_x, Q)
    out["greedy"] = make_row(gr_e, gr_x, gr_rt)

    # ── Simulated Annealing ──────────────────────────────────────────────────
    sa_e, sa_x, sa_rt = simulated_annealing(Q, N, seed=seed)
    out["sim_anneal"] = make_row(sa_e, sa_x, sa_rt)

    # ── QAOA with warm start across p ────────────────────────────────────────
    prev_params = None
    for p in p_list:
        qr          = run_qaoa(cost_op, Q, N, supply, p=p, x0=prev_params, seed=seed)
        prev_params = qr["opt_params"]   # warm start for next p
    return out


# ── Operational Entry Point for AquaQubit Water Allocation Engine ─────────────
def solve_water_release_schedule(N=5, supply_tmc=10.0, p_depth=2, seed=SEED_BASE, region_key="krishna_godavari"):
    """
    Main Quantum Decision Support function for AquaQubit.
    Solves the multi-canal QUBO model using QAOA and returns operational release schedule.
    """
    from data import get_canal_benefit_matrix, generate_release_schedule

    benefit_matrix = get_canal_benefit_matrix(N, seed=seed)

    Q = build_qubo(N, benefit_matrix, supply_tmc)
    h, J = qubo_to_ising(Q)
    cost_op = ising_to_sparse_pauli(h, J, N * 3)

    # Solve using QAOA quantum optimisation engine
    qr = run_qaoa(cost_op, Q, N, supply_tmc, p=p_depth, seed=seed)

    # Format operational schedule
    operational_order = generate_release_schedule(
        qr["best_x"], N, benefit_matrix, supply_tmc, region_key=region_key
    )
    operational_order["optimization_meta"] = {
        "engine": "AquaQubit QAOA Engine",
        "circuit_depth_p": p_depth,
        "n_qubits": N * 3,
        "runtime_seconds": round(qr["runtime"], 3),
        "ising_energy": round(float(qr["best_e"]), 4),
    }

    return operational_order
