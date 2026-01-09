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
    }
}

async function fetchAlarms() {
    try {
        const res = await fetch('/api/alarms');
        const alarms = await res.json();
        renderAlarms(alarms);
    } catch (err) {
        console.error("Alarm fetch error:", err);
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
        { label: "Motion X", value: data.accel_x_g ? data.accel_x_g.toFixed(3) : "--", unit: "g", status: "safe" }
    ];
    
    els.unit1Grid.innerHTML = metrics.map(m => `
         <div class="metric-card">
            <div class="metric-val status-${m.status}">${m.value}<span style="font-size:0.8rem; color:#64748b; margin-left:2px">${m.unit}</span></div>
            <div class="metric-label">${m.label}</div>
        </div>
    `).join('');
}

function renderWorkers(miners) {
    els.workersGrid.innerHTML = miners.map(m => `
        <div class="worker-card ${m.status}" onclick="openWorkerDetails(${m.id})">
            <div class="w-header">
                <div>
                    <div class="w-name">${m.name} ${m.is_real_data ? '<span style="color:var(--accent-green); font-size:0.7em">● LIVE</span>' : ''}</div>
                    <div class="w-loc">${m.location}</div>
                </div>
                <div class="badge badge-${m.is_real_data ? 'live' : 'simulated'}">${m.status.toUpperCase()}</div>
            </div>
            <div class="w-stats">
                <span title="Heart Rate">❤️ ${m.heart_rate}</span>
                <span title="Body Temp">🌡️ ${m.body_temp}°</span>
                ${m.env_temp ? `<span title="Env Temp" style="color:var(--accent-cyan)">🌍 ${m.env_temp}°</span>` : ''}
                <span class="status-${getStatus(m.co2_ppm, 'co2')}" title="CO2">💨 ${m.co2_ppm || '--'}</span>
            </div>
        </div>
    `).join('');
}

function renderAlarms(alarms) {
    if (alarms.length === 0) {
        els.alertList.innerHTML = '<div style="padding:1rem; text-align:center; color:#64748b">No active alerts</div>';
        return;
    }
    
    els.alertList.innerHTML = alarms.map(a => `
        <div class="alert-item ${a.severity}">
            <div class="alert-info">
                <h4>${a.metric} - ${a.sensor} ${a.is_simulated ? '<span style="font-size:0.6em; opacity:0.6">[SIM]</span>' : ''}</h4>
                <p>${a.message}</p>
            </div>
            <div class="alert-time">${a.triggered_at}</div>
        </div>
    `).join('');
}

function renderMap(miners) {
    // We want to preserve existing dots to allow transitions CSS
    // But for simplicity in this MVP, we re-render. A better approach is differencing.
    // Let's re-render but assume animations handle the "jump"
    
    // Clear existing dots but keep grid
    const dots = els.mapContainer.querySelectorAll('.map-dot');
    dots.forEach(d => d.remove());
    
    miners.forEach((m, i) => {
        // Calculate stable pseudo-random position based on ID if real pos mapping existed
        // Here we simulate movement slightly based on time if we wanted animation logic
        
        // Simulating simple movement around a base point
        const t = Date.now() / 1000;
        let baseX = 20 + (i % 4) * 20;
        let baseY = 30 + Math.floor(i / 4) * 30;
        
        // Add wander
        let x = baseX + Math.sin(t + i) * 2;
        let y = baseY + Math.cos(t + i * 2) * 2;
        
        const dot = document.createElement('div');
        dot.className = `map-dot ${m.status}`;
        dot.style.left = `${x}%`;
        dot.style.top = `${y}%`;
        dot.innerHTML = `<div class="map-tooltip">${m.name}</div>`;
        dot.onclick = () => openWorkerDetails(m.id);
        
        els.mapContainer.appendChild(dot);
    });
}

// --- Interactions ---

async function loadConfig() {
    try {
        const res = await fetch('/api/config');
        const cfg = await res.json();
        els.buzzDur.value = cfg.duration_s;
        els.durVal.textContent = cfg.duration_s;
        els.buzzBeeps.value = cfg.beeps;
        els.beepVal.textContent = cfg.beeps;
        els.ledToggle.checked = cfg.led_enabled;
    } catch (e) {
        console.error(e);
    }
}

async function saveConfig() {
    const payload = {
        duration_s: parseFloat(els.buzzDur.value),
        beeps: parseInt(els.buzzBeeps.value),
        led_enabled: els.ledToggle.checked
    };
    try {
        await fetch('/api/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        alert("Configuration updated!");
    } catch (e) {
        alert("Failed to save config");
    }
}

async function openWorkerDetails(id) {
    currentMinerId = id;
    els.modal.classList.remove('hidden');
    
    // Fetch miner data immediately from current cache or re-fetch would be better
    // For now, next poll updates it, but let's fetch history
    const res = await fetch('/api/dashboard'); // Get fresh single view
    const data = await res.json();
    const miner = data.miners.find(m => m.id === id);
    if(miner) {
        updateModalStats(miner);
        els.modalTitle.textContent = `Worker Details: ${miner.name}`;
    }
    
    loadChart(id);
}

function updateModalStats(m) {
    const items = [
        { l: "Heart Rate", v: m.heart_rate, u: "bpm" },
        { l: "Body Temp", v: m.body_temp, u: "°C" },
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
