# 🌊 AquaQubit
### Quantum-Powered Water Allocation & Release Optimization Engine

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Qiskit](https://img.shields.io/badge/Qiskit-1.2+-6929C4?style=flat&logo=qiskit&logoColor=white)](https://qiskit.org)
[![Flask](https://img.shields.io/badge/Flask-3.0+-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📌 Overview

**AquaQubit** is an operational decision-support platform designed for river basin authorities, irrigation boards, and water resource departments. It solves complex multi-canal, multi-reservoir water release scheduling problems by converting hydrological physical constraints into a **Quadratic Unconstrained Binary Optimization (QUBO)** model, solved via **Qiskit's Quantum Approximate Optimization Algorithm (QAOA)**.

By balancing agricultural crop demands, municipal drinking water floors, and conveyance losses, AquaQubit maximizes total system utility while ensuring zero tail-end farmer starvation.

---

## ✨ Key Capabilities

- **Scalable Basin Modeling**: Configurable profiles for major river basins including the Krishna-Godavari Command Area, Kaveri River Basin, Narmada Main Command, and Custom Regions.
- **Multi-Constraint QUBO Formulation**: Enforces reservoir storage capacity, municipal drinking water floor priority, and pairwise tail-end equity penalties.
- **Jain's Equity Index**: Evaluates distribution variance ($J = \frac{(\sum x_i)^2}{N \sum x_i^2}$) to guarantee fair water sharing between head-end and tail-end reaches.
- **Ultra-Fast Sub-Second QAOA Engine**: Vectorized statevector evaluation delivers optimal release schedules in **sub-second runtimes (<0.25s)**.
- **Interactive Command Center UI**: Custom dashboard with Chart.js visual analytics, clear operational units (TMC / Cusecs), and one-click CSV release order export.

---

## 🏗️ System Architecture

```
AquaQubit/
├── backend/
│   ├── app.py          # Flask REST API & Static Asset Server
│   ├── data.py         # Basin Profiles, Equity Metrics & Schedule Formatter
│   ├── qubo.py         # QUBO Matrix & Ising Hamiltonian Generator
│   └── solvers.py      # QAOA Quantum Optimization Engine & Classical Solvers
├── frontend/
│   ├── index.html      # AquaQubit Dashboard UI
│   ├── style.css       # Custom Responsive Design System
│   └── app.js          # Client-Side Controller & Chart.js Visualizations
├── requirements.txt    # Pinned Python Dependencies
└── README.md           # Project Documentation
```

---

## 📐 Mathematical QUBO Formulation

For $N$ canal reaches with 3 discrete water release levels (Low 33%, Medium 66%, High 100%), AquaQubit constructs a QUBO matrix $Q \in \mathbb{R}^{3N \times 3N}$ minimized over binary vector $x \in \{0, 1\}^{3N}$:

$$\min_{x} E(x) = x^T Q x = \text{Term}_1 + \text{Term}_2 + \text{Term}_3 + \text{Term}_4 + \text{Term}_5$$

1. **Term 1 (Utility Maximisation)**: Maximizes agricultural crop yield and municipal benefit.
   $$\text{Term}_1 = - \sum_{c=0}^{N-1} \sum_{l=0}^{2} B_{c,l} x_{c,l}$$
2. **Term 2 (Single-Level Penalty, $A = 100.0$)**: Enforces exactly one release level per canal.
   $$\text{Term}_2 = A \sum_{c=0}^{N-1} \left( \sum_{l=0}^{2} x_{c,l} - 1 \right)^2$$
3. **Term 3 (Reservoir Storage Penalty, $B = 100.0$)**: Penalizes total release exceeding available reservoir supply $S$.
   $$\text{Term}_3 = B \left( \sum_{c=0}^{N-1} \sum_{l=0}^{2} u_l x_{c,l} - S \right)^2$$
4. **Term 4 (Tail-End Equity Gap Penalty, $\lambda = 2.0$)**: Minimizes pairwise allocation variance between head-end and tail-end zones.
   $$\text{Term}_4 = \lambda \sum_{c_1 < c_2} \left( \sum_{l=0}^{2} u_l x_{c_1,l} - \sum_{l=0}^{2} u_l x_{c_2,l} \right)^2$$
5. **Term 5 (Minimum Flow Floor Penalty, $D = 50.0$)**: Guarantees non-negotiable floor flows for municipal intakes.
   $$\text{Term}_5 = D \sum_{c=0}^{N-1} \sum_{l: u_l < \text{min\_flow}_c} x_{c,l}$$

---

## 🚀 Quick Start & Installation

### 1. Clone & Setup Environment
```bash
# Clone the repository
git clone https://github.com/kumarraj-korasala/AquaQubit.git
cd AquaQubit

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python backend/app.py
```

Open your web browser and navigate to:
👉 **`http://localhost:5000`**

---

## 📡 REST API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | `GET` | Serves the AquaQubit Web UI Dashboard |
| `/api/health` | `GET` | Engine status check (`{"status": "ok"}`) |
| `/api/reservoirs` | `GET` | Returns registered command region profiles |
| `/api/schedule` | `POST` | Generates water release schedule via QAOA Engine |
| `/api/solve` | `POST` | Evaluates benchmark matrix (BruteForce, Greedy, SA, QAOA) |

### Sample Request (`POST /api/schedule`)
```json
{
  "n_canals": 5,
  "supply_tmc": 10.0,
  "p_depth": 2,
  "seed": 42,
  "region_key": "krishna_godavari"
}
```

### Sample Response (`POST /api/schedule`)
```json
{
  "success": true,
  "data": {
    "region_name": "Krishna-Godavari Command Area",
    "available_supply_tmc": 10.0,
    "total_allocated_tmc": 10.0,
    "water_efficiency_pct": 100.0,
    "jains_equity_index": 1.0,
    "min_flow_violations": 0,
    "schedule": [
      {
        "canal_id": 1,
        "canal_name": "Right Main Canal (Jawahar) (Zone 1)",
        "reach_zone": "Head-End",
        "target_use": "Municipal & Crop",
        "release_level": "Medium Release (66%)",
        "allocated_tmc": 2,
        "flow_cusecs": 2300,
        "gate_opening_pct": 50,
        "min_flow_met": true
      }
    ]
  }
}
```

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.
