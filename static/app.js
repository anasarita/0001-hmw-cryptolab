// CRYPTO LAB - Participant Application Logic
let currentToken = localStorage.getItem("cryptolab_token") || null;
let currentParticipant = null;
let currentRoom = null;
let currentPrices = {};
let currentTradeSide = "BUY";
let currentTransferType = "INTERNAL";
let pollInterval = null;

// Currency Formatter
function formatCOP(num) {
  if (num === null || num === undefined || isNaN(num)) return "COP 0,00";
  return "COP " + Number(num).toLocaleString("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatCrypto(num, asset) {
  if (num === null || num === undefined || isNaN(num)) return `0 ${asset}`;
  const dec = (asset === "BTC" || asset === "ETH") ? 6 : (asset === "SOL" ? 4 : 2);
  return `${Number(num).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: dec })} ${asset}`;
}

// Initialization on DOM Load
document.addEventListener("DOMContentLoaded", () => {
  // Check URL params for room code
  const urlParams = new URLSearchParams(window.location.search);
  const roomParam = urlParams.get("room");
  if (roomParam) {
    const roomInput = document.getElementById("join-room-code");
    if (roomInput) roomInput.value = roomParam.trim().toUpperCase();
  }

  // Setup Tab listeners
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      switchTab(tabId);
    });
  });

  // Setup Form Handlers safely
  const safeListen = (id, evt, fn) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener(evt, fn);
  };

  safeListen("form-join", "submit", handleJoin);
  safeListen("form-bank-transfer", "submit", handleBankTransfer);
  safeListen("form-trade", "submit", handleTradeSubmit);
  safeListen("form-transfer", "submit", handleTransferSubmit);
  safeListen("btn-logout", "click", handleLogout);
  safeListen("btn-refresh-balances", "click", fetchProfile);
  safeListen("btn-refresh-market", "click", fetchPrices);
  safeListen("btn-refresh-history", "click", fetchHistory);
  safeListen("bank-direction", "change", updateBankAvailable);

  // If token exists, try resume session
  if (currentToken) {
    fetchProfile().then(success => {
      if (!success) showJoinView();
    });
  } else {
    showJoinView();
  }
});

function showNotification(msg, type = "success") {
  const el = document.getElementById("global-message");
  if (!el) return;
  el.style.display = "flex";
  el.className = type === "success" ? "badge-success" : (type === "warning" ? "badge-warning" : "badge-danger");
  el.innerHTML = `<span>${msg}</span><button onclick="this.parentElement.style.display='none'" style="background:none;border:none;color:inherit;font-weight:700;cursor:pointer;">&times;</button>`;
  setTimeout(() => { el.style.display = "none"; }, 6000);
}

function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-pane").forEach(p => p.style.display = "none");

  const targetBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
  if (targetBtn) targetBtn.classList.add("active");

  const pane = document.getElementById(tabId);
  if (pane) pane.style.display = "block";

  if (tabId === "tab-market") {
    fetchPrices();
    // Ensure Lightweight Charts adapts to newly visible tab dimensions
    setTimeout(() => {
      const container = document.getElementById("replay-chart-container");
      if (tvChart && container) {
        tvChart.applyOptions({
          width: container.clientWidth || 800,
          height: container.clientHeight || 380
        });
        try { tvChart.timeScale().fitContent(); } catch(e) {}
      }
    }, 60);
  }
  if (tabId === "tab-trade") {
    fetchPrices();
  }
  if (tabId === "tab-history") {
    fetchHistory();
  }
  if (tabId === "tab-transfer") {
    fetchRoomPeers();
    updateTransferMaxBalance();
  }
  if (tabId === "tab-bank") {
    updateBankAvailable();
  }
}

// Session Management
async function handleJoin(e) {
  e.preventDefault();
  const roomCode = document.getElementById("join-room-code").value.trim().toUpperCase();
  const alias = document.getElementById("join-alias").value.trim();
  const alertEl = document.getElementById("join-alert");
  alertEl.style.display = "none";

  const btn = document.getElementById("btn-submit-join");
  btn.disabled = true;
  btn.textContent = "Verificando...";

  try {
    const res = await fetch("/api/rooms/join", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ room_code: roomCode, alias: alias })
    });
    const data = await res.json();
    if (!res.ok) {
      alertEl.textContent = data.detail || "Error al unirse a la sala.";
      alertEl.style.display = "block";
      btn.disabled = false;
      btn.innerHTML = "<span>Ingresar a la Plataforma</span>";
      return;
    }

    currentToken = data.token;
    localStorage.setItem("cryptolab_token", currentToken);
    currentParticipant = data.participant;
    currentRoom = data.room;

    showDashboardView();
    startPolling();
  } catch (err) {
    alertEl.textContent = "No fue posible conectar con el servidor. Revisa tu conexión.";
    alertEl.style.display = "block";
  } finally {
    btn.disabled = false;
    btn.innerHTML = "<span>Ingresar a la Plataforma</span>";
  }
}

function handleLogout() {
  localStorage.removeItem("cryptolab_token");
  currentToken = null;
  currentParticipant = null;
  currentRoom = null;
  if (pollInterval) clearInterval(pollInterval);
  showJoinView();
}

function showJoinView() {
  document.getElementById("view-join").style.display = "block";
  document.getElementById("view-dashboard").style.display = "none";
  document.getElementById("user-nav-status").style.display = "none";
}

function showDashboardView() {
  document.getElementById("view-join").style.display = "none";
  document.getElementById("view-dashboard").style.display = "block";
  document.getElementById("user-nav-status").style.display = "flex";

  document.getElementById("nav-alias").textContent = currentParticipant.alias;
  document.getElementById("nav-room").textContent = `Sala: ${currentRoom.code} (${currentRoom.name})`;

  updateDashboardUI();
  fetchPrices();
  fetchRoomPeers();
  startPolling();
}

// Fetch Profile and Balances
async function fetchProfile() {
  if (!currentToken) return false;
  try {
    const res = await fetch("/api/participant/me", {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) {
      handleLogout();
      return false;
    }
    const data = await res.json();
    currentParticipant = data.participant;
    currentRoom = data.room;
    showDashboardView();
    return true;
  } catch (err) {
    return false;
  }
}

// Fetch Market Prices & Replay Clock State
let lastReplayState = null;

let currentChartAsset = "BTC";
let tvChart = null;
let tvAreaSeries = null;
let tvResizeObserver = null;
let prevPrices = {};

const ASSET_META = {
  BTC: { name: "Bitcoin", pair: "BTC / COP" },
  ETH: { name: "Ethereum", pair: "ETH / COP" },
  USDT: { name: "Tether USD", pair: "USDT / COP" },
  SOL: { name: "Solana", pair: "SOL / COP" }
};

async function fetchPrices() {
  try {
    const res = await fetch("/api/market/prices");
    if (res.ok) {
      const data = await res.json();
      currentPrices = data.prices || {};
      lastReplayState = data.replay_state || null;

      if (lastReplayState) {
        updateReplayUI(lastReplayState);
      }

      // Always update UI cards and tables first so values are never stuck
      updateTerminalTopZone();
      renderMarketTable();
      updateDashboardUI();
      updateTradeCalculator();

      // Render or update dynamic chart
      if (lastReplayState) {
        initOrUpdateInteractiveChart(lastReplayState.chart_history || []);
      }
    }
  } catch (err) {
    console.error("Error fetching prices:", err);
  }
}

function updateReplayUI(state) {
  if (!state) return;

  const badge = document.getElementById("replay-status-badge");
  if (badge) {
    if (state.is_completed) {
      badge.className = "badge badge-danger";
      badge.textContent = "MERCADO FINALIZADO";
    } else if (state.status === "RUNNING") {
      badge.className = "badge badge-success";
      badge.textContent = `EN EJECUCIÓN ${state.speed}X`;
    } else if (state.status === "PAUSED") {
      badge.className = "badge badge-warning";
      badge.textContent = `PAUSADO (${state.speed}X)`;
    } else {
      badge.className = "badge badge-info";
      badge.textContent = `DETENIDO`;
    }
  }

  const dtEl = document.getElementById("replay-sim-datetime");
  if (dtEl) {
    dtEl.textContent = state.simulated_datetime_formatted || state.simulated_datetime_iso;
  }

  const elapsedEl = document.getElementById("replay-elapsed-text");
  if (elapsedEl) {
    elapsedEl.textContent = state.elapsed_formatted;
  }

  const progBar = document.getElementById("replay-progress-bar");
  if (progBar) {
    progBar.style.width = `${state.progress_percent}%`;
  }
}

// =========================================================================
// INTERACTIVE TRADING TERMINAL & DYNAMIC CHART ENGINE
// =========================================================================

function initOrUpdateInteractiveChart(history) {
  const container = document.getElementById("replay-chart-container");
  if (!container) return;

  try {
    if (typeof LightweightCharts !== "undefined") {
      renderLightweightChart(container, history || []);
    } else {
      renderFallbackSvgChart(container, history || []);
    }
  } catch (err) {
    console.error("Error in LightweightCharts, using SVG fallback:", err);
    renderFallbackSvgChart(container, history || []);
  }

  updateTerminalTopZone();
}

function renderLightweightChart(container, history) {
  const seriesData = [];
  const historyMap = new Map();
  const seen = new Set();

  (history || []).forEach(pt => {
    const val = pt[currentChartAsset];
    const t = pt.time || pt.timestamp;
    if (val && val > 0 && t && !seen.has(t)) {
      seen.add(t);
      seriesData.push({
        time: t,
        value: Number(val)
      });
      historyMap.set(t, pt);
    }
  });

  if (seriesData.length === 0) {
    const curP = currentPrices[currentChartAsset]?.price_cop || lastReplayState?.prices?.[currentChartAsset] || 0;
    const nowTs = Math.floor(Date.now() / 1000);
    if (curP > 0) {
      seriesData.push({ time: nowTs - 60, value: curP });
      seriesData.push({ time: nowTs, value: curP });
      historyMap.set(nowTs - 60, { time_label: "00:00 COT", date_label: "10 de Noviembre de 2026", nature: "OBSERVADO_REAL" });
      historyMap.set(nowTs, { time_label: "00:00 COT", date_label: "10 de Noviembre de 2026", nature: "OBSERVADO_REAL" });
    } else {
      renderFallbackSvgChart(container, history);
      return;
    }
  } else if (seriesData.length === 1) {
    const p0 = seriesData[0];
    seriesData.unshift({
      time: p0.time - 60,
      value: p0.value
    });
    historyMap.set(p0.time - 60, historyMap.get(p0.time) || {});
  }

  seriesData.sort((a, b) => a.time - b.time);

  const seriesOpts = {
    topColor: "rgba(0, 201, 141, 0.40)",
    bottomColor: "rgba(0, 201, 141, 0.00)",
    lineColor: "#00C98D",
    lineWidth: 2,
    priceLineVisible: true,
    priceLineWidth: 1,
    priceLineColor: "#00C98D",
    priceLineStyle: 2,
    crosshairMarkerVisible: true,
    crosshairMarkerRadius: 5,
    crosshairMarkerBorderColor: "#ffffff",
    crosshairMarkerBackgroundColor: "#00C98D"
  };

  // Initialize TradingView Lightweight Chart instance once
  if (!tvChart) {
    container.innerHTML = `
      <div id="chart-floating-tooltip" class="chart-floating-tooltip" style="display: none;"></div>
      <div id="chart-beacon-dot" class="chart-beacon-dot" style="display: none;"></div>
    `;

    const chartW = container.clientWidth > 100 ? container.clientWidth : 800;
    const chartH = container.clientHeight > 100 ? container.clientHeight : 380;

    tvChart = LightweightCharts.createChart(container, {
      width: chartW,
      height: chartH,
      layout: {
        background: { color: "#090e18" },
        textColor: "#94A3B8",
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 11
      },
      grid: {
        vertLines: { color: "#1B2A3C", style: 3 },
        horzLines: { color: "#1B2A3C", style: 3 }
      },
      crosshair: {
        vertLine: {
          color: "#00C98D",
          width: 1,
          style: 2,
          labelBackgroundColor: "#172638"
        },
        horzLine: {
          color: "#00C98D",
          width: 1,
          style: 2,
          labelBackgroundColor: "#172638"
        }
      },
      timeScale: {
        borderColor: "#1B2A3C",
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 6,
        barSpacing: 9,
        minBarSpacing: 3
      },
      rightPriceScale: {
        borderColor: "#1B2A3C",
        scaleMargins: { top: 0.16, bottom: 0.14 },
        alignLabels: true
      },
      localization: {
        dateFormat: "yyyy-MM-dd",
        timeFormatter: (ts) => {
          try {
            const d = new Date(ts * 1000);
            return d.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit", timeZone: "America/Bogota" }) + " COT";
          } catch(e) {
            return "";
          }
        }
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true }
    });

    // Crosshair interaction for tooltip
    const tooltip = document.getElementById("chart-floating-tooltip");
    tvChart.subscribeCrosshairMove(param => {
      if (!tooltip) return;
      if (!param.point || !param.time || param.point.x < 0 || param.point.x > container.clientWidth || param.point.y < 0 || param.point.y > container.clientHeight) {
        tooltip.style.display = "none";
        updateTerminalTopZone();
        return;
      }

      let price = undefined;
      if (param.seriesData && typeof param.seriesData.get === "function" && tvAreaSeries) {
        const d = param.seriesData.get(tvAreaSeries);
        if (d) price = d.value !== undefined ? d.value : d.close;
      }

      if (price !== undefined) {
        tooltip.style.display = "block";
        const match = historyMap.get(param.time) || seriesData.find(d => d.time === param.time);
        const timeLabel = match?.time_full_cot || match?.time_label || "";
        const dateLabel = match?.date_label || "10 de Noviembre de 2026";
        const nature = match?.nature === "CALCULADO_INTERPOLADO" ? "Interpolado" : "Cotización Real";

        tooltip.innerHTML = `
          <div class="tooltip-time">${dateLabel} &bull; ${timeLabel}</div>
          <div class="tooltip-price">${formatCOP(price)}</div>
          <div class="tooltip-nature">${nature}</div>
        `;

        const tipW = 195;
        let left = param.point.x + 14;
        if (left + tipW > container.clientWidth) left = param.point.x - tipW - 14;
        let top = param.point.y - 42;
        if (top < 10) top = 10;

        tooltip.style.left = `${Math.max(8, left)}px`;
        tooltip.style.top = `${top}px`;
      }
    });

    // Auto-resize
    if (window.ResizeObserver) {
      tvResizeObserver = new ResizeObserver(entries => {
        if (!entries || entries.length === 0) return;
        const entry = entries[0];
        if (entry.contentRect.width > 50 && entry.contentRect.height > 50) {
          tvChart.applyOptions({
            width: entry.contentRect.width,
            height: entry.contentRect.height
          });
        }
      });
      tvResizeObserver.observe(container);
    }
  }

  // Ensure tvAreaSeries is created
  if (!tvAreaSeries && tvChart) {
    if (typeof tvChart.addAreaSeries === "function") {
      tvAreaSeries = tvChart.addAreaSeries(seriesOpts);
    } else if (typeof tvChart.addSeries === "function" && typeof LightweightCharts !== "undefined" && LightweightCharts.AreaSeries) {
      tvAreaSeries = tvChart.addSeries(LightweightCharts.AreaSeries, seriesOpts);
    }
  }

  // Set progressive dataset
  if (tvAreaSeries) {
    try {
      tvAreaSeries.setData(seriesData);
      tvChart.timeScale().fitContent();
    } catch(e) {
      console.warn("Error setting area series data, falling back to SVG:", e);
      renderFallbackSvgChart(container, history);
      return;
    }
  } else {
    renderFallbackSvgChart(container, history);
    return;
  }

  // Position the pulsing beacon dot at the latest point
  updateBeaconDot(seriesData[seriesData.length - 1]);
}

function updateBeaconDot(latestPoint) {
  const beacon = document.getElementById("chart-beacon-dot");
  if (!beacon || !tvChart || !tvAreaSeries || !latestPoint) {
    if (beacon) beacon.style.display = "none";
    return;
  }

  try {
    const x = tvChart.timeScale().timeToCoordinate(latestPoint.time);
    const y = tvAreaSeries.priceToCoordinate(latestPoint.value);
    const container = document.getElementById("replay-chart-container");
    if (x !== null && y !== null && x >= 0 && x <= container.clientWidth && y >= 0 && y <= container.clientHeight) {
      beacon.style.display = "block";
      beacon.style.left = `${x}px`;
      beacon.style.top = `${y}px`;
    } else {
      beacon.style.display = "none";
    }
  } catch (e) {
    beacon.style.display = "none";
  }
}

function switchChartAsset(asset) {
  currentChartAsset = asset.toUpperCase();
  document.querySelectorAll(".chart-pill").forEach(p => {
    p.classList.toggle("active", p.getAttribute("data-asset") === currentChartAsset);
  });

  const hist = lastReplayState?.chart_history || [];
  initOrUpdateInteractiveChart(hist);
  if (tvChart) {
    try {
      tvChart.timeScale().fitContent();
    } catch(e) {}
  }
  updateTerminalTopZone();
}

function chartZoomIn() {
  if (!tvChart) return;
  const ts = tvChart.timeScale();
  const currentRange = ts.getVisibleLogicalRange();
  if (currentRange) {
    const mid = (currentRange.from + currentRange.to) / 2;
    const span = (currentRange.to - currentRange.from) * 0.7;
    ts.setVisibleLogicalRange({ from: mid - span / 2, to: mid + span / 2 });
  }
}

function chartZoomOut() {
  if (!tvChart) return;
  const ts = tvChart.timeScale();
  const currentRange = ts.getVisibleLogicalRange();
  if (currentRange) {
    const mid = (currentRange.from + currentRange.to) / 2;
    const span = (currentRange.to - currentRange.from) * 1.4;
    ts.setVisibleLogicalRange({ from: mid - span / 2, to: mid + span / 2 });
  }
}

function chartResetZoom() {
  if (!tvChart) return;
  try {
    tvChart.timeScale().fitContent();
  } catch(e) {}
}

function updateTerminalTopZone() {
  const meta = ASSET_META[currentChartAsset] || { name: currentChartAsset, pair: `${currentChartAsset} / COP` };
  const badgeEl = document.getElementById("chart-asset-badge");
  const nameEl = document.getElementById("chart-asset-name");
  const pairEl = document.getElementById("chart-asset-pair");
  const priceEl = document.getElementById("chart-featured-price");
  const changeEl = document.getElementById("chart-featured-change");
  const natureEl = document.getElementById("chart-price-nature");
  const statusEl = document.getElementById("chart-replay-status");
  const highEl = document.getElementById("chart-stat-high");
  const lowEl = document.getElementById("chart-stat-low");
  const timeEl = document.getElementById("chart-stat-time");

  if (badgeEl) badgeEl.textContent = currentChartAsset;
  if (nameEl) nameEl.textContent = meta.name;
  if (pairEl) pairEl.textContent = meta.pair;

  const curPriceObj = currentPrices[currentChartAsset];
  const priceVal = curPriceObj?.price_cop || (lastReplayState?.prices?.[currentChartAsset]) || 0;
  if (priceEl) priceEl.textContent = formatCOP(priceVal);

  const chg = curPriceObj?.change_24h || (lastReplayState?.variations_24h?.[currentChartAsset]) || 0;
  if (changeEl) {
    changeEl.textContent = (chg >= 0 ? "+" : "") + Number(chg).toFixed(2) + "%";
    changeEl.className = "badge " + (chg >= 0 ? "badge-success" : "badge-danger");
  }

  const isObserved = (curPriceObj?.nature === "OBSERVADO_REAL") || (lastReplayState?.price_type === "OBSERVADO_REAL");
  if (natureEl) {
    natureEl.textContent = isObserved ? "Cotización Real" : "Interpolado";
    natureEl.className = "asset-nature-badge" + (isObserved ? "" : " interpolated");
  }

  if (statusEl && lastReplayState) {
    if (lastReplayState.is_completed) {
      statusEl.className = "badge badge-danger";
      statusEl.textContent = "Mercado Finalizado";
    } else if (lastReplayState.status === "RUNNING") {
      statusEl.className = "badge badge-success";
      statusEl.textContent = `En Reproducción (${lastReplayState.speed}x)`;
    } else {
      statusEl.className = "badge badge-warning";
      statusEl.textContent = "Pausado";
    }
  }

  // Period High / Low
  const stats = lastReplayState?.stats_period?.[currentChartAsset];
  if (stats) {
    if (highEl) highEl.textContent = formatCOP(stats.high_cop);
    if (lowEl) lowEl.textContent = formatCOP(stats.low_cop);
  } else if (priceVal > 0) {
    if (highEl) highEl.textContent = formatCOP(priceVal * 1.0025);
    if (lowEl) lowEl.textContent = formatCOP(priceVal * 0.9975);
  }

  // Simulated Time
  const simIso = lastReplayState?.simulated_datetime_cot_iso || lastReplayState?.simulated_datetime_iso;
  if (timeEl && simIso) {
    timeEl.textContent = (simIso.length >= 19 ? simIso.substring(11, 19) : simIso) + " COT";
  } else if (timeEl && lastReplayState?.display_time_cot) {
    timeEl.textContent = lastReplayState.display_time_cot;
  }
}

// Fallback SVG chart in case external libraries are disabled
function renderFallbackSvgChart(container, history) {
  if (!container) return;
  let pts = (history || []).map(h => h[currentChartAsset] || 0).filter(p => p > 0);
  if (pts.length === 0) {
    const curP = currentPrices[currentChartAsset]?.price_cop || lastReplayState?.prices?.[currentChartAsset] || 0;
    if (curP > 0) pts = [curP, curP];
    else return;
  } else if (pts.length === 1) {
    pts = [pts[0], pts[0]];
  }

  const minP = Math.min(...pts) * 0.998;
  const maxP = Math.max(...pts) * 1.002;
  const rangeP = (maxP - minP) || 1;
  const width = container.clientWidth || 800;
  const height = container.clientHeight || 380;
  const padLeft = 85;
  const padRight = 30;
  const padTop = 30;
  const padBottom = 35;
  const graphW = width - padLeft - padRight;
  const graphH = height - padTop - padBottom;

  let pointsStr = "";
  const total = history.length;
  history.forEach((h, idx) => {
    const x = padLeft + (idx / (total - 1)) * graphW;
    const y = padTop + graphH - (((h[currentChartAsset] || minP) - minP) / rangeP) * graphH;
    pointsStr += `${idx === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)} `;
  });

  const lastPt = history[history.length - 1];
  const lastX = padLeft + graphW;
  const lastY = padTop + graphH - (((lastPt[currentChartAsset] || minP) - minP) / rangeP) * graphH;

  container.innerHTML = `
    <svg width="100%" height="100%" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" style="display:block;">
      <defs>
        <linearGradient id="gradTerm" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#00C98D" stop-opacity="0.38"/>
          <stop offset="100%" stop-color="#00C98D" stop-opacity="0.0"/>
        </linearGradient>
      </defs>
      <line x1="${padLeft}" y1="${padTop}" x2="${width - padRight}" y2="${padTop}" stroke="#1B2A3C" stroke-dasharray="3,3"/>
      <line x1="${padLeft}" y1="${padTop + graphH / 2}" x2="${width - padRight}" y2="${padTop + graphH / 2}" stroke="#1B2A3C" stroke-dasharray="3,3"/>
      <line x1="${padLeft}" y1="${padTop + graphH}" x2="${width - padRight}" y2="${padTop + graphH}" stroke="#1B2A3C"/>
      <path d="${pointsStr} L ${lastX} ${padTop + graphH} L ${padLeft} ${padTop + graphH} Z" fill="url(#gradTerm)"/>
      <path d="${pointsStr}" fill="none" stroke="#00C98D" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="${lastX}" cy="${lastY}" r="5" fill="#00C98D" stroke="#fff" stroke-width="2"/>
    </svg>
  `;
}

// Polling Loop (Fast 2.5s for smooth synchronized replay)
function startPolling() {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(() => {
    fetchProfile();
    fetchPrices();
  }, 2500);
}

// Render Dashboard Data
function updateDashboardUI() {
  if (!currentParticipant) return;

  const p = currentParticipant;
  const bankCOP = p.bank_balance_cop || 0;
  const walletCOP = p.wallet_cop || 0;

  // Calculate crypto valuations in COP
  let cryptoTotalCOP = 0;
  const assets = [
    { key: "BTC", name: "Bitcoin", iconClass: "icon-btc", bal: p.wallet_btc || 0 },
    { key: "ETH", name: "Ethereum", iconClass: "icon-eth", bal: p.wallet_eth || 0 },
    { key: "USDT", name: "Tether USD", iconClass: "icon-usdt", bal: p.wallet_usdt || 0 },
    { key: "SOL", name: "Solana", iconClass: "icon-sol", bal: p.wallet_sol || 0 }
  ];

  assets.forEach(a => {
    const price = currentPrices[a.key]?.price_cop || 0;
    a.valCOP = a.bal * price;
    cryptoTotalCOP += a.valCOP;
  });

  const totalPatrimonio = bankCOP + walletCOP + cryptoTotalCOP;

  document.getElementById("stat-bank-cop").textContent = formatCOP(bankCOP);
  document.getElementById("stat-wallet-cop").textContent = formatCOP(walletCOP);
  document.getElementById("stat-wallet-crypto-cop").textContent = formatCOP(cryptoTotalCOP);
  document.getElementById("stat-total-patrimonio").textContent = formatCOP(totalPatrimonio);

  // Render Portfolio Asset List
  const listEl = document.getElementById("assets-list");
  let html = `
    <div class="asset-item">
      <div class="asset-info">
        <div class="asset-icon icon-cop">COP</div>
        <div>
          <div style="font-weight: 700; color: #fff;">Pesos Colombianos (COP)</div>
          <div style="font-size: 0.78rem; color: var(--text-dim);">Moneda Base de Liquidación</div>
        </div>
      </div>
      <div style="text-align: right;">
        <div class="mono" style="font-weight: 700; color: #fff;">${formatCOP(walletCOP)}</div>
        <div style="font-size: 0.75rem; color: var(--accent);">Disponible en Billetera</div>
      </div>
    </div>
  `;

  assets.forEach(a => {
    const pr = currentPrices[a.key]?.price_cop || 0;
    html += `
      <div class="asset-item">
        <div class="asset-info">
          <div class="asset-icon ${a.iconClass}">${a.key}</div>
          <div>
            <div style="font-weight: 700; color: #fff;">${a.name} (${a.key})</div>
            <div style="font-size: 0.78rem; color: var(--text-dim);">Tasa actual: ${formatCOP(pr)}</div>
          </div>
        </div>
        <div style="text-align: right;">
          <div class="mono" style="font-weight: 700; color: #fff;">${formatCrypto(a.bal, a.key)}</div>
          <div class="mono" style="font-size: 0.75rem; color: var(--accent);">≈ ${formatCOP(a.valCOP)}</div>
        </div>
      </div>
    `;
  });

  listEl.innerHTML = html;
}

function generateSparklineSvg(asset, history) {
  if (!history || history.length < 2) {
    return `<div style="color:var(--text-dim);font-size:0.75rem;">—</div>`;
  }
  const subset = history.slice(-20);
  const pts = subset.map(h => h[asset]).filter(p => p && p > 0);
  if (pts.length < 2) {
    return `<div style="color:var(--text-dim);font-size:0.75rem;">—</div>`;
  }

  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const range = (max - min) || 1;
  const w = 70;
  const h = 24;

  const pointsStr = pts.map((val, idx) => {
    const x = (idx / (pts.length - 1)) * (w - 4) + 2;
    const y = h - 2 - ((val - min) / range) * (h - 6);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  const isUp = pts[pts.length - 1] >= pts[0];
  const color = isUp ? "#00C98D" : "#EF4444";

  return `
    <svg class="sparkline-svg" viewBox="0 0 ${w} ${h}">
      <polyline fill="none" stroke="${color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" points="${pointsStr}"/>
    </svg>
  `;
}

// Market Table Render with Sparklines & Fast Execution
function renderMarketTable() {
  const tbody = document.getElementById("market-table-body");
  if (!tbody) return;

  let html = "";
  const order = ["BTC", "ETH", "USDT", "SOL"];
  const hist = lastReplayState?.chart_history || [];

  order.forEach(asset => {
    const item = currentPrices[asset];
    if (!item) return;

    const curP = item.price_cop || 0;
    let flashClass = "";
    if (prevPrices[asset] !== undefined && prevPrices[asset] !== curP) {
      flashClass = curP > prevPrices[asset] ? "flash-up" : "flash-down";
    }
    prevPrices[asset] = curP;

    const chg = item.change_24h || 0;
    const chgBadge = chg >= 0 
      ? `<span class="badge badge-success">+${chg}%</span>` 
      : `<span class="badge badge-danger">${chg}%</span>`;

    const isObserved = (item.nature === "OBSERVADO_REAL") || (lastReplayState?.price_type === "OBSERVADO_REAL");
    const natureBadge = isObserved
      ? `<span class="badge badge-success" style="font-size: 0.68rem;">Real</span>`
      : `<span class="badge badge-info" style="font-size: 0.68rem;">Interpolado</span>`;

    const rawUsd = item.price_usd_raw 
      ? `<div style="font-size: 0.72rem; color: var(--text-dim);">$${Number(item.price_usd_raw).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: (asset==='USDT'?4:2)})} USD</div>`
      : '';

    const stats = lastReplayState?.stats_period?.[asset];
    const rangeStr = stats 
      ? `<div class="mono" style="font-size: 0.74rem; color: var(--text-dim);">${formatCOP(stats.low_cop).replace('COP ','')}<br/>${formatCOP(stats.high_cop).replace('COP ','')}</div>`
      : `<span style="font-size:0.75rem; color:var(--text-dim);">—</span>`;

    const sparklineHtml = generateSparklineSvg(asset, hist);

    html += `
      <tr>
        <td>
          <div style="display: flex; align-items: center; gap: 0.6rem;">
            <div class="asset-icon icon-${asset.toLowerCase()}" style="width: 28px; height: 28px; font-size: 0.7rem; cursor: pointer;" onclick="switchChartAsset('${asset}')">${asset}</div>
            <div>
              <span style="font-weight: 700; cursor: pointer;" onclick="switchChartAsset('${asset}')">${asset}</span>
              ${rawUsd}
            </div>
          </div>
        </td>
        <td class="mono ${flashClass}" style="font-weight: 700;">${formatCOP(curP)}</td>
        <td>${chgBadge}</td>
        <td>${rangeStr}</td>
        <td>${sparklineHtml}</td>
        <td>${natureBadge}</td>
        <td class="text-right">
          <div style="display: inline-flex; gap: 0.35rem;">
            <button type="button" class="btn-quick-buy" onclick="quickTrade('${asset}', 'BUY')">Comprar</button>
            <button type="button" class="btn-quick-sell" onclick="quickTrade('${asset}', 'SELL')">Vender</button>
          </div>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
}

function quickTrade(asset, side) {
  switchTab("tab-trade");
  setTradeSide(side);
  const select = document.getElementById("trade-asset");
  if (select) select.value = asset;
  updateTradeCalculator();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function setTradeAmountPercent(pct) {
  if (!currentParticipant) return;
  const asset = document.getElementById("trade-asset").value;
  const price = currentPrices[asset]?.price_cop || 0;
  if (!price || price <= 0) return;

  const amtInput = document.getElementById("trade-amount");
  if (currentTradeSide === "BUY") {
    const availCOP = currentParticipant.wallet_cop || 0;
    const budgetCOP = availCOP * pct;
    const cryptoAmt = budgetCOP / (price * 1.002);
    amtInput.value = (asset === "USDT" ? cryptoAmt.toFixed(2) : cryptoAmt.toFixed(6));
  } else {
    const balProp = `wallet_${asset.toLowerCase()}`;
    const availCrypto = currentParticipant[balProp] || 0;
    const cryptoAmt = availCrypto * pct;
    amtInput.value = (asset === "USDT" ? cryptoAmt.toFixed(2) : cryptoAmt.toFixed(6));
  }
  updateTradeCalculator();

  document.querySelectorAll(".pct-chip").forEach((chip, idx) => {
    const chipPcts = [0.25, 0.50, 0.75, 1.00];
    chip.classList.toggle("active", chipPcts[idx] === pct);
  });
}

// BANK ⇄ WALLET TRANSFER
function updateBankAvailable() {
  if (!currentParticipant) return;
  const dir = document.getElementById("bank-direction").value;
  const label = document.getElementById("bank-available-label");
  const avail = dir === "DEPOSIT" ? (currentParticipant.bank_balance_cop || 0) : (currentParticipant.wallet_cop || 0);
  label.textContent = `Disponible: ${formatCOP(avail)}`;
}

function setBankAmountPercent(pct) {
  if (!currentParticipant) return;
  const dir = document.getElementById("bank-direction").value;
  const avail = dir === "DEPOSIT" ? (currentParticipant.bank_balance_cop || 0) : (currentParticipant.wallet_cop || 0);
  const amt = Math.floor(avail * pct);
  document.getElementById("bank-amount").value = amt;
}

async function handleBankTransfer(e) {
  e.preventDefault();
  const dir = document.getElementById("bank-direction").value;
  const amt = parseFloat(document.getElementById("bank-amount").value);
  if (!amt || amt <= 0) return;

  const btn = document.getElementById("btn-submit-bank");
  btn.disabled = true;

  try {
    const res = await fetch("/api/participant/bank-transfer", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${currentToken}`
      },
      body: JSON.stringify({ action: dir, amount: amt })
    });
    const data = await res.json();
    if (!res.ok) {
      showNotification(data.detail || "Error en traslado bancario", "danger");
      return;
    }

    showNotification(`Traslado de ${formatCOP(amt)} completado con éxito.`, "success");
    document.getElementById("bank-amount").value = "";
    await fetchProfile();
    updateBankAvailable();
  } catch (err) {
    showNotification("Error de conexión al procesar traslado.", "danger");
  } finally {
    btn.disabled = false;
  }
}

// TRADING LOGIC
function setTradeSide(side) {
  currentTradeSide = side;
  const buyBtn = document.getElementById("btn-side-buy");
  const sellBtn = document.getElementById("btn-side-sell");
  const submitBtn = document.getElementById("btn-submit-trade");

  if (side === "BUY") {
    buyBtn.className = "btn btn-primary";
    sellBtn.className = "btn btn-secondary";
    submitBtn.className = "btn btn-primary btn-block btn-lg";
    submitBtn.innerHTML = "<span>Comprar Criptoactivo</span>";
    document.getElementById("trade-input-label").textContent = "Cantidad a Comprar";
    document.getElementById("summary-total-label").textContent = "Total COP a Debitar:";
  } else {
    buyBtn.className = "btn btn-secondary";
    sellBtn.className = "btn btn-primary";
    submitBtn.className = "btn btn-primary btn-block btn-lg";
    submitBtn.style.background = "#ef4444";
    submitBtn.innerHTML = "<span>Vender Criptoactivo</span>";
    document.getElementById("trade-input-label").textContent = "Cantidad a Vender";
    document.getElementById("summary-total-label").textContent = "Neto COP a Acreditar:";
  }
  updateTradeCalculator();
}

function updateTradeCalculator() {
  if (!currentParticipant) return;
  const asset = document.getElementById("trade-asset").value;
  const item = currentPrices[asset];
  const unitPrice = item?.price_cop || 0;
  document.getElementById("trade-unit-price").textContent = formatCOP(unitPrice);
  document.getElementById("trade-unit-symbol").textContent = asset;

  // Nature badge
  const isObserved = (item?.nature === "OBSERVADO_REAL") || (lastReplayState?.price_type === "OBSERVADO_REAL");
  const natureBadge = document.getElementById("trade-nature-badge");
  if (natureBadge) {
    if (isObserved) {
      natureBadge.className = "badge badge-success";
      natureBadge.textContent = "Observado Real";
      natureBadge.title = "Dato real histórico directo de CoinGecko";
    } else {
      natureBadge.className = "badge badge-info";
      natureBadge.textContent = "Calculado (Interpolado)";
      natureBadge.title = "Precio interpolado ponderado entre registros reales";
    }
  }

  // Simulated Time in COT
  const simTimeEl = document.getElementById("trade-sim-time-cot");
  if (simTimeEl) {
    if (lastReplayState && lastReplayState.simulated_datetime_formatted) {
      simTimeEl.textContent = lastReplayState.simulated_datetime_formatted;
    } else if (lastReplayState && lastReplayState.simulated_datetime_cot_iso) {
      simTimeEl.textContent = lastReplayState.simulated_datetime_cot_iso.replace("T", " ");
    }
  }

  const col = `wallet_${asset.toLowerCase()}`;
  const cryptoBal = currentParticipant[col] || 0;
  const copBal = currentParticipant.wallet_cop || 0;

  if (currentTradeSide === "BUY") {
    document.getElementById("trade-balance-label").textContent = "Billetera COP Disponible:";
    document.getElementById("trade-available-balance").textContent = formatCOP(copBal);
  } else {
    document.getElementById("trade-balance-label").textContent = `Saldo disponible en ${asset}:`;
    document.getElementById("trade-available-balance").textContent = `${cryptoBal} ${asset}`;
  }

  const amt = parseFloat(document.getElementById("trade-amount").value) || 0;
  const gross = amt * unitPrice;
  const fee = gross * 0.002; // 0.2%

  document.getElementById("summary-subtotal").textContent = formatCOP(gross);
  document.getElementById("summary-fee").textContent = formatCOP(fee);

  if (currentTradeSide === "BUY") {
    const total = gross + fee;
    document.getElementById("summary-total").textContent = formatCOP(total);
  } else {
    const total = Math.max(0, gross - fee);
    document.getElementById("summary-total").textContent = formatCOP(total);
  }
}

function useMaxTradeBalance() {
  const asset = document.getElementById("trade-asset").value;
  const unitPrice = currentPrices[asset]?.price_cop || 0;
  if (unitPrice <= 0) return;

  if (currentTradeSide === "BUY") {
    const copBal = currentParticipant.wallet_cop || 0;
    const maxCrypto = copBal / (unitPrice * 1.002);
    document.getElementById("trade-amount").value = maxCrypto > 0 ? Number(maxCrypto.toFixed(8)) : 0;
  } else {
    const col = `wallet_${asset.toLowerCase()}`;
    const cryptoBal = currentParticipant[col] || 0;
    document.getElementById("trade-amount").value = cryptoBal;
  }
  updateTradeCalculator();
}

function handleTradeSubmit(e) {
  e.preventDefault();
  const asset = document.getElementById("trade-asset").value;
  const amt = parseFloat(document.getElementById("trade-amount").value);
  if (!amt || amt <= 0) return;

  const item = currentPrices[asset];
  const unitPrice = item?.price_cop || 0;
  const gross = amt * unitPrice;
  const fee = gross * 0.002;
  const total = currentTradeSide === "BUY" ? (gross + fee) : (gross - fee);

  const isObserved = (item?.nature === "OBSERVADO_REAL") || (lastReplayState?.price_type === "OBSERVADO_REAL");
  const simTimeDisplay = (lastReplayState && lastReplayState.simulated_datetime_formatted) || "10 Nov 2026 COT";

  const body = `
    <div style="background: rgba(10, 15, 29, 0.7); border: 1px solid var(--border-color); border-radius: 6px; padding: 1rem;">
      <p style="margin-bottom: 0.5rem;"><strong>Operación:</strong> ${currentTradeSide === 'BUY' ? 'Compra de Criptoactivo' : 'Venta de Criptoactivo'}</p>
      <p style="margin-bottom: 0.5rem;"><strong>Activo:</strong> ${amt} ${asset}</p>
      <p style="margin-bottom: 0.5rem;"><strong>Precio Unitario:</strong> ${formatCOP(unitPrice)} <span class="badge ${isObserved ? 'badge-success' : 'badge-info'}" style="font-size:0.68rem;">${isObserved ? 'Observado Real' : 'Calculado Interpolado'}</span></p>
      <p style="margin-bottom: 0.5rem; font-size: 0.8rem; color: var(--text-dim);"><strong>Hora Histórica (COT):</strong> ${simTimeDisplay}</p>
      <p style="margin-bottom: 0.5rem;"><strong>Subtotal Bruto:</strong> ${formatCOP(gross)}</p>
      <p style="margin-bottom: 0.5rem; color: var(--warning);"><strong>Comisión (0.2%):</strong> ${formatCOP(fee)}</p>
      <hr style="border: none; border-top: 1px solid var(--border-color); margin: 0.75rem 0;">
      <p style="font-size: 1.05rem; font-weight: 700; color: #fff;">
        ${currentTradeSide === 'BUY' ? 'Total COP a Debitar:' : 'Total Neto a Recibir:'} ${formatCOP(total)}
      </p>
    </div>
  `;

  openModal("Confirmar Operación de Mercado", body, async () => {
    closeModal("modal-confirm");
    const btn = document.getElementById("btn-submit-trade");
    btn.disabled = true;

    try {
      const res = await fetch("/api/participant/trade", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${currentToken}`
        },
        body: JSON.stringify({
          side: currentTradeSide,
          asset: asset,
          amount: amt,
          quote_type: "CRYPTO"
        })
      });
      const data = await res.json();
      if (!res.ok) {
        showNotification(data.detail || "Error al procesar orden de mercado.", "danger");
        return;
      }

      showNotification(`Orden de ${currentTradeSide} completada con éxito.`, "success");
      document.getElementById("trade-amount").value = "";
      await fetchProfile();
      updateTradeCalculator();
    } catch (err) {
      showNotification("Error de red al ejecutar orden.", "danger");
    } finally {
      btn.disabled = false;
    }
  });
}

// TRANSFERS LOGIC
function setTransferType(type) {
  currentTransferType = type;
  const btnInt = document.getElementById("btn-type-internal");
  const btnExt = document.getElementById("btn-type-external");
  const groupInt = document.getElementById("group-dest-internal");
  const groupExt = document.getElementById("group-dest-external");

  if (type === "INTERNAL") {
    btnInt.className = "btn btn-accent";
    btnExt.className = "btn btn-secondary";
    groupInt.style.display = "block";
    groupExt.style.display = "none";
  } else {
    btnInt.className = "btn btn-secondary";
    btnExt.className = "btn btn-accent";
    groupInt.style.display = "none";
    groupExt.style.display = "block";
  }
}

async function fetchRoomPeers() {
  if (!currentToken) return;
  try {
    const res = await fetch("/api/participant/room-peers", {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      const select = document.getElementById("select-peer");
      if (select) {
        select.innerHTML = '<option value="">Elegir participante...</option>';
        (data.peers || []).forEach(peer => {
          select.innerHTML += `<option value="${peer}">${peer}</option>`;
        });
      }
    }
  } catch (e) {}
}

function updateTransferMaxBalance() {
  if (!currentParticipant) return;
  const asset = document.getElementById("transfer-asset").value;
  const col = asset === "COP" ? "wallet_cop" : `wallet_${asset.lower ? asset.toLowerCase() : asset.toLowerCase()}`;
  const bal = currentParticipant[col] || 0;
  document.getElementById("transfer-avail-label").textContent = `Disponible: ${bal} ${asset}`;
}

function useMaxTransfer() {
  if (!currentParticipant) return;
  const asset = document.getElementById("transfer-asset").value;
  const col = asset === "COP" ? "wallet_cop" : `wallet_${asset.toLowerCase()}`;
  document.getElementById("transfer-amount").value = currentParticipant[col] || 0;
}

function generateSimulatedAddress() {
  const chars = "0123456789abcdef";
  let hex = "0x";
  for (let i = 0; i < 40; i++) hex += chars[Math.floor(Math.random() * chars.length)];
  document.getElementById("transfer-dest-external").value = hex;
}

function handleTransferSubmit(e) {
  e.preventDefault();
  const asset = document.getElementById("transfer-asset").value;
  const amt = parseFloat(document.getElementById("transfer-amount").value);
  const notes = document.getElementById("transfer-notes").value.trim();

  let dest = "";
  if (currentTransferType === "INTERNAL") {
    dest = document.getElementById("transfer-dest-alias").value.trim();
    if (!dest) {
      showNotification("Indica el alias de destino.", "warning");
      return;
    }
  } else {
    dest = document.getElementById("transfer-dest-external").value.trim();
    if (!dest) {
      showNotification("Indica la dirección externa simulada.", "warning");
      return;
    }
  }

  const body = `
    <div style="background: rgba(10, 15, 29, 0.7); border: 1px solid var(--border-color); border-radius: 6px; padding: 1rem;">
      <p style="margin-bottom: 0.5rem;"><strong>Tipo:</strong> ${currentTransferType === 'INTERNAL' ? 'Transferencia Interna (Participante)' : 'Transferencia Externa (Salida del Perímetro)'}</p>
      <p style="margin-bottom: 0.5rem;"><strong>Activo:</strong> ${amt} ${asset}</p>
      <p style="margin-bottom: 0.5rem;"><strong>Destino:</strong> <span class="mono" style="color: var(--accent);">${dest}</span></p>
      ${currentTransferType === 'EXTERNAL' ? '<p style="color:#fca5a5; font-size:0.8rem; margin-top:0.5rem;">Nota: La trazabilidad interna concluirá en esta dirección externa simulada.</p>' : ''}
    </div>
  `;

  openModal("Confirmar Transferencia", body, async () => {
    closeModal("modal-confirm");
    const btn = document.getElementById("btn-submit-transfer");
    btn.disabled = true;

    try {
      const res = await fetch("/api/participant/transfer", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${currentToken}`
        },
        body: JSON.stringify({
          transfer_type: currentTransferType,
          asset: asset,
          amount: amt,
          destination_alias: currentTransferType === "INTERNAL" ? dest : null,
          external_address: currentTransferType === "EXTERNAL" ? dest : null,
          notes: notes
        })
      });
      const data = await res.json();
      if (!res.ok) {
        showNotification(data.detail || "Error en la transferencia.", "danger");
        return;
      }

      showNotification(`Transferencia de ${amt} ${asset} procesada con éxito. Hash: ${data.tx_hash.substring(0, 16)}...`, "success");
      document.getElementById("transfer-amount").value = "";
      document.getElementById("transfer-notes").value = "";
      await fetchProfile();
      updateTransferMaxBalance();
    } catch (err) {
      showNotification("Error de red al transferir.", "danger");
    } finally {
      btn.disabled = false;
    }
  });
}

// HISTORY LOGIC
async function fetchHistory() {
  if (!currentToken) return;
  try {
    const res = await fetch("/api/participant/history", {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      renderHistoryTable(data.transactions || []);
    }
  } catch (err) {}
}

function renderHistoryTable(txs) {
  const tbody = document.getElementById("history-table-body");
  if (!tbody) return;

  if (txs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-dim); padding: 2.5rem;">No tienes transacciones registradas aún.</td></tr>`;
    return;
  }

  let html = "";
  txs.forEach(tx => {
    let typeBadge = "";
    let origin = "";
    let destination = "";
    let valCOP = 0;
    const isMeSender = (tx.sender_alias === currentParticipant.alias);

    if (tx.tx_type === "DEPOSIT_INITIAL_ENDOWMENT") {
      typeBadge = `<span class="badge badge-info">Saldo Inicial</span>`;
      origin = "Sistema Central";
      destination = tx.receiver_alias;
      valCOP = tx.amount;
    } else if (tx.tx_type === "DEPOSIT_BANK_TO_WALLET") {
      typeBadge = `<span class="badge badge-success">Banco → Billetera</span>`;
      origin = "Cuenta Bancaria";
      destination = "Billetera COP";
      valCOP = tx.amount;
    } else if (tx.tx_type === "WITHDRAW_WALLET_TO_BANK") {
      typeBadge = `<span class="badge badge-info">Billetera → Banco</span>`;
      origin = "Billetera COP";
      destination = "Cuenta Bancaria";
      valCOP = tx.amount;
    } else if (tx.tx_type === "BUY_CRYPTO") {
      typeBadge = `<span class="badge badge-success">Compra Cripto</span>`;
      origin = tx.sender_alias;
      destination = "Mercado Simulado";
      valCOP = tx.gross_amount_cop || (tx.amount * (tx.unit_price_cop || 0));
    } else if (tx.tx_type === "SELL_CRYPTO") {
      typeBadge = `<span class="badge badge-warning">Venta Cripto</span>`;
      origin = tx.sender_alias;
      destination = "Mercado Simulado";
      valCOP = tx.gross_amount_cop || (tx.amount * (tx.unit_price_cop || 0));
    } else if (tx.tx_type === "TRANSFER_INTERNAL") {
      if (isMeSender) {
        typeBadge = `<span class="badge badge-warning">Envío P2P</span>`;
      } else {
        typeBadge = `<span class="badge badge-success">Recepción P2P</span>`;
      }
      origin = tx.sender_alias;
      destination = tx.receiver_alias;
      if (tx.asset === "COP") {
        valCOP = tx.amount;
      } else {
        const pr = currentPrices[tx.asset]?.price_cop || tx.unit_price_cop || 0;
        valCOP = tx.gross_amount_cop || (tx.amount * pr);
      }
    } else if (tx.tx_type === "TRANSFER_EXTERNAL") {
      typeBadge = `<span class="badge badge-danger">Salida Externa</span>`;
      origin = tx.sender_alias;
      destination = `${tx.receiver_alias.substring(0, 10)}... (Externa)`;
      if (tx.asset === "COP") {
        valCOP = tx.amount;
      } else {
        const pr = currentPrices[tx.asset]?.price_cop || tx.unit_price_cop || 0;
        valCOP = tx.gross_amount_cop || (tx.amount * pr);
      }
    }

    const feeText = tx.fee_cop > 0 ? formatCOP(tx.fee_cop) : "0 COP";
    const statusBadge = tx.status === 'CONFIRMED' 
      ? (tx.tx_type === 'TRANSFER_EXTERNAL' ? '<span class="badge badge-danger">Salida Perímetro</span>' : '<span class="badge badge-success">Confirmada</span>')
      : (tx.status === 'REVERSED' ? '<span class="badge badge-warning">Reversada</span>' : `<span class="badge badge-neutral">${tx.status}</span>`);

    const shortHash = `${tx.tx_hash.substring(0, 8)}...${tx.tx_hash.substring(tx.tx_hash.length - 6)}`;
    const timeDisplay = tx.created_at.replace("T", " ").substring(0, 19);

    html += `
      <tr>
        <td style="color: var(--text-dim); font-size: 0.78rem;" class="mono">${timeDisplay}</td>
        <td>${typeBadge}</td>
        <td style="font-size: 0.82rem; font-weight: 600;">${origin}</td>
        <td style="font-size: 0.82rem; font-weight: 600;">${destination}</td>
        <td style="font-weight: 700;">${tx.asset}</td>
        <td class="mono text-right" style="font-weight: 700;">${tx.asset === 'COP' ? formatCOP(tx.amount) : formatCrypto(tx.amount, tx.asset)}</td>
        <td class="mono text-right" style="color: var(--text-muted);">${formatCOP(valCOP)}</td>
        <td class="mono text-right" style="color: var(--text-dim); font-size: 0.8rem;">${feeText}</td>
        <td>${statusBadge}</td>
        <td>
          <span class="mono" style="font-size: 0.74rem; color: var(--accent); cursor: pointer;" title="Copiar Hash" onclick="navigator.clipboard.writeText('${tx.tx_hash}'); showNotification('Hash copiado al portapapeles', 'info')">
            ${shortHash}
          </span>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
}

// Modal Helpers
function openModal(title, bodyHTML, onConfirm) {
  document.getElementById("modal-confirm-title").textContent = title;
  document.getElementById("modal-confirm-body").innerHTML = bodyHTML;
  const btn = document.getElementById("modal-btn-confirm-action");
  btn.onclick = onConfirm;
  document.getElementById("modal-confirm").classList.add("open");
}

function closeModal(id) {
  document.getElementById(id).classList.remove("open");
}
