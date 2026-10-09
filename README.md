# 🌊 AquaQubit
### Quantum-Powered Water Allocation & Distribution Engine

AquaQubit is an operational decision-support platform that optimizes water release schedules across agricultural command areas and municipal networks under hydrological constraints.

Built with **Qiskit's Quantum Approximate Optimization Algorithm (QAOA)**, AquaQubit translates complex multi-canal, multi-stakeholder water allocation problems into Quadratic Unconstrained Binary Optimization (QUBO) models to achieve equitable, efficient water distribution.

---

## 🌟 Key Capabilities

- **Scalable Command Region Profiles**: Out-of-the-box support for major agricultural river basins (Krishna-Godavari, Kaveri, Narmada Main Command, and Custom Regions).
- **Multi-Constraint Optimization**: Enforces reservoir capacity limits, municipal drinking water floor priorities, and tail-end agricultural equity.
- **Jain's Equity Metrics**: Computes Jain's Fairness Index to ensure zero tail-end farmer starvation.
- **Accelerated QAOA Engine**: High-performance statevector quantum evaluation delivering optimal schedules in sub-second runtimes (<0.25s).
- **One-Click Operational Export**: Generates exportable Water Release Orders (CSV format) for irrigation boards and river basin authorities.

---

## 🏗️ Project Architecture

```
AquaQubit/
├── backend/
│   ├── app.py          # Flask REST API & Static Asset Server
│   ├── data.py         # Basin Profiles, Equity Metrics & Schedule Formatter
│   ├── qubo.py         # QUBO Matrix & Ising Hamiltonian Generator
│   └── solvers.py      # QAOA Quantum Optimization Engine & Classical Solvers
├── frontend/
│   ├── index.html      # Command Center UI Dashboard
│   ├── style.css       # Clean Corporate Design System
│   └── app.js          # Interactive Client Engine Controller
├── requirements.txt    # Pinned Dependencies (Qiskit, NumPy, SciPy, Flask)
└── README.md           # Project Documentation
```

---

## ⚙️ Mathematical Formulation

For $N$ canal reaches with 3 discrete water release levels (Low 33%, Medium 66%, High 100%), the system constructs a QUBO matrix $Q \in \mathbb{R}^{3N \times 3N}$ minimized over binary state $x \in \{0, 1\}^{3N}$:

$$\min_{x} E(x) = x^T Q x = \text{Term}_1 + \text{Term}_2 + \text{Term}_3 + \text{Term}_4 + \text{Term}_5$$

- **Term 1 (Utility Maximisation)**: Maximize agricultural yield and municipal benefit.
- **Term 2 (Single-Level Penalty)**: Enforce exactly one release level per canal.
- **Term 3 (Reservoir Supply Penalty)**: Penalize releases exceeding available reservoir storage.
- **Term 4 (Pairwise Equity Gap Penalty)**: Minimize allocation variance between head-end and tail-end zones.
- **Term 5 (Minimum Flow Floor Penalty)**: Guarantee minimum required flow for municipal intakes.

---

## 🚀 Quick Start & Installation

### 1. Prerequisites
- Python 3.10+ installed.

### 2. Setup Virtual Environment
```bash
# Clone repository
git clone https://github.com/kumarraj-korasala/AquaQubit.git
cd AquaQubit

# Create virtual environment
python -m venv .venv

# Activate environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Activate environment (Linux/macOS)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Launch Application
```bash
python backend/app.py
```

Open your browser and navigate to:
👉 **`http://localhost:5000`**

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | `GET` | Serves the AquaQubit Web UI Dashboard |
| `/api/health` | `GET` | Engine status check |
| `/api/reservoirs` | `GET` | Returns registered basin profiles |
| `/api/schedule` | `POST` | Generates water release schedule via QAOA Engine |
| `/api/solve` | `POST` | Runs benchmark matrix (BruteForce, Greedy, SA, QAOA) |

### Sample `/api/schedule` Request Payload
```json
{
  "n_canals": 5,
  "supply_tmc": 10.0,
  "p_depth": 2,
  "seed": 42,
  "region_key": "krishna_godavari"
}
```

---

## 📄 License

Distributed under the MIT License.
