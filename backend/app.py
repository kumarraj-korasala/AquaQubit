"""
app.py — Flask API for the Irrigation QAOA backend.
Run: python app.py
API base: http://localhost:5000/api/
"""
import sys, os, time, traceback
sys.path.insert(0, os.path.dirname(__file__))   # ensure local imports work

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from data import make_instance, SCENARIOS
from solvers import run_all_solvers

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app = Flask(__name__)
CORS(app)   # allow the frontend (any origin) to call the API


# ── GET / — Serve Frontend ───────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(frontend_dir, "index.html")


@app.route("/style.css")
def serve_css():
    return send_from_directory(frontend_dir, "style.css")


@app.route("/app.js")
def serve_js():
    return send_from_directory(frontend_dir, "app.js")


# ── GET /api/health ───────────────────────────────────────────────────────────
@app.route("/api/health")
def health():
    return jsonify({
        "status":  "ok",
        "message": "Irrigation QAOA Backend is running",
    })


# ── GET /api/config ───────────────────────────────────────────────────────────
@app.route("/api/config")
def config():
    """Return all valid parameter options and defaults for the frontend."""
    return jsonify({
        "n_canals_options": [3, 4, 5],
        "n_qubits_map":     {3: 9, 4: 12, 5: 15},
        "scenarios":        list(SCENARIOS.keys()),
        "p_options":        [1, 2, 3],
        "defaults": {
            "n_canals":    4,
            "scenario":    "Normal",
            "p_list":      [1, 2, 3],
            "seed":        42,
        },
        "penalties": {
            "A":      100.0,
            "B":      100.0,
            "LAMBDA": 2.0,
        },
        "data_note": (
            "All data is ILLUSTRATIVE (seeded random). "
            "Replace make_instance() in data.py with real CWC/KGBO data."
        ),
    })


# ── POST /api/solve ───────────────────────────────────────────────────────────
@app.route("/api/solve", methods=["POST"])
def solve():
    """
    Run all 4 solvers on one instance and return results.

    Request JSON body:
      n_canals  : int   3, 4, or 5          (default 4)
      scenario  : str   Dry/Normal/Wet       (default Normal)
      p_list    : list  e.g. [1, 2, 3]      (default [1,2,3])
      seed      : int   random seed          (default 42)

    Response JSON:
      success, n_canals, n_qubits, scenario, supply, crops, seed,
      results  (brute_force, greedy, sim_anneal, qaoa),
      elapsed_s
    """
    try:
        body     = request.get_json(force=True) or {}
        n_canals = int(body.get("n_canals", 4))
        scenario = str(body.get("scenario", "Normal"))
        p_list   = [int(p) for p in body.get("p_list", [1, 2, 3])]
        seed     = int(body.get("seed", 42))

        # ── Validation ────────────────────────────────────────────────────
        if n_canals not in [3, 4, 5]:
            return jsonify({"error": "n_canals must be 3, 4, or 5"}), 400
        if scenario not in SCENARIOS:
            return jsonify({"error": f"scenario must be one of {list(SCENARIOS)}"}), 400
        if not p_list or any(p not in [1, 2, 3] for p in p_list):
            return jsonify({"error": "p_list must be a subset of [1, 2, 3]"}), 400

        # ── Run solvers ───────────────────────────────────────────────────
        t0 = time.time()
        crops, benefit, supply_by_scen, stakeholders, min_flows = make_instance(n_canals, seed)
        supply  = supply_by_scen[scenario]
        results = run_all_solvers(n_canals, benefit, supply, crops, p_list, seed,
                                 stakeholders=stakeholders, min_flows=min_flows)

        return jsonify({
            "success":   True,
            "n_canals":  n_canals,
            "n_qubits":  n_canals * 3,
            "scenario":  scenario,
            "supply":    supply,
            "crops":     crops,
            "seed":      seed,
            "results":   results,
            "elapsed_s": round(time.time() - t0, 2),
        })

    except Exception as exc:
        return jsonify({
            "error":     str(exc),
            "traceback": traceback.format_exc(),
        }), 500


# ── POST /api/demo ────────────────────────────────────────────────────────────
@app.route("/api/demo", methods=["GET", "POST"])
def demo():
    """Quick demo: N=4, Normal, p=1 only (fast, ~5-10 s)."""
    try:
        t0 = time.time()
        crops, benefit, supply_by_scen, stakeholders, min_flows = make_instance(4, seed=42)
        supply  = supply_by_scen["Normal"]
        results = run_all_solvers(4, benefit, supply, crops, p_list=[1], seed=42,
                                 stakeholders=stakeholders, min_flows=min_flows)
        return jsonify({
            "success":  True,
            "n_canals": 4,
            "n_qubits": 12,
            "scenario": "Normal",
            "supply":   supply,
            "crops":    crops,
            "seed":     42,
            "results":  results,
            "elapsed_s": round(time.time() - t0, 2),
            "note": "Demo run: N=4, Normal, QAOA p=1 only for speed.",
        })
    except Exception as exc:
        return jsonify({"error": str(exc), "traceback": traceback.format_exc()}), 500


# ── POST /api/schedule ────────────────────────────────────────────────────────
@app.route("/api/schedule", methods=["GET", "POST"])
def schedule():
    """
    Generate official CWC / KGBO Water Release Order using Quantum QAOA Engine.
    Body JSON / Query Params:
      n_canals: int (3, 4, 5)
      scenario: str ("Deficit", "Normal", "Surplus")
      p_depth: int (1, 2, 3)
      seed: int
    """
    try:
        from solvers import solve_water_release_schedule
        if request.method == "POST":
            body = request.get_json(force=True, silent=True) or {}
        else:
            body = request.args
        n_canals = int(body.get("n_canals", 5))
        scenario = str(body.get("scenario", "Normal"))
        p_depth  = int(body.get("p_depth", 2))
        seed     = int(body.get("seed", 42))

        order = solve_water_release_schedule(N=n_canals, scenario_name=scenario, p_depth=p_depth, seed=seed)
        return jsonify({
            "success": True,
            "data": order,
        })
    except Exception as exc:
        return jsonify({"error": str(exc), "traceback": traceback.format_exc()}), 500


# ── GET /api/reservoirs ───────────────────────────────────────────────────────
@app.route("/api/reservoirs", methods=["GET", "POST"])
def reservoirs():
    """Return status of Krishna-Godavari Basin reservoirs."""
    from data import RESERVOIRS, INFLOW_SCENARIOS
    return jsonify({
        "basin": "Krishna-Godavari Command Area",
        "reservoirs": RESERVOIRS,
        "scenarios": INFLOW_SCENARIOS,
    })


if __name__ == "__main__":
    print("Starting Krishna-Godavari Water Release Decision Support System on http://localhost:5000")
    print("Endpoints:")
    print("  GET  / (CWC Command Center UI)")
    print("  GET  /api/health")
    print("  GET  /api/reservoirs")
    print("  POST /api/schedule")
    print("  POST /api/solve")
    app.run(debug=False, host="0.0.0.0", port=5000)
