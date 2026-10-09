# 🌊 Equitable Irrigation Water Allocation using QAOA
### Qiskit Fall Fest 2026 — Use Case 03

Allocate limited reservoir water across N canals in AP's Krishna-Godavari command area using a quantum-classical hybrid (QAOA) approach. Benchmarked against brute force, greedy, and simulated annealing.

> **Data is ILLUSTRATIVE** (seeded random). Replace `make_instance()` in `backend/data.py` with real CWC/KGBO hydrological data to use in production.

---

## Project Structure

```
Project/
├── backend/
│   ├── app.py          Flask API — 4 routes
│   ├── data.py         Crop data, instance generation, metric helpers
│   ├── qubo.py         QUBO builder, Ising conversion, SparsePauliOp
│   └── solvers.py      Brute force, Greedy, Sim. Annealing, QAOA
├── frontend/
│   ├── index.html      Single-page web app
│   ├── style.css       Dark glassmorphism theme
│   └── app.js          API calls + result rendering
├── README.md
└── requirements.txt
```

---

## How to Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the backend
```bash
cd backend
python app.py
# Running on http://localhost:5000
```

### 3. Open the frontend
Open `frontend/index.html` in your browser (or serve it):
```bash
cd frontend
python -m http.server 3000
# Open http://localhost:3000
```

---

## API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/health` | Server status |
| GET | `/api/config` | Valid params + defaults |
| GET | `/api/demo` | Quick demo (N=4, Normal, p=1) |
| POST | `/api/solve` | Run all solvers with custom params |

### POST `/api/solve` — Request
```json
{
  "n_canals": 4,
  "scenario": "Normal",
  "p_list": [1, 2, 3],
  "seed": 42
}
```

---

## Problem Formulation

**Variables:** `x[canal, level] ∈ {0,1}` — 1 if canal gets that release level
**Qubits:** N × 3 (N=3→9q, N=4→12q, N=5→15q)

**QUBO cost function (4 terms):**
- Benefit: maximise crop-specific water benefit
- Supply constraint (A=100): total allocation ≤ reservoir supply
- One-level constraint (B=100): each canal picks exactly one level
- **Equity term (Λ=2)** ⭐: minimise head-end/tail-end disparity (novel)

Converted to Ising Hamiltonian by hand. No `qiskit-optimization`.

---

## Solvers Compared

| Solver | Type | Purpose |
|--------|------|---------|
| Brute Force | Exact | Ground truth (optimal) |
| Greedy | Classical | Fast baseline |
| Simulated Annealing | Classical (quantum-inspired) | Better baseline |
| QAOA p=1,2,3 | Quantum hybrid | Main experiment |

QAOA uses warm start: p=2 initialises from p=1 optimal parameters.

---

## Metrics

| Metric | Description |
|--------|-------------|
| `opt_gap` | Energy gap from brute-force optimum (↓ better) |
| `approx_ratio` | Benefit / optimal benefit (↑ closer to 1 = better) |
| `p_optimal` | Probability of sampling the optimal bitstring (QAOA) |
| `feasibility_rate` | Fraction of samples satisfying all constraints |
| `fairness_gap` | max(level) − min(level) across canals (↓ = equitable) |
| `waste_pct` | |used − supply| / supply × 100 |

---

## Quantum Advantage Statement

**No speedup is claimed at 12 qubits** — a laptop solves this instantly.
We demonstrate: (1) correct QUBO with equity term, (2) QAOA finds near-optimal solutions,
(3) the framework is a one-line swap from FakeFez to real IBM hardware.

---

## Limitations & Upgrade Path

| Limitation | Upgrade |
|-----------|---------|
| Illustrative data | Real CWC/KGBO inflow + benefit curves |
| Single reservoir | Cascade / multi-reservoir QUBO |
| 3 release levels | Finer discretisation |
| Statevector sim ~20q | SamplerV2 on real IBM hardware |
| COBYLA local minima | SPSA / Adam with gradients |
