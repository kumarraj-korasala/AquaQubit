/**
 * app.js — Client-Side Logic for CWC / KGBO Command Area Water Release Decision Support System
 */

const API_BASE = window.location.protocol.startsWith('http')
    ? `${window.location.origin}/api`
    : 'http://localhost:5000/api';

let currentScheduleData = null;

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
    checkHealth();
    // Auto-load default schedule on startup
    fetchSchedule(5, "Normal", 2, 42);
});

/**
 * Check backend connectivity
 */
async function checkHealth() {
    const statusEl = document.getElementById("apiStatus");
    try {
        const res = await fetch(`${API_BASE}/health`);
        if (res.ok) {
            statusEl.classList.add("connected");
            statusEl.querySelector(".status-text").textContent = "Engine Online";
        } else {
            throw new Error("HTTP " + res.status);
        }
    } catch (err) {
        statusEl.classList.remove("connected");
        statusEl.querySelector(".status-text").textContent = "Offline Mode";
    }
}

/**
 * Form Submit Handler — POST /api/schedule
 */
function handleScheduleSubmit(e) {
    e.preventDefault();
    const nCanals = parseInt(document.getElementById("nCanalsSelect").value);
    const scenario = document.querySelector('input[name="scenario"]:checked').value;
    const pDepth = parseInt(document.getElementById("pDepthSelect").value);
    const seed = parseInt(document.getElementById("seedInput").value) || 42;

    fetchSchedule(nCanals, scenario, pDepth, seed);
}

/**
 * Fetch Water Release Schedule from API
 */
async function fetchSchedule(nCanals, scenario, pDepth, seed) {
    showLoading(true);
    try {
        const res = await fetch(`${API_BASE}/schedule`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                n_canals: nCanals,
                scenario: scenario,
                p_depth: pDepth,
                seed: seed
            })
        });

        if (!res.ok) throw new Error("Schedule generation failed");
        const json = await res.json();
        
        if (json.success && json.data) {
            currentScheduleData = json.data;
            renderDashboard(json.data);
        }
    } catch (err) {
        alert("Failed to generate water release schedule: " + err.message);
    } finally {
        showLoading(false);
    }
}

/**
 * Loading Banner State
 */
function showLoading(show) {
    const banner = document.getElementById("loadingBanner");
    const btn = document.getElementById("scheduleBtn");
    if (show) {
        banner.classList.remove("hidden");
        btn.disabled = true;
    } else {
        banner.classList.add("hidden");
        btn.disabled = false;
    }
}

/**
 * Render Master Dashboard Data
 */
function renderDashboard(data) {
    // 1. Update KPI Summary Header
    document.getElementById("kpiSupply").textContent = `${data.reservoir_supply_available_tmc} TMC`;
    document.getElementById("kpiScenarioLabel").textContent = data.scenario;

    document.getElementById("kpiAllocated").textContent = `${data.total_water_allocated_tmc} TMC`;
    document.getElementById("kpiEfficiency").textContent = `${data.water_utilization_efficiency_pct}% Efficiency (${data.reservoir_spill_waste_tmc} TMC Waste)`;

    document.getElementById("kpiEquity").textContent = data.jains_equity_index.toFixed(2);
    document.getElementById("kpiEquitySub").textContent = data.jains_equity_index >= 0.85 ? "Optimal Equity (Zero Starvation)" : "Sub-Optimal Equity";

    document.getElementById("kpiConflict").textContent = data.conflict_risk_level.split(" ")[0];
    document.getElementById("kpiViolations").textContent = `${data.min_flow_violations_count} Min-Flow Violations`;

    // 2. Render Official Water Release Schedule Table
    renderScheduleTable(data.schedule);

    // 3. Render Network Flow Visual Map
    renderNetworkFlowGrid(data.schedule);

    // 4. Update Solver Info
    if (data.solver_info) {
        const info = data.solver_info;
        document.getElementById("solverInfoText").textContent = 
            `Engine: ${info.engine} | Qubits: ${info.n_qubits} | Circuit Depth: p=${info.circuit_depth_p} | Runtime: ${info.runtime_seconds}s | Ising Energy: ${info.energy_score}`;
    }
}

/**
 * Render Release Order Table Rows
 */
function renderScheduleTable(schedule) {
    const tbody = document.getElementById("scheduleTbody");
    tbody.innerHTML = "";

    schedule.forEach(row => {
        const tr = document.createElement("tr");

        const minBadge = row.min_flow_met 
            ? `<span class="badge-tag badge-success">✅ Met (${row.min_flow_required_tmc} TMC)</span>`
            : `<span class="badge-tag badge-danger">❌ Violated</span>`;

        tr.innerHTML = `
            <td><strong>${row.canal_name}</strong></td>
            <td><span class="badge-tag badge-cwc">${row.zone}</span></td>
            <td>${row.target_use}</td>
            <td><strong>${row.assigned_level}</strong></td>
            <td><strong>${row.allocated_units_tmc} TMC</strong></td>
            <td>${row.flow_rate_cusecs.toLocaleString()} cusecs</td>
            <td>${row.gate_opening_pct}%</td>
            <td>${minBadge}</td>
            <td>+${row.benefit_score}</td>
        `;
        tbody.appendChild(tr);
    });
}

/**
 * Render Canal Flow Visual Map
 */
function renderNetworkFlowGrid(schedule) {
    const grid = document.getElementById("networkFlowGrid");
    grid.innerHTML = "";

    schedule.forEach(row => {
        const card = document.createElement("div");
        const zoneClass = row.zone.toLowerCase().includes("head") ? "zone-head" : (row.zone.toLowerCase().includes("middle") ? "zone-middle" : "zone-tail");
        card.className = `flow-card ${zoneClass}`;

        const isMun = row.stakeholder === "municipal";
        const icon = isMun ? "🏙️" : "🌾";

        card.innerHTML = `
            <div class="flow-title">${icon} ${row.canal_name.split("(")[0]}</div>
            <div class="flow-units">${row.allocated_units_tmc} TMC</div>
            <div class="flow-meta">
                <span>Rate: ${row.flow_rate_cusecs.toLocaleString()} cusecs</span>
                <span>Gate: ${row.gate_opening_pct}% Open</span>
            </div>
        `;
        grid.appendChild(card);
    });
}

/**
 * CSV Release Order Exporter for CWC/KGBO Officials
 */
function exportScheduleCSV() {
    if (!currentScheduleData || !currentScheduleData.schedule) {
        alert("No schedule data available to export.");
        return;
    }

    const rows = [
        ["Canal Name", "Zone", "Stakeholder", "Target Use", "Assigned Level", "Allocated TMC", "Flow Rate (Cusecs)", "Gate Opening %", "Min Flow Met", "Utility Score"]
    ];

    currentScheduleData.schedule.forEach(item => {
        rows.push([
            `"${item.canal_name}"`,
            `"${item.zone}"`,
            `"${item.stakeholder}"`,
            `"${item.target_use}"`,
            `"${item.assigned_level}"`,
            item.allocated_units_tmc,
            item.flow_rate_cusecs,
            item.gate_opening_pct,
            item.min_flow_met ? "Yes" : "No",
            item.benefit_score
        ]);
    });

    const csvContent = "data:text/csv;charset=utf-8," + rows.map(e => e.join(",")).join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `CWC_Water_Release_Order_${currentScheduleData.scenario}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
