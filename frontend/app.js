/**
 * app.js — Frontend JavaScript for Krishna-Godavari Command Area Water Allocation Web UI
 * Connects to Flask backend API (http://localhost:5000/api/)
 */

const API_BASE = window.location.protocol.startsWith('http')
    ? `${window.location.origin}/api`
    : 'http://localhost:5000/api';

let convergenceChart = null;

// Initialize dashboard on DOM ready
document.addEventListener("DOMContentLoaded", () => {
    checkHealth();
    updateQubitBadge();
});

/**
 * Check backend connectivity status
 */
async function checkHealth() {
    const statusEl = document.getElementById("apiStatus");
    try {
        const res = await fetch(`${API_BASE}/health`, { method: "GET" });
        if (res.ok) {
            const data = await res.json();
            statusEl.classList.add("connected");
            statusEl.classList.remove("error");
            statusEl.querySelector(".status-text").textContent = "Backend Connected";
        } else {
            throw new Error("HTTP " + res.status);
        }
    } catch (err) {
        statusEl.classList.add("error");
        statusEl.classList.remove("connected");
        statusEl.querySelector(".status-text").textContent = "Backend Offline (Offline Mode)";
    }
}

/**
 * Update Qubit Badge & Hardware metrics based on canal selection
 */
function updateQubitBadge() {
    const n = parseInt(document.getElementById("nCanalsSelect").value);
    const nQubits = n * 3;
    document.getElementById("kpiQubits").textContent = `${nQubits} Qubits`;
    document.getElementById("kpiCanals").textContent = `${n} Canals (3^${n} = ${Math.pow(3, n)} states)`;

    // Update estimated hardware metrics
    const hwQubits = document.getElementById("hwQubits");
    const hwDepth = document.getElementById("hwDepth");
    const hwCnots = document.getElementById("hwCnots");

    if (hwQubits) hwQubits.textContent = `${nQubits} / 156 (FakeFez)`;
    if (hwDepth)  hwDepth.textContent  = n === 3 ? "~90 - 120" : (n === 4 ? "~140 - 200" : "~220 - 350");
    if (hwCnots)  hwCnots.textContent  = n === 3 ? "~60 - 90"  : (n === 4 ? "~100 - 160" : "~180 - 280");
}

/**
 * Handle form submission — POST /api/solve
 */
async function handleFormSubmit(e) {
    e.preventDefault();

    const nCanals = parseInt(document.getElementById("nCanalsSelect").value);
    const scenario = document.querySelector('input[name="scenario"]:checked').value;
    const pCheckboxes = document.querySelectorAll('input[name="p_list"]:checked');
    const pList = Array.from(pCheckboxes).map(cb => parseInt(cb.value));
    const seed = parseInt(document.getElementById("seedInput").value) || 42;

    if (pList.length === 0) {
        alert("Please select at least one QAOA depth p (e.g., p=1).");
        return;
    }

    const payload = {
        n_canals: nCanals,
        scenario: scenario,
        p_list: pList,
        seed: seed
    };

    showLoading(true, "Simulating Quantum QAOA Engine...", `Solving for ${nCanals} canals (${nCanals * 3} qubits), ${scenario} scenario.`);

    try {
        const res = await fetch(`${API_BASE}/solve`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.error || "Solver failed");
        }

        const data = await res.json();
        renderDashboard(data);
    } catch (err) {
        alert("Backend request failed: " + err.message + "\n\nMake sure the backend is running at http://localhost:5000");
    } finally {
        showLoading(false);
    }
}

/**
 * Quick Demo Trigger (N=4, p=1)
 */
async function runDemo() {
    showLoading(true, "Running Quick Demo (N=4, p=1)...", "Executing fast 12-qubit evaluation (~5 seconds)");
    try {
        const res = await fetch(`${API_BASE}/demo`, { method: "GET" });
        if (!res.ok) throw new Error("Demo route failed");
        const data = await res.json();
        renderDashboard(data);
    } catch (err) {
        alert("Demo failed: " + err.message);
    } finally {
        showLoading(false);
    }
}

/**
 * Loading Banner Toggle
 */
function showLoading(show, title = "", sub = "") {
    const banner = document.getElementById("loadingBanner");
    const runBtn = document.getElementById("runBtn");

    if (show) {
        document.getElementById("loadingTitle").textContent = title;
        document.getElementById("loadingSub").textContent = sub;
        banner.classList.remove("hidden");
        runBtn.disabled = true;
    } else {
        banner.classList.add("hidden");
        runBtn.disabled = false;
    }
}

/**
 * Master Render Function for API Data
 */
function renderDashboard(data) {
    const results = data.results;
    const bf = results.brute_force;

    // Update Scenario Badge
    document.getElementById("scenarioBadge").textContent = `Scenario: ${data.scenario} (${data.supply} Units)`;

    // 1. KPI Cards
    if (bf) {
        document.getElementById("kpiBenefit").textContent = `${bf.benefit.toFixed(1)} Units`;
        document.getElementById("kpiOptimal").textContent = `Ground Truth (E = ${bf.energy})`;
    }

    // QAOA p=3 or max p ratio
    const qaoaKeys = Object.keys(results.qaoa || {}).sort();
    let maxPKey = qaoaKeys[qaoaKeys.length - 1];
    if (maxPKey && results.qaoa[maxPKey]) {
        const maxQaoa = results.qaoa[maxPKey];
        const ratio = (maxQaoa.approx_ratio * 100).toFixed(1);
        document.getElementById("kpiRatio").textContent = `${ratio}%`;
        document.getElementById("kpiFeasibility").textContent = `Feasibility: ${(maxQaoa.feasibility_rate * 100).toFixed(0)}%`;
    }

    // Optimal allocation metrics for fairness & min flow
    const optAlloc = (bf && bf.allocation) ? bf.allocation : null;
    if (optAlloc) {
        document.getElementById("kpiFairness").textContent = optAlloc.fairness_gap !== null ? optAlloc.fairness_gap.toFixed(2) : "0.00";
        document.getElementById("kpiMinFlow").textContent = `${optAlloc.min_flow_violations} Violations`;
    }

    // 2. Algorithm Benchmark Table
    renderResultsTable(results);

    // 3. Canal Allocation Grid (from Brute Force / Optimal solution)
    if (optAlloc && optAlloc.canals) {
        renderCanalGrid(optAlloc.canals);
    }

    // 4. Convergence Chart
    renderConvergenceChart(results.qaoa, bf ? bf.benefit : null);
}

/**
 * Populate Benchmark Table
 */
function renderResultsTable(results) {
    const tbody = document.getElementById("resultsTbody");
    tbody.innerHTML = "";

    const rows = [];

    // Brute Force Row
    if (results.brute_force) {
        rows.push({
            name: "Brute Force (Ground Truth)",
            data: results.brute_force,
            isOptimal: true,
            isQaoa: false
        });
    }

    // Greedy Row
    if (results.greedy) {
        rows.push({
            name: "Greedy Heuristic",
            data: results.greedy,
            isOptimal: false,
            isQaoa: false
        });
    }

    // Sim Anneal Row
    if (results.sim_anneal) {
        rows.push({
            name: "Simulated Annealing",
            data: results.sim_anneal,
            isOptimal: false,
            isQaoa: false
        });
    }

    // QAOA Rows
    if (results.qaoa) {
        Object.keys(results.qaoa).forEach(pKey => {
            rows.push({
                name: `QAOA (${pKey.toUpperCase()})`,
                data: results.qaoa[pKey],
                isOptimal: false,
                isQaoa: true
            });
        });
    }

    rows.forEach(r => {
        const d = r.data;
        const tr = document.createElement("tr");
        if (r.isOptimal) tr.classList.add("optimal-row");
        if (r.isQaoa) tr.classList.add("qaoa-row");

        const feasBadge = d.feasible
            ? `<span class="badge-tag badge-success">Feasible</span>`
            : `<span class="badge-tag badge-danger">Infeasible</span>`;

        const minFlowMet = (d.allocation && d.allocation.min_flow_violations === 0)
            ? `<span class="badge-tag badge-success">Met (0)</span>`
            : `<span class="badge-tag badge-warning">${d.allocation ? d.allocation.min_flow_violations : 0} Violated</span>`;

        tr.innerHTML = `
            <td><strong>${r.name}</strong></td>
            <td>${d.benefit ? d.benefit.toFixed(1) : "—"}</td>
            <td>${d.energy !== null ? d.energy.toFixed(4) : "—"}</td>
            <td>${d.opt_gap !== null ? d.opt_gap.toFixed(4) : "0.0000"}</td>
            <td>${d.approx_ratio !== null ? (d.approx_ratio * 100).toFixed(1) + "%" : "100.0%"}</td>
            <td>${feasBadge}</td>
            <td>${d.fairness_gap !== null ? d.fairness_gap.toFixed(2) : "—"}</td>
            <td>${minFlowMet}</td>
            <td>${d.runtime_s ? d.runtime_s.toFixed(3) + "s" : "<0.001s"}</td>
        `;

        tbody.appendChild(tr);
    });
}

/**
 * Render Canal Release Schedule Grid
 */
function renderCanalGrid(canals) {
    const grid = document.getElementById("canalScheduleGrid");
    grid.innerHTML = "";

    canals.forEach(c => {
        const card = document.createElement("div");
        card.className = `canal-card type-${c.stakeholder}`;

        const isMun = c.stakeholder === "municipal";
        const icon = isMun ? "🏙️" : "🌾";

        card.innerHTML = `
            <div class="canal-header">
                <span>Canal #${c.id} (${c.position})</span>
                <span>${icon}</span>
            </div>
            <div class="canal-title">${c.canal_type}</div>
            <div class="canal-level-badge">Release: ${c.level} (${c.units} Units)</div>
            <div class="canal-meta">
                <span>Benefit: +${c.benefit}</span>
                <span>Min Flow Req: ${c.min_flow_required} Unit (${c.min_flow_met ? "✅ Met" : "❌ Violated"})</span>
            </div>
        `;

        grid.appendChild(card);
    });
}

/**
 * Render QAOA Depth Convergence Chart using Chart.js
 */
function renderConvergenceChart(qaoaResults, bfBenefit) {
    const ctx = document.getElementById("convergenceChart").getContext("2d");

    if (convergenceChart) {
        convergenceChart.destroy();
    }

    if (!qaoaResults || Object.keys(qaoaResults).length === 0) {
        return;
    }

    const labels = [];
    const ratios = [];
    const benefits = [];

    Object.keys(qaoaResults).forEach(pKey => {
        labels.push(pKey.toUpperCase());
        const item = qaoaResults[pKey];
        ratios.push((item.approx_ratio * 100).toFixed(1));
        benefits.push(item.benefit);
    });

    convergenceChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Approx Ratio (%)",
                    data: ratios,
                    borderColor: "#a855f7",
                    backgroundColor: "rgba(168, 85, 247, 0.15)",
                    borderWidth: 3,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 6,
                    pointBackgroundColor: "#a855f7"
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: "#cbd5e1", font: { family: "Outfit" } }
                }
            },
            scales: {
                y: {
                    min: 50,
                    max: 105,
                    grid: { color: "#334155" },
                    ticks: { color: "#94a3b8" }
                },
                x: {
                    grid: { color: "#334155" },
                    ticks: { color: "#94a3b8" }
                }
            }
        }
    });
}
