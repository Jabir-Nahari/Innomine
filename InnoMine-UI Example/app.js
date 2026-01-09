// InnoMine Professional Dashboard

(function () {
  // Data will be available after scripts load
  let Data = null;

  // State
  const TARGET_MINE = "Mahd adh Dhahab (Gold)";
  let selectedSection =
    localStorage.getItem("innomine:selectedSection") || "ALL";
  let selectedShift = localStorage.getItem("innomine:selectedShift") || "ALL";
  let selectedStatus = localStorage.getItem("innomine:selectedStatus") || "ALL";
  let live = (localStorage.getItem("innomine:live") ?? "true") === "true";
  let muted = (localStorage.getItem("innomine:muted") ?? "true") === "true";
  let searchQuery = "";
  let viewMode = "sections"; // "sections" or "miners"
  const overallRiskSeries = [];
  const anomaliesFeed = [];
  let overallChart, sparklineChart, tickTimer, clockTimer;

  // Elements
  const el = (id) => document.getElementById(id);
  const sectionsGrid = el("sectionsGrid");
  const currentSectionTitle = el("currentSectionTitle");
  const currentSectionDesc = el("currentSectionDesc");
  const showAllSectionsBtn = el("showAllSectionsBtn");
  const shiftFilter = el("shiftFilter");
  const statusFilter = el("statusFilter");
  const searchInput = el("searchInput");
  const liveToggle = el("liveToggle");
  const communicateBtn = el("communicateBtn");
  const minersGrid = el("minersGrid");
  const insightsPanel = el("insightsPanel");
  const insightsContent = el("insightsContent");
  const insightsTime = el("insightsTime");
  const exportBtn = el("exportBtn");
  const screenshotBtn = el("screenshotBtn");
  const toast = el("toast");
  const beepAudio = el("beepAudio");
  const modal = el("modal");
  const modalClose = el("modalClose");

  // Setup
  function init() {
    // Check if data is available, if not wait a bit
    if (!window.InnoMineData) {
      setTimeout(init, 50);
      return;
    }

    // Assign data reference
    Data = window.InnoMineData;

    // Ensure we're in sections view initially
    viewMode = "sections";
    selectedSection = "ALL";

    renderSelectors();
    applySelectorValues();
    renderStats();
    renderSectionsGrid();
    renderMinersGrid();
    renderInsights();
    updateViewMode();
    bindEvents();
    updateClock();
    clockTimer = setInterval(updateClock, 1000);
    setLive(live);
    updateLiveButton();
  }

  // Renderers
  function renderSelectors() {
    // No-op: single mine MVP, no site/miner dropdowns
  }
  function applySelectorValues() {
    shiftFilter.value = selectedShift;
    statusFilter.value = selectedStatus;
  }

  function renderStats() {
    let minersForStats = [];
    if (selectedSection === "ALL") {
      minersForStats = Data.getMinersBySite(TARGET_MINE);
    } else {
      minersForStats = Data.getMinersBySection(selectedSection);
    }

    const totalMiners = minersForStats.length;
    const avgRisk =
      totalMiners > 0
        ? minersForStats.reduce((sum, m) => sum + m.risk, 0) / totalMiners
        : 0;
    const activeAlerts = anomaliesFeed.filter(
      (a) => Date.now() - a.timeMs < 10 * 60 * 1000
    ).length;

    el("kpiTotalMiners").textContent = String(totalMiners);
    el("kpiActiveAlerts").textContent = String(activeAlerts);
    el("kpiAvgRisk").textContent = getRiskLevelText(avgRisk);

    // Update mine overview stats
    renderMineOverview();
  }

  function renderMineOverview() {
    const miners = Data.getMinersBySite(TARGET_MINE);

    // Calculate average gas levels
    const avgCO = miners.reduce((sum, m) => sum + m.env.co, 0) / miners.length;
    const avgH2S =
      miners.reduce((sum, m) => sum + m.env.h2s, 0) / miners.length;
    const avgCH4 =
      miners.reduce((sum, m) => sum + m.env.ch4LEL, 0) / miners.length;
    const avgO2 = miners.reduce((sum, m) => sum + m.env.o2, 0) / miners.length;
    const avgNoise =
      miners.reduce((sum, m) => sum + m.env.dBA, 0) / miners.length;

    const coEl = el("mineCO");
    const h2sEl = el("mineH2S");
    const ch4El = el("mineCH4");
    const o2El = el("mineO2");
    const noiseEl = el("mineNoise");

    if (coEl) coEl.textContent = `${Math.round(avgCO)} ppm`;
    if (h2sEl) h2sEl.textContent = `${Math.round(avgH2S)} ppm`;
    if (ch4El) ch4El.textContent = `${Math.round(avgCH4)}%`;
    if (o2El) o2El.textContent = `${avgO2.toFixed(1)}%`;
    if (noiseEl) noiseEl.textContent = `${Math.round(avgNoise)} dBA`;
  }

  function renderSectionsGrid() {
    const container = document.getElementById("sectionsGrid");
    if (!container) return;
    if (!Data || !Data.getMineSections) {
      container.innerHTML =
        '<div style="text-align: center; padding: 2rem; color: #64748b; background: #1e293b; border-radius: 8px;">Loading data...</div>';
      return;
    }

    const sections = Data.getMineSections();

    container.innerHTML = "";

    // If no sections, show a message
    if (!sections || sections.length === 0) {
      container.innerHTML =
        '<div style="text-align: center; padding: 2rem; color: #64748b; background: #1e293b; border-radius: 8px;">No mine sections found</div>';
      return;
    }

    for (const section of sections) {
      const miners = Data.getMinersBySection
        ? Data.getMinersBySection(section)
        : [];

      const avgRisk =
        miners.length > 0
          ? miners.reduce((sum, m) => sum + m.risk, 0) / miners.length
          : 0;

      // Determine section status based on miners
      let sectionStatus = "normal";
      let hasWarning = miners.some((m) => getMinerStatus(m) === "WARNING");
      let hasDanger = miners.some((m) => getMinerStatus(m) === "DANGER");

      if (hasDanger) sectionStatus = "danger";
      else if (hasWarning) sectionStatus = "warning";

      const sectionCard = document.createElement("div");
      sectionCard.className = `section-card ${
        selectedSection === section ? "selected" : ""
      }`;
      sectionCard.innerHTML = `
        <div class="section-icon">🏗️</div>
        <div class="section-name">${section}</div>
        <div class="section-stats">
          <div class="section-miners">${miners.length} miners</div>
          <div class="section-status ${sectionStatus}">${sectionStatus}</div>
        </div>
      `;

      sectionCard.addEventListener("click", () => {
        selectedSection = section;
        viewMode = "miners";
        persistState();
        updateViewMode();
        renderMinersGrid();
        updateCurrentSectionDisplay();
      });

      container.appendChild(sectionCard);
    }
  }

  function updateViewMode() {
    const sectionsSection = document.querySelector(".mine-sections");
    const minersGrid = document.getElementById("minersGrid");
    const currentSection = document.querySelector(".current-section");

    if (viewMode === "sections") {
      if (sectionsSection) sectionsSection.style.display = "block";
      if (minersGrid) minersGrid.style.display = "none";
      if (currentSection) currentSection.style.display = "none";
    } else {
      if (sectionsSection) sectionsSection.style.display = "none";
      if (minersGrid) minersGrid.style.display = "grid";
      if (currentSection) currentSection.style.display = "flex";
    }
  }

  function updateCurrentSectionDisplay() {
    if (selectedSection === "ALL") {
      currentSectionTitle.textContent = "All Sections";
      currentSectionDesc.textContent = "Showing miners from all mine sections";
    } else {
      currentSectionTitle.textContent = selectedSection;
      currentSectionDesc.textContent = `Showing miners from ${selectedSection} section`;
    }
  }

  function getRiskLevelText(risk) {
    if (risk >= 70) return "High";
    if (risk >= 40) return "Medium";
    return "Low";
  }

  function renderMinersGrid() {
    let miners = [];

    if (selectedSection === "ALL") {
      miners = Data.getMinersBySite(TARGET_MINE);
    } else {
      miners = Data.getMinersBySection(selectedSection);
    }

    miners = miners
      .filter((m) => {
        const q = searchQuery.trim().toLowerCase();
        if (!q) return true;
        return (
          m.id.toLowerCase().includes(q) || m.name.toLowerCase().includes(q)
        );
      })
      .filter((m) => {
        if (selectedShift === "ALL") return true;
        return m.shift === selectedShift;
      })
      .filter((m) => {
        if (selectedStatus === "ALL") return true;
        const status = getMinerStatus(m);
        return status === selectedStatus;
      })
      .sort((a, b) => b.risk - a.risk);

    minersGrid.innerHTML = "";

    for (const miner of miners) {
      const status = getMinerStatus(miner);
      const statusClass = status.toLowerCase();
      const card = document.createElement("div");
      card.className = `miner-card status-${statusClass}`;
      card.innerHTML = `
        <div class="miner-card-header">
          <div class="miner-avatar">${miner.name.charAt(0)}</div>
          <div class="miner-info">
            <div class="miner-name">${miner.name}</div>
            <div class="miner-details">${miner.section} • ${
        miner.shift
      } Shift</div>
          </div>
          <div class="miner-status ${statusClass}">${status}</div>
        </div>
        <div class="miner-metrics">
          <div class="metric">
            <div class="metric-label">Heart Rate</div>
            <div class="metric-value">${miner.vitals.hr} BPM</div>
          </div>
          <div class="metric">
            <div class="metric-label">Temperature</div>
            <div class="metric-value">${miner.vitals.temp.toFixed(1)}°C</div>
          </div>
          <div class="metric">
            <div class="metric-label">Battery</div>
            <div class="metric-value">${Math.round(miner.battery)}%</div>
          </div>
          <div class="metric">
            <div class="metric-label">Risk Score</div>
            <div class="metric-value">${miner.risk}%</div>
          </div>
        </div>
        <div class="miner-last-update">
          Updated ${new Date(miner.lastUpdate).toLocaleTimeString()}
        </div>
        ${
          miner.battery < 30
            ? `<button class="call-btn" onclick="callMiner('${miner.id}')">📞 Call Miner</button>`
            : ""
        }
      `;
      card.addEventListener("click", () => openMinerModal(miner.id));
      minersGrid.appendChild(card);
    }
  }

  function getMinerStatus(miner) {
    if (isEmergency(miner)) return "DANGER";
    // Smooth warning noise: require sustained elevated risk
    const sustainedWarning =
      miner._history && miner._history.risk
        ? miner._history.risk.slice(-5).filter((r) => r >= 45).length >= 3
        : false;
    if (sustainedWarning || miner.risk >= 55) return "WARNING";
    return "NORMAL";
  }

  function renderInsights() {
    const miners = Data.getMinersBySite(TARGET_MINE);
    const totalMiners = miners.length;
    const normalMiners = miners.filter(
      (m) => getMinerStatus(m) === "NORMAL"
    ).length;
    const warningMiners = miners.filter(
      (m) => getMinerStatus(m) === "WARNING"
    ).length;
    const dangerMiners = miners.filter(
      (m) => getMinerStatus(m) === "DANGER"
    ).length;

    const insights = [];

    // Overall status insight
    if (dangerMiners > 0) {
      insights.push({
        priority: "danger",
        title: "Critical Safety Alert",
        message: `${dangerMiners} miner${
          dangerMiners > 1 ? "s" : ""
        } in immediate danger. Emergency evacuation recommended.`,
      });
    } else if (warningMiners > 0) {
      insights.push({
        priority: "warning",
        title: "Safety Monitoring Required",
        message: `${warningMiners} miner${
          warningMiners > 1 ? "s" : ""
        } showing elevated risk levels. Increased monitoring advised.`,
      });
    } else {
      insights.push({
        priority: "normal",
        title: "All Systems Normal",
        message:
          "All miners operating within safe parameters. Continue standard monitoring protocols.",
      });
    }

    // Battery insights
    const lowBatteryMiners = miners.filter((m) => m.battery < 30);
    if (lowBatteryMiners.length > 0) {
      insights.push({
        priority: "warning",
        title: "Battery Alert",
        message: `${lowBatteryMiners.length} miner${
          lowBatteryMiners.length > 1 ? "s" : ""
        } with low battery. Schedule equipment replacement.`,
      });
    }

    // Environmental insights
    const highNoiseMiners = miners.filter((m) => m.env.dBA > 95);
    if (highNoiseMiners.length > 0) {
      insights.push({
        priority: "warning",
        title: "Noise Exposure",
        message: `${highNoiseMiners.length} miner${
          highNoiseMiners.length > 1 ? "s" : ""
        } exposed to high noise levels. Consider hearing protection rotation.`,
      });
    }

    const gasAlerts = miners.filter(
      (m) => m.env.co > 50 || m.env.h2s > 10 || m.env.ch4LEL > 50
    );
    if (gasAlerts.length > 0) {
      insights.push({
        priority: "danger",
        title: "Gas Alert",
        message:
          "Elevated gas levels detected. Ventilation system check required.",
      });
    }

    // Render insights
    insightsContent.innerHTML = insights
      .map(
        (insight) => `
      <div class="insight-item">
        <div class="insight-priority priority-${insight.priority}">
          <span class="priority-dot"></span>
          <span>${insight.title}</span>
        </div>
        <p>${insight.message}</p>
      </div>
    `
      )
      .join("");

    insightsTime.textContent = `Updated ${new Date().toLocaleTimeString()}`;
  }

  // Realtime loop
  function tick() {
    const miners = Data.getMinersBySite(TARGET_MINE);
    for (const m of miners) {
      const anomaly = Data.randomizeTick(m);
      if (anomaly) {
        anomaliesFeed.unshift({
          ...anomaly,
          timeMs: Date.now(),
          miner: { id: m.id, name: m.name, site: m.site },
        });
        if (!muted)
          try {
            beepAudio.currentTime = 0;
            beepAudio.play().catch(() => {});
          } catch (_) {}
      }
    }

    // Series updates
    const agg = Data.getAggregates(TARGET_MINE);
    overallRiskSeries.push(agg.avgRisk);
    if (overallRiskSeries.length > 60) overallRiskSeries.shift();

    // UI incremental updates
    renderStats();
    renderMinersGrid();
    renderInsights();
  }

  // Utils
  function getRiskLevel(r) {
    if (r >= 70) return "High";
    if (r >= 40) return "Medium";
    return "Low";
  }
  function isEmergency(m) {
    const { co, h2s, ch4LEL, o2, dBA } = m.env;
    const { hr, hrv, temp } = m.vitals;
    return (
      co >= 50 ||
      h2s >= 10 ||
      ch4LEL >= 50 ||
      o2 < 19.5 ||
      temp >= 38.5 ||
      hr >= 130
    );
  }
  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 2000);
  }
  function persistState() {
    localStorage.setItem("innomine:selectedSection", selectedSection);
    localStorage.setItem("innomine:selectedShift", selectedShift);
    localStorage.setItem("innomine:selectedStatus", selectedStatus);
    localStorage.setItem("innomine:live", String(live));
    localStorage.setItem("innomine:muted", String(muted));
  }

  // Global function for call button
  window.callMiner = function (minerId) {
    const miner = Data.getMinerById(minerId);
    if (miner) {
      startCommsOverlay({
        title: `Call with ${miner.name}`,
        subtitle: `${miner.section} • ${miner.shift} Shift`,
      });
    }
  };

  function setLive(v) {
    live = v;
    persistState();
    if (tickTimer) clearInterval(tickTimer);
    if (live) {
      tick();
      tickTimer = setInterval(tick, 1500);
    } // start immediately then every 1.5s
  }
  function updateLiveButton() {
    liveToggle.setAttribute("aria-pressed", String(live));
    liveToggle.innerHTML = `<span class="btn-icon">${live ? "⏸" : "▶"}</span> ${
      live ? "Live" : "Paused"
    }`;
    liveToggle.classList.toggle("active", live);
  }
  function updateClock() {
    clockText.textContent = new Date().toLocaleTimeString();
  }

  // Modal
  function openMinerModal(minerId) {
    const m = Data.getMinerById(minerId);
    if (!m) return;

    const status = getMinerStatus(m);
    const statusClass = status.toLowerCase();

    // Update modal header
    el("modalTitle").textContent = m.name;
    el("modalStatusBadge").textContent = status;
    el("modalStatusBadge").className = `miner-status-badge ${statusClass}`;

    // Update overview section
    el("modalName").textContent = m.name;
    el("modalId").textContent = m.id;
    el("modalSite").textContent = m.site;
    el("modalShift").textContent = m.shift;
    el("modalBattery").innerHTML = `<span style="width: ${m.battery}%"></span>`;
    if (m.maintenance && typeof m.maintenance.helmetDueDays === "number") {
      const days = m.maintenance.helmetDueDays;
      const label =
        days < 7
          ? `${days} days`
          : days < 60
          ? `${Math.round(days / 7)} weeks`
          : `${Math.round(days / 30)} months`;
      el("modalHelmetDue").textContent = label;
    } else {
      el("modalHelmetDue").textContent = "—";
    }
    el("modalLastUpdate").textContent = new Date(m.lastUpdate).toLocaleString();

    // Update vital signs
    updateMetricCard(
      "modalHR",
      m.vitals.hr,
      "BPM",
      getMetricStatus(m.vitals.hr, "hr")
    );
    updateMetricCard(
      "modalHRV",
      m.vitals.hrv,
      "ms",
      getMetricStatus(m.vitals.hrv, "hrv")
    );
    updateMetricCard(
      "modalTemp",
      m.vitals.temp.toFixed(1),
      "°C",
      getMetricStatus(m.vitals.temp, "temp")
    );

    // Update environmental data
    updateMetricCard(
      "modalO2",
      m.env.o2.toFixed(1),
      "%",
      getMetricStatus(m.env.o2, "o2")
    );
    updateMetricCard(
      "modalCO",
      m.env.co,
      "ppm",
      getMetricStatus(m.env.co, "co")
    );
    updateMetricCard(
      "modalH2S",
      m.env.h2s,
      "ppm",
      getMetricStatus(m.env.h2s, "h2s")
    );
    updateMetricCard(
      "modalCH4",
      m.env.ch4LEL,
      "% LEL",
      getMetricStatus(m.env.ch4LEL, "ch4")
    );
    updateMetricCard(
      "modalNoise",
      m.env.dBA,
      "dBA",
      getMetricStatus(m.env.dBA, "noise")
    );
    updateMetricCard(
      "modalSway",
      m.motion.sway.toFixed(2),
      "sway",
      getMetricStatus(m.motion.sway, "sway")
    );

    // Update insights
    updateMinerInsights(m);

    // Show modal
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";

    renderSparkline(minerId);
  }

  // Comms Overlay Logic (simulated voice)
  let commsTimerId = null;
  function startCommsOverlay({ title, subtitle }) {
    const overlay = document.getElementById("commsOverlay");
    const titleEl = document.getElementById("commsTitle");
    const subtitleEl = document.getElementById("commsSubtitle");
    const timerEl = document.getElementById("commsTimer");
    const endBtn = document.getElementById("commsEndBtn");
    if (!overlay || !titleEl || !subtitleEl || !timerEl || !endBtn) return;

    titleEl.textContent = title || "Live communication";
    subtitleEl.textContent = subtitle || "Voice link active";
    timerEl.textContent = "00:00";

    // Show overlay
    overlay.style.display = "flex";
    overlay.classList.add("show");

    // Simple timer
    const start = Date.now();
    commsTimerId && clearInterval(commsTimerId);
    commsTimerId = setInterval(() => {
      const s = Math.floor((Date.now() - start) / 1000);
      const mm = String(Math.floor(s / 60)).padStart(2, "0");
      const ss = String(s % 60).padStart(2, "0");
      timerEl.textContent = `${mm}:${ss}`;
    }, 500);

    // Soft beep every few seconds (if not muted)
    let beepTick = 0;
    const beepIv = setInterval(() => {
      if (!muted && ++beepTick % 3 === 0) {
        try {
          beepAudio.currentTime = 0;
          beepAudio.play().catch(() => {});
        } catch {}
      }
      if (overlay.style.display === "none") clearInterval(beepIv);
    }, 1000);

    const end = () => {
      overlay.classList.remove("show");
      overlay.style.display = "none";
      commsTimerId && clearInterval(commsTimerId);
      showToast("📢 Communication ended");
    };
    endBtn.onclick = end;
    overlay.onclick = (e) => {
      if (e.target === overlay) end();
    };
    window.addEventListener("keydown", function onKey(e) {
      if (e.key === "Escape") {
        end();
        window.removeEventListener("keydown", onKey);
      }
    });
  }

  function updateMetricCard(elementId, value, unit, statusClass) {
    const card = el(elementId);
    const valueEl = card.querySelector(".metric-value");
    const statusEl = card.querySelector(".metric-status");

    valueEl.textContent = value;
    statusEl.className = `metric-status ${statusClass}`;
  }

  function getMetricStatus(value, type) {
    switch (type) {
      case "hr":
        return value >= 130 ? "danger" : value >= 100 ? "warning" : "";
      case "hrv":
        return value <= 20 ? "danger" : value <= 30 ? "warning" : "";
      case "temp":
        return value >= 38.5 ? "danger" : value >= 38.0 ? "warning" : "";
      case "o2":
        return value < 19.5 ? "danger" : value < 20.0 ? "warning" : "";
      case "co":
        return value >= 50 ? "danger" : value >= 25 ? "warning" : "";
      case "h2s":
        return value >= 10 ? "danger" : value >= 5 ? "warning" : "";
      case "ch4":
        return value >= 50 ? "danger" : value >= 25 ? "warning" : "";
      case "noise":
        return value >= 95 ? "danger" : value >= 85 ? "warning" : "";
      case "sway":
        return value >= 0.35 ? "danger" : value >= 0.25 ? "warning" : "";
      default:
        return "";
    }
  }

  function updateMinerInsights(miner) {
    const insights = [];

    // Health insights
    if (miner.vitals.hr >= 130) {
      insights.push({
        type: "danger",
        message:
          "Critical heart rate detected. Immediate medical attention required.",
      });
    } else if (miner.vitals.hr >= 100) {
      insights.push({
        type: "warning",
        message: "Elevated heart rate. Monitor closely.",
      });
    }

    if (miner.vitals.temp >= 38.5) {
      insights.push({
        type: "danger",
        message: "High body temperature. Possible heat stress.",
      });
    }

    // Environmental insights
    if (miner.env.co >= 50 || miner.env.h2s >= 10 || miner.env.ch4LEL >= 50) {
      insights.push({
        type: "danger",
        message: "Toxic gas levels detected. Evacuate immediately.",
      });
    }

    if (miner.env.o2 < 19.5) {
      insights.push({
        type: "danger",
        message: "Low oxygen levels. Emergency oxygen supply required.",
      });
    }

    if (miner.battery < 30) {
      insights.push({
        type: "warning",
        message: "Low battery. Schedule equipment replacement.",
      });
    }

    // Default insight
    if (insights.length === 0) {
      insights.push({
        type: "safe",
        message:
          "All vital signs and environmental conditions within safe parameters.",
      });
    }

    const insightsHtml = insights
      .map(
        (insight) => `
      <div class="insight-card">
        <div class="insight-priority priority-${insight.type}">
          <span class="priority-dot"></span>
          <span>${getInsightTitle(insight.type)}</span>
        </div>
        <p>${insight.message}</p>
      </div>
    `
      )
      .join("");

    el("minerInsights").innerHTML = insightsHtml;
  }

  function getInsightTitle(type) {
    switch (type) {
      case "danger":
        return "Critical Alert";
      case "warning":
        return "Safety Concern";
      case "safe":
        return "Normal Status";
      default:
        return "Status";
    }
  }
  function closeMinerModal() {
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }
  function renderSparkline(minerId) {
    const ctx = document.getElementById("modalSparkline");
    const miner = Data.getMinerById(minerId);
    const series = miner ? miner._history.risk : [];
    if (sparklineChart) sparklineChart.destroy();
    sparklineChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: Array(Math.max(1, series.length)).fill(""),
        datasets: [
          { data: series, borderColor: "#e74c3c", tension: 0.25, fill: false },
        ],
      },
      options: {
        animation: false,
        responsive: true,
        scales: {
          y: { beginAtZero: true, max: 100, ticks: { color: "#8aa0c4" } },
          x: { display: false },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  // Events
  function bindEvents() {
    shiftFilter.addEventListener("change", () => {
      selectedShift = shiftFilter.value;
      persistState();
      renderMinersGrid();
    });

    statusFilter.addEventListener("change", () => {
      selectedStatus = statusFilter.value;
      persistState();
      renderMinersGrid();
    });

    searchInput.addEventListener("input", (e) => {
      searchQuery = e.target.value;
      renderMinersGrid();
    });

    liveToggle.addEventListener("click", () => {
      setLive(!live);
      updateLiveButton();
      showToast(live ? "Live updates resumed" : "Live paused");
    });

    showAllSectionsBtn.addEventListener("click", () => {
      selectedSection = "ALL";
      viewMode = "sections";
      persistState();
      updateViewMode();
      updateCurrentSectionDisplay();
    });

    communicateBtn.addEventListener("click", () => {
      startCommsOverlay({
        title: "Broadcast to all miners",
        subtitle: "Live voice broadcast",
      });
    });
    exportBtn.addEventListener("click", () => {
      const data = { sites: Data.getSites(), miners: Data.getAllMiners() };
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "innomine-dataset.json";
      a.click();
      URL.revokeObjectURL(url);
    });
    screenshotBtn.addEventListener("click", () => {
      showToast("Tip: Use your OS screenshot tool for now.");
    });
    // Modal controls
    modal.addEventListener("click", (e) => {
      if (e.target.hasAttribute("data-modal-close")) closeMinerModal();
      if (e.target === modal) closeMinerModal();
    });
    modalClose.addEventListener("click", closeMinerModal);
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && modal.getAttribute("aria-hidden") === "false")
        closeMinerModal();
    });
  }

  // Global test function
  window.testSections = function () {
    console.log("Manual test: calling renderSectionsGrid");
    console.log("Data available:", !!Data);
    console.log("Data object:", Data);
    renderSectionsGrid();
  };

  // Kickoff - call init directly since scripts load synchronously
  init();
})();
