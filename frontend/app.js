/**
 * app.js — AquaQubit Client-Side Engine & Chart.js Visualizer
 * Color Palette:
 *   --stormy-teal:    #006d77
 *   --pearl-aqua:     #83c5be
 *   --alice-blue:     #edf6f9
 *   --almond-silk:    #ffddd2
 *   --tangerine-dream: #e29578
 */

const API_BASE = window.location.protocol.startsWith('http')
    ? `${window.location.origin}/api`
    : 'http://localhost:5000/api';

let currentScheduleData = null;
let allocationChartInstance = null;
let equityChartInstance = null;

const REGION_SUPPLY_DEFAULTS = {
    "krishna_godavari": 10.0,
    "kaveri_basin": 8.0,
    "narmada_command": 12.0,
    "custom": 9.0
};

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
    checkHealth();
    fetchSchedule(5, 10.0, 2, 42, "krishna_godavari");
});

function onRegionChange() {
    const key = document.getElementById("regionSelect").value;
    const supplyInput = document.getElementById("supplyInput");
    if (REGION_SUPPLY_DEFAULTS[key]) {
        supplyInput.value = REGION_SUPPLY_DEFAULTS[key].toFixed(1);
    }
}

async function checkHealth() {
    const statusEl = document.getElementById("apiStatus");
    try {
        const res = await fetch(`${API_BASE}/health`);
        if (res.ok) {
            statusEl.classList.add("connected");
            statusEl.querySelector(".status-text").textContent = "Engine Ready";
        }
    } catch (err) {
        statusEl.classList.remove("connected");
        statusEl.querySelector(".status-text").textContent = "Offline Mode";
    }
}

function handleScheduleSubmit(e) {
    e.preventDefault();
    const regionKey = document.getElementById("regionSelect").value;
    const supplyTmc = parseFloat(document.getElementById("supplyInput").value) || 10.0;
    const nCanals   = parseInt(document.getElementById("nCanalsSelect").value);
    const pDepth    = parseInt(document.getElementById("pDepthSelect").value);
    const seed      = parseInt(document.getElementById("seedInput").value) || 42;

    fetchSchedule(nCanals, supplyTmc, pDepth, seed, regionKey);
}

async function fetchSchedule(nCanals, supplyTmc, pDepth, seed, regionKey) {
    showLoading(true);
    try {
        const res = await fetch(`${API_BASE}/schedule`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                n_canals: nCanals,
                supply_tmc: supplyTmc,
                p_depth: pDepth,
                seed: seed,
                region_key: regionKey
            })
        });

        if (!res.ok) throw new Error("Optimization failed");
        const json = await res.json();
        
        if (json.success && json.data) {
            currentScheduleData = json.data;
            renderDashboard(json.data);
        }
    } catch (err) {
        alert("Optimization failed: " + err.message);
    } finally {
        showLoading(false);
    }
}

function showLoading(show) {
    const banner = document.getElementById("loadingBanner");
    const btn    = document.getElementById("scheduleBtn");
    if (show) {
        banner.classList.remove("hidden");
        btn.disabled = true;
    } else {
        banner.classList.add("hidden");
        btn.disabled = false;
    }
}

function renderDashboard(data) {
    // 1. KPI Cards
    document.getElementById("kpiSupply").textContent = `${data.available_supply_tmc.toFixed(1)} TMC`;
    document.getElementById("kpiRegionName").textContent = data.region_name;

    document.getElementById("kpiAllocated").textContent = `${data.total_allocated_tmc.toFixed(1)} TMC`;
    document.getElementById("kpiEfficiency").textContent = `${data.water_efficiency_pct.toFixed(1)}% Water Efficiency`;

    document.getElementById("kpiEquity").textContent = data.jains_equity_index.toFixed(2);
    document.getElementById("kpiEquitySub").textContent = data.equity_status;

    document.getElementById("kpiUtility").textContent = data.total_utility_score.toFixed(1);
    document.getElementById("kpiViolations").textContent = `${data.min_flow_violations} Floor Violations`;

    // 2. Schedule Table
    renderScheduleTable(data.schedule);

    // 3. Render Visual Charts
    renderAllocationChart(data.schedule);
    renderGateChart(data.schedule);

    // 4. Optimization Meta
    if (data.optimization_meta) {
        const meta = data.optimization_meta;
        document.getElementById("solverInfoText").textContent = 
            `Engine: ${meta.engine} | Qubits: ${meta.n_qubits} | Depth: p=${meta.circuit_depth_p} | Runtime: ${meta.runtime_seconds}s | Ising Energy: ${meta.ising_energy}`;
    }
}

function renderScheduleTable(schedule) {
    const tbody = document.getElementById("scheduleTbody");
    tbody.innerHTML = "";

    schedule.forEach(row => {
        const tr = document.createElement("tr");
        const statusBadge = row.min_flow_met 
            ? `<span class="badge-tag badge-success">Passed (${row.min_flow_req_tmc} TMC)</span>`
            : `<span class="badge-tag badge-danger">Violated</span>`;

        tr.innerHTML = `
            <td><strong>Zone ${row.canal_id}</strong></td>
            <td>${row.canal_name}</td>
            <td>${row.reach_zone}</td>
            <td>${row.target_use}</td>
            <td><strong>${row.release_level}</strong></td>
            <td><strong>${row.allocated_tmc} TMC</strong></td>
            <td>${row.flow_cusecs.toLocaleString()} cusecs</td>
            <td>${row.gate_opening_pct}%</td>
            <td>${statusBadge}</td>
        `;
        tbody.appendChild(tr);
    });
}

/**
 * Chart 1: Allocated Volume vs Required Min Flow
 */
function renderAllocationChart(schedule) {
    const ctx = document.getElementById("allocationChart").getContext("2d");
    if (allocationChartInstance) allocationChartInstance.destroy();

    const labels = schedule.map(s => `Zone ${s.canal_id}`);
    const allocated = schedule.map(s => s.allocated_tmc);
    const required = schedule.map(s => s.min_flow_req_tmc);

    allocationChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Allocated Volume (TMC)",
                    data: allocated,
                    backgroundColor: "#006d77",
                    borderRadius: 4
                },
                {
                    label: "Required Floor (TMC)",
                    data: required,
                    backgroundColor: "#e29578",
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: "#003840", font: { family: "Inter", weight: "600" } } }
            },
            scales: {
                y: { beginAtZero: true, grid: { color: "#edf6f9" }, ticks: { color: "#2d4a52" } },
                x: { grid: { display: false }, ticks: { color: "#2d4a52" } }
            }
        }
    });
}

/**
 * Chart 2: Gate Opening % per Canal Zone
 */
function renderGateChart(schedule) {
    const ctx = document.getElementById("equityChart").getContext("2d");
    if (equityChartInstance) equityChartInstance.destroy();

    const labels = schedule.map(s => `Zone ${s.canal_id}`);
    const openings = schedule.map(s => s.gate_opening_pct);

    equityChartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Gate Opening (% Capacity)",
                    data: openings,
                    borderColor: "#006d77",
                    backgroundColor: "rgba(131, 197, 190, 0.3)",
                    borderWidth: 3,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 6,
                    pointBackgroundColor: "#e29578"
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: "#003840", font: { family: "Inter", weight: "600" } } }
            },
            scales: {
                y: { min: 0, max: 100, grid: { color: "#edf6f9" }, ticks: { color: "#2d4a52" } },
                x: { grid: { display: false }, ticks: { color: "#2d4a52" } }
            }
        }
    });
}

function exportScheduleCSV() {
    if (!currentScheduleData || !currentScheduleData.schedule) {
        alert("No schedule data available to export.");
        return;
    }

    const rows = [
        ["Zone ID", "Canal Reach Name", "Position", "Target Use", "Release Level", "Allocated TMC", "Flow Rate (Cusecs)", "Gate Opening %", "Min Flow Status"]
    ];

    currentScheduleData.schedule.forEach(r => {
        rows.push([
            r.canal_id,
            `"${r.canal_name}"`,
            `"${r.reach_zone}"`,
            `"${r.target_use}"`,
            `"${r.release_level}"`,
            r.allocated_tmc,
            r.flow_cusecs,
            r.gate_opening_pct,
            r.min_flow_met ? "Passed" : "Violated"
        ]);
    });

    const csvContent = "data:text/csv;charset=utf-8," + rows.map(e => e.join(",")).join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `AquaQubit_Release_Schedule_${currentScheduleData.region_name.replace(/\s+/g, '_')}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
