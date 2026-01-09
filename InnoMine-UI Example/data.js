// InnoMine dummy data and update engine (data layer)
// Exports: SITES, MINERS, functions: getAllMiners, getSites, getMinerById, getMinersBySite,
// randomizeTick(miner), getAggregates()

const SITES = ["Mahd adh Dhahab (Gold)"];

// Mine sections for Mahd adh Dhahab
const MINE_SECTIONS = [
  "Eastern Trench",
  "Western Shaft",
  "Southern Gallery",
  "Northern Drift",
  "Central Chamber",
];

// Seed 20 miners with Saudi context and mine sections
const MINERS = [
  {
    id: "KSA-MIN-001",
    name: "Faisal Alharbi",
    site: SITES[0],
    section: MINE_SECTIONS[0],
    shift: "Day",
  },
  {
    id: "KSA-MIN-002",
    name: "Amina Alqahtani",
    site: SITES[0],
    section: MINE_SECTIONS[0],
    shift: "Night",
  },
  {
    id: "KSA-MIN-003",
    name: "Yazeed Alotaibi",
    site: SITES[0],
    section: MINE_SECTIONS[1],
    shift: "Day",
  },
  {
    id: "KSA-MIN-004",
    name: "Huda Almutairi",
    site: SITES[0],
    section: MINE_SECTIONS[1],
    shift: "Night",
  },
  {
    id: "KSA-MIN-005",
    name: "Khalid Alsubaie",
    site: SITES[0],
    section: MINE_SECTIONS[2],
    shift: "Day",
  },
  {
    id: "KSA-MIN-006",
    name: "Sara Alrasheed",
    site: SITES[0],
    section: MINE_SECTIONS[2],
    shift: "Night",
  },
  {
    id: "KSA-MIN-007",
    name: "Nasser Alharthi",
    site: SITES[0],
    section: MINE_SECTIONS[2],
    shift: "Day",
  },
  {
    id: "KSA-MIN-008",
    name: "Mansour Alzahrani",
    site: SITES[0],
    section: MINE_SECTIONS[3],
    shift: "Night",
  },
  {
    id: "KSA-MIN-009",
    name: "Reema Alghamdi",
    site: SITES[0],
    section: MINE_SECTIONS[3],
    shift: "Day",
  },
  {
    id: "KSA-MIN-010",
    name: "Bandar Alshehri",
    site: SITES[0],
    section: MINE_SECTIONS[3],
    shift: "Night",
  },
  {
    id: "KSA-MIN-011",
    name: "Hussain Alshammari",
    site: SITES[0],
    section: MINE_SECTIONS[4],
    shift: "Day",
  },
  {
    id: "KSA-MIN-012",
    name: "Rasha Alenzi",
    site: SITES[0],
    section: MINE_SECTIONS[4],
    shift: "Night",
  },
  {
    id: "KSA-MIN-013",
    name: "Fahad Almarri",
    site: SITES[0],
    section: MINE_SECTIONS[0],
    shift: "Day",
  },
  {
    id: "KSA-MIN-014",
    name: "Maha Alsehli",
    site: SITES[0],
    section: MINE_SECTIONS[0],
    shift: "Night",
  },
  {
    id: "KSA-MIN-015",
    name: "Abdulrahman Alotaishan",
    site: SITES[0],
    section: MINE_SECTIONS[1],
    shift: "Day",
  },
  {
    id: "KSA-MIN-016",
    name: "Hatoon Alhamdi",
    site: SITES[0],
    section: MINE_SECTIONS[1],
    shift: "Night",
  },
  {
    id: "KSA-MIN-017",
    name: "Sultan Alhajri",
    site: SITES[0],
    section: MINE_SECTIONS[2],
    shift: "Day",
  },
  {
    id: "KSA-MIN-018",
    name: "Lama Alarab",
    site: SITES[0],
    section: MINE_SECTIONS[3],
    shift: "Night",
  },
  {
    id: "KSA-MIN-019",
    name: "Tariq Alruwais",
    site: SITES[0],
    section: MINE_SECTIONS[4],
    shift: "Day",
  },
  {
    id: "KSA-MIN-020",
    name: "Noura Alotaibi",
    site: SITES[0],
    section: MINE_SECTIONS[4],
    shift: "Night",
  },
].map((m) => ({
  ...m,
  vitals: {
    hr: randRange(65, 95),
    hrv: randRange(30, 60),
    temp: +(36.6 + Math.random() * 0.6).toFixed(1),
  },
  motion: { sway: +(Math.random() * 0.15).toFixed(2), posture: "OK" },
  env: {
    co: randRange(2, 18),
    h2s: randRange(0, 5),
    ch4LEL: randRange(1, 12),
    o2: +(20.5 + Math.random() * 0.4).toFixed(1),
    dBA: randRange(78, 92),
  },
  maintenance: { helmetDueDays: randRange(2, 90) },
  risk: 0,
  battery: randRange(60, 100),
  lastUpdate: new Date().toISOString(),
  _history: { risk: [] },
}));

// Utils
function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}
function randRange(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}
function randFloat(min, max, decimals = 2) {
  const v = Math.random() * (max - min) + min;
  return +v.toFixed(decimals);
}

// Normalization helpers for risk (0..1 unsafe scale per metric)
function normHR(hr) {
  return clamp((hr - 55) / (135 - 55), 0, 1);
}
function normHRV(hrv) {
  return clamp((hrv - 12) / (80 - 12), 0, 1);
}
function normTemp(t) {
  return clamp((t - 36.2) / (39.0 - 36.2), 0, 1);
}
function normGas(v) {
  return clamp(v / 100, 0, 1);
} // co,h2s,ch4LEL scaled roughly 0..100 danger
function normNoise(dba) {
  return clamp((dba - 70) / (110 - 70), 0, 1);
}
function normSway(s) {
  return clamp(s / 0.45, 0, 1);
}
function normO2(o2) {
  return clamp((o2 - 18.0) / (21.0 - 18.0), 0, 1);
}

function computeRisk(miner) {
  const { vitals, env, motion } = miner;
  const envDanger = Math.max(
    normGas(env.co),
    normGas(env.h2s * 5),
    normGas(env.ch4LEL)
  );
  const risk = Math.round(
    100 *
      (0.22 * normHR(vitals.hr) +
        0.22 * (1 - normHRV(vitals.hrv)) +
        0.15 * normTemp(vitals.temp) +
        0.16 * envDanger +
        0.1 * normNoise(env.dBA) +
        0.1 * normSway(motion.sway) +
        0.05 * (1 - normO2(env.o2)))
  );
  return clamp(risk, 0, 100);
}

// Initialize risk and history
for (const m of MINERS) {
  m.risk = computeRisk(m);
  m._history.risk.push(m.risk);
}

function getAllMiners() {
  return MINERS;
}
function getSites() {
  return SITES;
}
function getMineSections() {
  return MINE_SECTIONS;
}
function getMinerById(id) {
  return MINERS.find((m) => m.id === id) || null;
}
function getMinersBySite(site) {
  return MINERS.filter((m) => m.site === site);
}
function getMinersBySection(section) {
  return MINERS.filter((m) => m.section === section);
}

function randomizeTick(miner) {
  // small drifts
  const dHr = randFloat(-3, 3, 1);
  const dHrv = randFloat(-3, 3, 1);
  const dTemp = randFloat(-0.15, 0.15, 2);
  const dCo = randFloat(-5, 6, 2);
  const dH2s = randFloat(-1.5, 1.8, 2);
  const dCh4 = randFloat(-6, 6, 2);
  const dO2 = randFloat(-0.2, 0.2, 2);
  const dDba = randFloat(-3, 3, 1);
  const dSway = randFloat(-0.05, 0.06, 3);

  miner.vitals.hr = clamp(Math.round(miner.vitals.hr + dHr), 55, 135);
  miner.vitals.hrv = clamp(Math.round(miner.vitals.hrv + dHrv), 12, 80);
  miner.vitals.temp = clamp(
    +(miner.vitals.temp + dTemp).toFixed(1),
    36.2,
    39.0
  );
  miner.env.co = clamp(Math.round(miner.env.co + dCo), 0, 100);
  miner.env.h2s = clamp(Math.round(miner.env.h2s + dH2s), 0, 20);
  miner.env.ch4LEL = clamp(Math.round(miner.env.ch4LEL + dCh4), 0, 100);
  miner.env.o2 = clamp(+(miner.env.o2 + dO2).toFixed(1), 18.0, 21.0);
  miner.env.dBA = clamp(Math.round(miner.env.dBA + dDba), 70, 110);
  miner.motion.sway = clamp(+(miner.motion.sway + dSway).toFixed(2), 0.0, 0.45);
  miner.battery = clamp(miner.battery - randFloat(0.05, 0.25, 2), 0, 100);
  miner.lastUpdate = new Date().toISOString();

  miner.risk = computeRisk(miner);
  const hist = miner._history.risk;
  hist.push(miner.risk);
  if (hist.length > 60) hist.shift();

  // anomaly rules
  let anomaly = null;
  const { co, h2s, ch4LEL, o2, dBA } = miner.env;
  const { hr, hrv, temp } = miner.vitals;
  if (
    co >= 50 ||
    h2s >= 10 ||
    ch4LEL >= 50 ||
    o2 < 19.5 ||
    temp >= 38.5 ||
    hr >= 130
  ) {
    anomaly = {
      severity: "EMERGENCY",
      cause: "Threshold breach",
      values: { co, h2s, ch4LEL, o2, temp, hr },
    };
  } else if (dBA >= 95 || miner.risk >= 70 || hrv <= 20) {
    anomaly = {
      severity: "WARNING",
      cause: "Elevated risk",
      values: { dBA, risk: miner.risk, hrv },
    };
  }
  return anomaly;
}

function getAggregates(siteFilter = null) {
  const miners =
    siteFilter && siteFilter !== "ALL"
      ? MINERS.filter((m) => m.site === siteFilter)
      : MINERS;
  const totalMiners = miners.length;
  const avgRisk = totalMiners
    ? Math.round(miners.reduce((a, m) => a + m.risk, 0) / totalMiners)
    : 0;
  const siteRisk = SITES.map((site) => ({
    site,
    risk: Math.round(
      getMinersBySite(site).reduce((a, m) => a + m.risk, 0) /
        Math.max(1, getMinersBySite(site).length)
    ),
  })).sort((a, b) => b.risk - a.risk);
  const highestRiskSite = siteRisk[0] || { site: "—", risk: 0 };
  return { totalMiners, avgRisk, highestRiskSite };
}

// Export to window
window.InnoMineData = {
  SITES,
  MINE_SECTIONS,
  MINERS,
  getAllMiners,
  getSites,
  getMineSections,
  getMinerById,
  getMinersBySite,
  getMinersBySection,
  randomizeTick,
  getAggregates,
};
