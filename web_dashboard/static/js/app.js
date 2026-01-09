/**
 * InnoMine Dashboard Controller
 * Handles data fetching, UI updates, and interactions.
 */

// Configuration
const REFRESH_INTERVAL_MS = 2000;
let chartInstance = null;
let currentMinerId = null;

// DOM Elements
const els = {
    clockTime: document.getElementById('clock-time'),
    clockDate: document.getElementById('clock-date'),
    healthGrid: document.getElementById('site-health-grid'),
    unit1Grid: document.getElementById('unit1-grid'),
    workersGrid: document.getElementById('workers-grid'),
    alertList: document.getElementById('alert-list'),
    mapContainer: document.getElementById('map-container'),
    
    // Config
    buzzDur: document.getElementById('buzz-duration'),
    buzzBeeps: document.getElementById('buzz-beeps'),
    ledToggle: document.getElementById('led-toggle'),
    durVal: document.getElementById('dur-val'),
    beepVal: document.getElementById('beep-val'),
    saveBtn: document.getElementById('save-config-btn'),
    
    // Modal
    modal: document.getElementById('worker-modal'),
    modalTitle: document.getElementById('modal-title'),
    modalStats: document.getElementById('modal-stats-grid'),
    closeModal: document.getElementById('close-modal'),
    chartCanvas: document.getElementById('worker-chart')
};

// --- Initialization ---

window.onerror = function(msg, url, line, col, error) {
   const el = document.getElementById('site-health-grid');
   if (el) el.innerHTML = `<div style="grid-column:1/-1; color:red; padding:10px;">
      <strong>JS Error:</strong> ${msg}<br>
      <small>${url}:${line}</small>
   </div>`;
};

async function init() {
    updateClock();
    setInterval(updateClock, 1000);
    
    // Load initial config
    loadConfig();
    
    // Start polling
    fetchDashboardData();
    setInterval(fetchDashboardData, REFRESH_INTERVAL_MS);
    
    // Load alarms separately
    fetchAlarms();
    setInterval(fetchAlarms, 5000);
    
    // Event Listeners
    els.buzzDur.addEventListener('input', (e) => els.durVal.textContent = e.target.value);
    els.buzzBeeps.addEventListener('input', (e) => els.beepVal.textContent = e.target.value);
    els.saveBtn.addEventListener('click', saveConfig);
    
    els.closeModal.addEventListener('click', () => {
        els.modal.classList.add('hidden');
        currentMinerId = null;
    });
    
    // Close modal on outside click
    els.modal.addEventListener('click', (e) => {
        if (e.target === els.modal) {
            els.modal.classList.add('hidden');
            currentMinerId = null;
        }
    });
}

// --- Data Fetching & Rendering ---

async function fetchDashboardData() {
    try {
        const res = await fetch('/api/dashboard');
        const data = await res.json();
        
        renderHealth(data.health);
        renderUnit1(data.unit1_raw);
        renderWorkers(data.miners);
        renderMap(data.miners);
        
        // Update modal if open
        if (currentMinerId && !els.modal.classList.contains('hidden')) {
            const miner = data.miners.find(m => m.id === currentMinerId);
            if (miner) updateModalStats(miner);
        }
        
    } catch (err) {
        console.error("Dashboard fetch error:", err);
        if (els.healthGrid) {
             els.healthGrid.innerHTML = `<div style="grid-column:1/-1; color:#ef4444; padding:1rem;">
                <strong>Connection Error:</strong> ${err.message}<br>
                <small>Ensure run_all.py is running and port 8000 is open.</small>
             </div>`;
        }
    }
}

async function fetchAlarms() {
    try {
        const res = await fetch('/api/alarms');
        const alarms = await res.json();
        renderAlarms(alarms);
    } catch (e) {
        console.error("Error fetching metrics:", e);
        const el = document.getElementById("health-panel");
        if (el) {
             el.innerHTML = `<div style="color:orange; padding:10px;">Connection Error: ${e.message}. Backend may be starting...</div>`;
        }
    }
}

// --- Renderers ---

function renderHealth(health) {
    const metrics = [
        { label: "Active Workers", value: health.active_workers, unit: "", status: "safe" },
        { label: "Avg CO₂", value: health.avg_co2, unit: "ppm", status: getStatus(health.avg_co2, 'co2') },
        { label: "Avg Temp", value: health.avg_temp, unit: "°C", status: getStatus(health.avg_temp, 'temp') },
        { label: "Site Safety", value: health.site_safety_score + "%", unit: "", status: health.site_safety_score > 90 ? "safe" : "warning" },
        { label: "Active Alerts", value: health.active_alerts, unit: "", status: health.active_alerts > 0 ? "danger" : "safe" }
    ];
    
    els.healthGrid.innerHTML = metrics.map(m => `
        <div class="metric-card">
            <div class="metric-val status-${m.status}">${m.value}<span style="font-size:0.8rem; color:#64748b; margin-left:2px">${m.unit}</span></div>
            <div class="metric-label">${m.label}</div>
        </div>
    `).join('');
}

function renderUnit1(data) {
    if (!data || Object.keys(data).length === 0) {
        els.unit1Grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:1rem; color:#64748b">Connecting to sensors...</div>';
        return;
    }
    
    const metrics = [
        { label: "CO₂ Level", value: data.co2_ppm || "--", unit: "ppm", status: getStatus(data.co2_ppm, 'co2') },
        { label: "Temperature", value: data.temperature_c ? data.temperature_c.toFixed(1) : "--", unit: "°C", status: getStatus(data.temperature_c, 'temp') },
        { label: "Humidity", value: data.humidity_rh ? data.humidity_rh.toFixed(1) : "--", unit: "%RH", status: "safe" },
        { label: "Motion", value: data.motion_g ? data.motion_g.toFixed(3) : "--", unit: "g", status: "safe" }
    ];
    
    els.unit1Grid.innerHTML = metrics.map(m => `
         <div class="metric-card">
            <div class="metric-val status-${m.status}">${m.value}<span style="font-size:0.8rem; color:#64748b; margin-left:2px">${m.unit}</span></div>
            <div class="metric-label">${m.label}</div>
        </div>
    `).join('');
}

// --- Restored Renderers & Logic ---

function renderWorkers(miners) {
    if (!els.workersGrid) return;
    els.workersGrid.innerHTML = miners.map(m => `
        <div class="worker-card status-${m.status}" onclick="openWorkerModal(${m.id})">
            <div class="worker-header">
                <span class="worker-id">${m.name}</span>
                <span class="status-dot"></span>
            </div>
            <div class="worker-body">
                <div>${m.location}</div>
                <div style="font-size:0.8rem; opacity:0.7">${m.shift} Shift</div>
            </div>
             <div class="worker-footer">
                <span>🔋 ${m.battery}%</span>
                <span>❤ ${m.heart_rate}</span>
            </div>
        </div>
    `).join('');
}

function renderAlarms(alarms) {
    if (!els.alertList) return;
    if (alarms.length === 0) {
        els.alertList.innerHTML = '<div style="padding:1rem; color:#64748b; text-align:center">No active alerts</div>';
        return;
    }
    els.alertList.innerHTML = alarms.map(a => `
        <div class="alert-item severity-${a.severity}">
            <div class="alert-header">
                <strong>${a.sensor}</strong>
                <span style="font-size:0.8rem">${a.triggered_at}</span>
            </div>
            <div>${a.message}</div>
        </div>
    `).join('');
}

function renderMap(miners) {
    if (!els.mapContainer) return;
    
    // Ensure background grid exists
    if (!els.mapContainer.querySelector('.map-grid-bg')) {
         els.mapContainer.innerHTML = '<div class="map-grid-bg"></div>';
    }
    
    // Remove old dots
    const oldDots = els.mapContainer.querySelectorAll('.map-dot');
    oldDots.forEach(d => d.remove());
    
    miners.forEach(m => {
        const dot = document.createElement('div');
        dot.className = `map-dot status-${m.status}`;
        dot.title = `${m.name}: ${m.location}`;
        
        // Randomize position based on Miner ID
        let top=50, left=50;
        if (m.location.includes("Section A")) { top = 20; left = 20; }
        else if (m.location.includes("Section B")) { top = 20; left = 80; }
        else if (m.location.includes("Section C")) { top = 80; left = 20; }
        else { top = 80; left = 80; }
        
        // Jitter
        top += (m.id * 5) % 15;
        left += (m.id * 7) % 15;
        
        dot.style.top = top + '%';
        dot.style.left = left + '%';
        
        dot.onclick = () => openWorkerModal(m.id);
        
        els.mapContainer.appendChild(dot);
    });
}

// --- Config Logic ---

async function loadConfig() {
    try {
        const res = await fetch('/api/config');
        const config = await res.json();
        
        if (els.buzzDur) {
            els.buzzDur.value = config.duration_s;
            els.durVal.textContent = config.duration_s;
        }
        if (els.buzzBeeps) {
            els.buzzBeeps.value = config.beeps;
            els.beepVal.textContent = config.beeps;
        }
        if (els.alarmPoll) {
            els.alarmPoll.value = config.poll_interval_s;
            els.pollVal.textContent = config.poll_interval_s;
        }
        if (els.ledToggle) els.ledToggle.checked = config.led_enabled;
    } catch (err) {
        console.error("Config load error:", err);
    }
}

async function saveConfig() {
    const config = {
        duration_s: parseFloat(els.buzzDur.value),
        beeps: parseInt(els.buzzBeeps.value),
        poll_interval_s: parseFloat(els.alarmPoll.value),
        led_enabled: els.ledToggle.checked
    };
    
    els.saveBtn.textContent = "Saving...";
    els.saveBtn.disabled = true;
    
    try {
        const res = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        if (res.ok) {
            els.saveBtn.textContent = "Saved!";
            setTimeout(() => {
                els.saveBtn.textContent = "Update Config";
                els.saveBtn.disabled = false;
            }, 2000);
        } else {
            throw new Error(await res.text());
        }
    } catch (err) {
        alert("Failed to save: " + err.message);
        els.saveBtn.textContent = "Error";
        els.saveBtn.disabled = false;
    }
}

// Global modal opener
window.openWorkerModal = function(id) {
    currentMinerId = id;
    if (els.modalStats) els.modalStats.innerHTML = 'Loading...';
    if (els.modal) els.modal.classList.remove('hidden');
    if (els.modalTitle) els.modalTitle.textContent = `Worker 00${id}`;
    loadChart(id);
};

function updateModalStats(m) {
    const isSim = m.id === 1; // Assuming ID 1 is the 'Live' one with some sim parts
    const items = [
        { l: "Heart Rate", v: m.heart_rate + (isSim ? " <span style='font-size:0.7em; opacity:0.6'>(Sim)</span>" : ""), u: "bpm" },
        { l: "Body Temp", v: m.body_temp, u: "°C" },
        { l: "Env Humidity", v: m.humidity || "--", u: "%" },
        { l: "Motion", v: m.motion || "0", u: "g" },
        { l: "CO₂ Level", v: m.co2_ppm || "--", u: "ppm" },
        { l: "Battery", v: m.battery, u: "%" }
    ];
    
    els.modalStats.innerHTML = items.map(x => `
        <div class="metric-card">
             <div class="metric-val">${x.v}<span style="font-size:0.6em; color:#888; margin-left:4px">${x.u}</span></div>
             <div class="metric-label">${x.l}</div>
        </div>
    `).join('');
}

async function loadChart(id) {
    const res = await fetch(`/api/history/${id}`);
    const data = await res.json();
    
    const ctx = els.chartCanvas.getContext('2d');
    
    if (chartInstance) {
        chartInstance.destroy();
    }
    
    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: 'CO₂ (ppm)',
                    data: data.co2,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y'
                },
                {
                    label: 'Temp (°C)',
                    data: data.temp,
                    borderColor: '#3b82f6',
                    borderWidth: 2,
                    tension: 0.4,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    grid: { color: 'rgba(255,255,255,0.05)' }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    grid: { drawOnChartArea: false }
                }
            },
            plugins: {
                legend: { labels: { color: '#94a3b8' } }
            }
        }
    });
}

// --- Utils ---

function updateClock() {
    const now = new Date();
    els.clockTime.textContent = now.toLocaleTimeString('en-US', {hour12: false});
    els.clockDate.textContent = now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

function getStatus(val, type) {
    if (val === null || val === undefined) return "safe";
    if (type === 'co2') {
        if (val >= 1000) return 'danger';
        if (val >= 800) return 'warning';
    }
    if (type === 'temp') {
        if (val >= 38) return 'danger';
        if (val >= 37) return 'warning';
    }
    return "safe";
}

// Start app
init();
