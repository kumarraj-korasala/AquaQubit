"""
qubo.py — QUBO builder, QUBO->Ising conversion, and SparsePauliOp builder.
All math is done by hand with numpy; no qiskit-optimization dependency.
"""
import numpy as np
from qiskit.quantum_info import SparsePauliOp
from data import UNITS

# Penalty weights.
# A, B >> max_benefit (~9.5*N for municipal) ensures infeasible states are never optimal.
A_DEFAULT      = 100.0
B_DEFAULT      = 100.0
LAMBDA_DEFAULT = 2.0    # equity penalty (soft — fairness is important but not absolute)
D_DEFAULT      = 50.0   # min-flow / hydrological floor penalty (softer than A, B)
                         # D < A so a min-flow violation is cheaper than a supply violation
                         # but still expensive enough to avoid unless forced by Dry scenario.


def build_qubo(N, benefit, supply,
               A=A_DEFAULT, B=B_DEFAULT, lam=LAMBDA_DEFAULT,
               D=D_DEFAULT, min_flows=None):
    """
    Build the upper-triangular QUBO matrix Q for N canals.
    Energy E = x^T Q x  (x binary; x_i^2 = x_i on diagonal).

    5 terms:
      1) Crop/municipal benefit (negated — we minimise)
      2) Supply constraint A*(sum u_l*x[c,l] - supply)^2
      3) One-level-per-canal B*(sum_l x[c,l] - 1)^2
      4) Equity LAMBDA*sum_{c<d}(level_c - level_d)^2  [NOVEL]
      5) Min-flow hydrological floor D*x[c,l]          [NEW — addresses problem statement]
         Applied for every (c, l) where UNITS[l] < min_flows[c].
    """
    n = N * 3
    Q = np.zeros((n, n))
    us = UNITS

    def idx(c, l):
        return c * 3 + l

    # ── Term 1: Benefit ────────────────────────────────────────────────────
    for c in range(N):
        for l in range(3):
            Q[idx(c, l), idx(c, l)] -= benefit[c, l]

    # ── Term 2: Supply constraint ──────────────────────────────────────────
    # Expanded (constant supply^2 dropped):
    #   A*sum_i(w_i^2 - 2*supply*w_i)*x_i + 2A*sum_{i<j} w_i*w_j*x_i*x_j
    # A=100 >> max_benefit so violating supply is never optimal.
    for c in range(N):
        for l in range(3):
            i  = idx(c, l)
            wi = us[l]
            Q[i, i] += A * (wi ** 2 - 2 * supply * wi)
            for c2 in range(N):
                for l2 in range(3):
                    j = idx(c2, l2)
                    if j > i:
                        Q[i, j] += 2.0 * A * wi * us[l2]

    # ── Term 3: One level per canal ────────────────────────────────────────
    for c in range(N):
        for l in range(3):
            i = idx(c, l)
            Q[i, i] -= B                          # linear: B*(1-2) = -B
            for l2 in range(l + 1, 3):
                Q[i, idx(c, l2)] += 2.0 * B       # quadratic cross-term

    # ── Term 4: Equity (novel) ─────────────────────────────────────────────
    # level_c = sum_l UNITS[l]*x[c,l]
    # (level_c - level_d)^2 = level_c^2 + level_d^2 - 2*level_c*level_d
    # c < d => idx(c,l) < idx(d,l2) always (upper-tri guaranteed)
    for c in range(N):
        for d in range(c + 1, N):
            # level_c^2 and level_d^2
            for src in (c, d):
                for l in range(3):
                    i = idx(src, l)
                    Q[i, i] += lam * us[l] ** 2
                    for l2 in range(l + 1, 3):
                        Q[i, idx(src, l2)] += 2.0 * lam * us[l] * us[l2]
            # -2*level_c*level_d cross-canal terms
            for l in range(3):
                for l2 in range(3):
                    Q[idx(c, l), idx(d, l2)] -= 2.0 * lam * us[l] * us[l2]

    # ── Term 5: Min-flow hydrological floor (NEW) ─────────────────────────
    # Penalise selecting a level below the stakeholder's minimum required flow.
    # Only diagonal — no cross-terms. D=50 is softer than A=B=100:
    # the solver avoids violations but is not forced to if supply is too tight
    # (Dry scenario). Violations are reported in the API output.
    if min_flows is not None:
        for c in range(N):
            mf = min_flows[c]   # minimum required UNITS for canal c
            for l in range(3):
                if us[l] < mf:  # this release level is below hydrological floor
                    Q[idx(c, l), idx(c, l)] += D

    return Q


def qubo_to_ising(Q):
    """
    Convert upper-triangular QUBO Q to Ising h, J.
    Substitution: x_i = (1 - z_i) / 2   (z_i in {-1, +1})

    h[i] = -Q[ii]/2 - (1/4)*sum_{j!=i} Q_upper[min,max]
    J[i,j] = Q[i,j] / 4   for i < j
    """
    n = Q.shape[0]
    h = np.zeros(n)
    J = {}

    for i in range(n):
        h[i] = -Q[i, i] / 2.0
        for j in range(n):
            if j != i:
                h[i] -= Q[min(i, j), max(i, j)] / 4.0

    for i in range(n):
        for j in range(i + 1, n):
            if abs(Q[i, j]) > 1e-12:
                J[(i, j)] = Q[i, j] / 4.0

    return h, J


def ising_to_sparse_pauli(h, J, n):
    """
    Convert Ising h,J to Qiskit SparsePauliOp.
    Qiskit string convention: rightmost char = qubit 0.
    So qubit i -> position (n-1-i) from the left.
    """
    pauli_list = []

    for i, hi in enumerate(h):
        if abs(hi) > 1e-10:
            s = ["I"] * n
            s[n - 1 - i] = "Z"
            pauli_list.append(("".join(s), hi))

    for (i, j), Jij in J.items():
        if abs(Jij) > 1e-10:
            s = ["I"] * n
            s[n - 1 - i] = "Z"
            s[n - 1 - j] = "Z"
            pauli_list.append(("".join(s), Jij))

    if not pauli_list:
        return SparsePauliOp(["I" * n], [0.0])
    return SparsePauliOp.from_list(pauli_list)
