import { JkBms } from "./jk-bms.js";

const $ = (s) => document.querySelector(s);
const bms = new JkBms();
let lastData = null;

// --- UI References ---
const connectBtn = $("#connect-btn");
const disconnectBtn = $("#disconnect-btn");
const statusDot = $("#status-dot");
const statusText = $("#status-text");
const deviceName = $("#device-name");
const viewConnect = $("#view-connect");
const viewDashboard = $("#view-dashboard");
const cellsContainer = $("#cells-container");
const historyBody = $("#history-body");

const MAX_HISTORY = 50;
const history = [];

// --- Helpers ---
function fmt(val, digits = 1) {
  return val != null ? val.toFixed(digits) : "--";
}

function formatDuration(seconds) {
  if (seconds == null) return "--";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function setStatus(state) {
  statusDot.className = "dot " + state;
  const labels = {
    disconnected: "Disconnected",
    connecting: "Connecting...",
    connected: "Connected",
  };
  statusText.textContent = labels[state] || state;
}

function showView(view) {
  viewConnect.classList.toggle("hidden", view !== "connect");
  viewDashboard.classList.toggle("hidden", view !== "dashboard");
}

// --- Cell Voltage Rendering ---
function renderCells(data) {
  cellsContainer.innerHTML = "";

  if (!data || !data.cells.length) {
    cellsContainer.innerHTML = '<p class="muted">No cell data</p>';
    return;
  }

  const min = data.minCellMv;
  const max = data.maxCellMv;
  // Scale bar heights: 40% to 100% of container
  const range = max - min || 1;

  data.cells.forEach((mv, i) => {
    const pct = ((mv - min) / range) * 60 + 40;
    const v = (mv / 1000).toFixed(3);

    // Color: green if balanced, yellow/red if deviating
    const deviation = Math.abs(mv - data.avgCellMv);
    let color = "var(--green)";
    if (deviation > 20) color = "var(--yellow)";
    if (deviation > 50) color = "var(--red)";

    const cell = document.createElement("div");
    cell.className = "cell-bar";
    cell.innerHTML = `
      <div class="bar-wrap">
        <div class="bar" style="height:${pct}%;background:${color}"></div>
      </div>
      <span class="cell-v">${v}</span>
      <span class="cell-n">${i + 1}</span>
    `;
    cellsContainer.appendChild(cell);
  });
}

// --- Dashboard Update ---
function updateDashboard(data) {
  if (!data) return;

  // Main metrics
  $("#val-soc").textContent = data.soc + "%";
  $("#val-voltage").textContent = fmt(data.voltageV, 2) + " V";
  $("#val-current").textContent = fmt(data.currentA, 2) + " A";
  $("#val-power").textContent = fmt(data.powerW, 1) + " W";

  // SoC ring
  const ring = $("#soc-ring");
  const circumference = 2 * Math.PI * 54;
  ring.style.strokeDasharray = circumference;
  ring.style.strokeDashoffset = circumference * (1 - data.soc / 100);

  // SoC color
  let socColor = "var(--green)";
  if (data.soc < 20) socColor = "var(--red)";
  else if (data.soc < 40) socColor = "var(--yellow)";
  ring.style.stroke = socColor;

  // Temperatures
  $("#val-temp1").textContent =
    data.temp1 != null ? fmt(data.temp1) + " C" : "--";
  $("#val-temp2").textContent =
    data.temp2 != null ? fmt(data.temp2) + " C" : "--";
  $("#val-mos-temp").textContent =
    data.mosTemp != null ? fmt(data.mosTemp) + " C" : "--";

  // Battery info
  $("#val-cells").textContent = data.cellCount;
  $("#val-cycles").textContent = data.cycles ?? "--";
  $("#val-capacity").textContent =
    data.totalCapacityAh > 0 ? fmt(data.totalCapacityAh, 1) + " Ah" : "--";
  $("#val-delta").textContent = data.deltaCellMv + " mV";
  $("#val-min-cell").textContent = (data.minCellMv / 1000).toFixed(3) + " V";
  $("#val-max-cell").textContent = (data.maxCellMv / 1000).toFixed(3) + " V";
  $("#val-uptime").textContent = formatDuration(data.uptimeS);

  // Status indicators
  setIndicator("#ind-charge", data.chargeMos, "CHG");
  setIndicator("#ind-discharge", data.dischargeMos, "DSG");
  setIndicator("#ind-balance", data.balancerActive, "BAL");

  // Charging/discharging direction
  const dirEl = $("#val-direction");
  if (data.currentA > 0.05) {
    dirEl.textContent = "Charging";
    dirEl.className = "direction charging";
  } else if (data.currentA < -0.05) {
    dirEl.textContent = "Discharging";
    dirEl.className = "direction discharging";
  } else {
    dirEl.textContent = "Idle";
    dirEl.className = "direction idle";
  }

  // Warnings
  const warnEl = $("#val-warnings");
  if (data.warnings) {
    warnEl.textContent = "0x" + data.warnings.toString(16).padStart(4, "0");
    warnEl.className = "warn active";
  } else {
    warnEl.textContent = "None";
    warnEl.className = "warn";
  }

  // Cell bars
  renderCells(data);

  // History
  addHistory(data);
}

function setIndicator(sel, active, label) {
  const el = $(sel);
  el.textContent = label;
  el.className = "indicator " + (active ? "on" : "off");
}

function addHistory(data) {
  const time = new Date(data.timestamp);
  const timeStr =
    time.getHours().toString().padStart(2, "0") +
    ":" +
    time.getMinutes().toString().padStart(2, "0") +
    ":" +
    time.getSeconds().toString().padStart(2, "0");

  history.unshift({
    time: timeStr,
    soc: data.soc,
    voltage: data.voltageV,
    current: data.currentA,
    power: data.powerW,
    temp: data.temp1,
    delta: data.deltaCellMv,
  });

  if (history.length > MAX_HISTORY) history.pop();

  historyBody.innerHTML = history
    .map(
      (h) => `
    <tr>
      <td>${h.time}</td>
      <td>${h.soc}%</td>
      <td>${fmt(h.voltage, 2)}</td>
      <td>${fmt(h.current, 2)}</td>
      <td>${fmt(h.power, 1)}</td>
      <td>${h.temp != null ? fmt(h.temp) : "--"}</td>
      <td>${h.delta}</td>
    </tr>
  `
    )
    .join("");
}

// --- Events ---
connectBtn.addEventListener("click", async () => {
  try {
    setStatus("connecting");
    connectBtn.disabled = true;
    await bms.connect();
  } catch (err) {
    setStatus("disconnected");
    connectBtn.disabled = false;
    if (err.name !== "NotFoundError") {
      alert("Connection failed: " + err.message);
    }
  }
});

disconnectBtn.addEventListener("click", () => {
  bms.disconnect();
});

bms.addEventListener("connected", () => {
  setStatus("connected");
  deviceName.textContent = bms.deviceName;
  connectBtn.disabled = false;
  showView("dashboard");
  bms.startPolling(5000);
});

bms.addEventListener("disconnected", () => {
  setStatus("disconnected");
  connectBtn.disabled = false;
  showView("connect");
});

bms.addEventListener("data", (e) => {
  lastData = e.detail;
  updateDashboard(lastData);
});

// --- Init ---
showView("connect");
setStatus("disconnected");

// Register service worker
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
