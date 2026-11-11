// CRYPTO LAB - Admin & Forensic Investigation Logic
let adminToken = localStorage.getItem("cryptolab_admin_token") || null;
let currentRooms = [];
let activeRoomCode = null;
let currentInvestigationData = null;
let networkGraph = null;

function formatCOP(num) {
  if (num === null || num === undefined || isNaN(num)) return "COP 0,00";
  return "COP " + Number(num).toLocaleString("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatCrypto(num, asset) {
  if (num === null || num === undefined || isNaN(num)) return `0 ${asset}`;
  const dec = (asset === "BTC" || asset === "ETH") ? 6 : (asset === "SOL" ? 4 : 2);
  return `${Number(num).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: dec })} ${asset}`;
}

document.addEventListener("DOMContentLoaded", () => {
  // Setup Tab listeners
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      switchAdminTab(tabId);
    });
  });

  document.getElementById("form-admin-login").addEventListener("submit", handleAdminLogin);
  document.getElementById("btn-admin-logout").addEventListener("click", handleAdminLogout);

  if (adminToken) {
    verifyAdminSession();
  } else {
    showLoginView();
  }
});

function switchAdminTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-pane").forEach(p => p.style.display = "none");

  const targetBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
  if (targetBtn) targetBtn.classList.add("active");

  const pane = document.getElementById(tabId);
  if (pane) pane.style.display = "block";

  if (tabId === "tab-admin-rooms") {
    loadRooms();
    loadNetworkInfo();
  } else if (tabId === "tab-admin-monitor") {
    loadRoomStats();
  } else if (tabId === "tab-admin-forensics") {
    populateForensicParticipantDropdown();
  }
}

function showLoginView() {
  document.getElementById("view-admin-login").style.display = "block";
  document.getElementById("view-admin-dashboard").style.display = "none";
  document.getElementById("admin-nav-right").style.display = "none";
}

function showDashboardView(username) {
  document.getElementById("view-admin-login").style.display = "none";
  document.getElementById("view-admin-dashboard").style.display = "block";
  document.getElementById("admin-nav-right").style.display = "flex";
  document.getElementById("admin-user-label").textContent = `Docente: ${username}`;

  loadRooms();
  loadNetworkInfo();
}

async function handleAdminLogin(e) {
  e.preventDefault();
  const u = document.getElementById("admin-username").value.trim();
  const p = document.getElementById("admin-password").value;
  const alertEl = document.getElementById("admin-login-alert");
  alertEl.style.display = "none";

  const btn = document.getElementById("btn-admin-submit-login");
  btn.disabled = true;

  try {
    const res = await fetch("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: u, password: p })
    });
    const data = await res.json();
    if (!res.ok) {
      alertEl.textContent = data.detail || "Credenciales incorrectas.";
      alertEl.style.display = "block";
      return;
    }

    adminToken = data.token;
    localStorage.setItem("cryptolab_admin_token", adminToken);
    showDashboardView(data.username);
  } catch (err) {
    alertEl.textContent = "Error al conectar con el servidor.";
    alertEl.style.display = "block";
  } finally {
    btn.disabled = false;
  }
}

async function verifyAdminSession() {
  try {
    const res = await fetch("/api/admin/me", {
      headers: { "Authorization": `Bearer ${adminToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      showDashboardView(data.username);
    } else {
      handleAdminLogout();
    }
  } catch (err) {
    showLoginView();
  }
}

function handleAdminLogout() {
  localStorage.removeItem("cryptolab_admin_token");
  adminToken = null;
  showLoginView();
}

// NETWORK INFO
async function loadNetworkInfo() {
  try {
    const res = await fetch("/api/network-info");
    if (res.ok) {
      const data = await res.json();
      const el = document.getElementById("net-info-box");
      if (el) {
        el.innerHTML = `
          <div style="margin-bottom: 0.3rem;"><strong>IP Local (Wi-Fi):</strong> <span style="color: var(--accent);">${data.lan_ip}</span> (Puerto: ${data.port})</div>
          <div style="margin-bottom: 0.3rem;"><strong>Enlace para Dispositivos Móviles:</strong> <a href="${data.participant_url}" target="_blank" style="color: var(--primary); text-decoration: underline;">${data.participant_url}</a></div>
          <div><strong>Enlace Local (Este equipo):</strong> <a href="${data.local_participant_url}" target="_blank" style="color: var(--text-muted); text-decoration: underline;">${data.local_participant_url}</a></div>
        `;
      }
    }
  } catch (e) {}
}

// ROOMS MANAGEMENT
async function loadRooms() {
  if (!adminToken) return;
  try {
    const res = await fetch("/api/admin/rooms", {
      headers: { "Authorization": `Bearer ${adminToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();
    currentRooms = data.rooms || [];
    renderRoomsTable();
    updateRoomSelectors();
  } catch (err) {}
}

function renderRoomsTable() {
  const tbody = document.getElementById("rooms-table-body");
  if (!tbody) return;

  if (currentRooms.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-dim); padding: 2rem;">No hay salas creadas. Crea una nueva sala para comenzar.</td></tr>`;
    return;
  }

  let html = "";
  currentRooms.forEach(r => {
    const isOpen = (r.status === "OPEN");
    const statusBadge = isOpen 
      ? `<span class="badge badge-success">ABIERTA</span>` 
      : `<span class="badge badge-danger">CERRADA</span>`;

    html += `
      <tr>
        <td class="mono" style="font-weight: 800; color: var(--accent);">${r.code}</td>
        <td style="font-weight: 600;">${r.name}</td>
        <td class="mono text-right">${formatCOP(r.initial_bank_balance_cop)}</td>
        <td class="mono text-right" style="font-weight: 700;">${r.participant_count}</td>
        <td class="mono text-right">${r.tx_count}</td>
        <td>${statusBadge}</td>
        <td class="text-right">
          <div style="display: inline-flex; gap: 0.4rem;">
            <button class="btn btn-accent btn-sm" onclick="projectRoom('${r.code}')">Proyectar</button>
            <button class="btn btn-secondary btn-sm" onclick="selectAndMonitorRoom('${r.code}')">Monitorear</button>
            <button class="btn ${isOpen ? 'btn-danger' : 'btn-primary'} btn-sm" onclick="toggleRoomStatus('${r.code}', '${isOpen ? 'CLOSED' : 'OPEN'}')">
              ${isOpen ? 'Cerrar' : 'Reabrir'}
            </button>
          </div>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
}

function updateRoomSelectors() {
  const selectMonitor = document.getElementById("select-active-room");
  if (selectMonitor) {
    const currentVal = selectMonitor.value;
    selectMonitor.innerHTML = "";
    currentRooms.forEach(r => {
      selectMonitor.innerHTML += `<option value="${r.code}">${r.code} — ${r.name}</option>`;
    });
    if (currentVal && currentRooms.some(r => r.code === currentVal)) {
      selectMonitor.value = currentVal;
      activeRoomCode = currentVal;
    } else if (currentRooms.length > 0) {
      activeRoomCode = currentRooms[0].code;
      selectMonitor.value = activeRoomCode;
    }
  }
}

function openCreateRoomModal() {
  document.getElementById("modal-create-room").classList.add("open");
}

async function handleCreateRoom(e) {
  e.preventDefault();
  const code = document.getElementById("cr-code").value.trim().toUpperCase();
  const name = document.getElementById("cr-name").value.trim();
  const bal = parseFloat(document.getElementById("cr-balance").value);

  const btn = document.getElementById("btn-submit-create-room");
  btn.disabled = true;

  try {
    const res = await fetch("/api/admin/rooms", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${adminToken}`
      },
      body: JSON.stringify({ code: code, name: name, initial_bank_balance_cop: bal })
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Error al crear sala.");
      return;
    }
    closeModal("modal-create-room");
    await loadRooms();
    selectAndMonitorRoom(code);
  } catch (err) {
    alert("Error de conexión al crear sala.");
  } finally {
    btn.disabled = false;
  }
}

async function toggleRoomStatus(code, newStatus) {
  try {
    const res = await fetch(`/api/admin/rooms/${code}/status?status=${newStatus}`, {
      method: "PATCH",
      headers: { "Authorization": `Bearer ${adminToken}` }
    });
    if (res.ok) {
      await loadRooms();
      if (activeRoomCode === code) loadRoomStats();
    }
  } catch (e) {}
}

function projectRoom(code) {
  activeRoomCode = code;
  openProjectorModal();
}

function selectAndMonitorRoom(code) {
  activeRoomCode = code;
  const select = document.getElementById("select-active-room");
  if (select) select.value = code;
  switchAdminTab("tab-admin-monitor");
  loadRoomStats();
}

// PROJECTOR MODAL
async function openProjectorModal() {
  if (!activeRoomCode) {
    if (currentRooms.length > 0) activeRoomCode = currentRooms[0].code;
    else return;
  }

  const room = currentRooms.find(r => r.code === activeRoomCode) || { code: activeRoomCode, name: "Sesión Crypto Lab" };
  document.getElementById("proj-room-title").textContent = room.name;
  document.getElementById("proj-room-code-badge").textContent = `Código de Sala: ${room.code}`;

  const qrImg = document.getElementById("proj-qr-img");
  qrImg.src = `/api/rooms/${room.code}/qr?format=png&t=${Date.now()}`;

  // Get network URL
  try {
    const netRes = await fetch("/api/network-info");
    const netData = await netRes.json();
    document.getElementById("proj-url-text").textContent = `${netData.participant_url}/?room=${room.code}`;
  } catch (e) {}

  document.getElementById("modal-projector").classList.add("open");
}

// LIVE ROOM MONITOR
async function loadRoomStats() {
  if (!adminToken) return;
  const select = document.getElementById("select-active-room");
  if (select && select.value) activeRoomCode = select.value;
  if (!activeRoomCode) return;

  try {
    const res = await fetch(`/api/admin/rooms/${activeRoomCode}/stats`, {
      headers: { "Authorization": `Bearer ${adminToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();

    const stats = data.stats || {};
    document.getElementById("room-stat-users").textContent = (data.participants || []).length;
    document.getElementById("room-stat-volume").textContent = formatCOP(stats.total_volume_cop || 0);
    document.getElementById("room-stat-fees").textContent = formatCOP(stats.total_fees_cop || 0);
    document.getElementById("room-stat-transfers").textContent = `${stats.internal_transfers || 0} Internas / ${stats.external_transfers || 0} Externas`;

    renderMonitorParticipants(data.participants || []);
    renderMonitorRecentTxs(data.recent_transactions || []);
  } catch (err) {}
}

function renderMonitorParticipants(parts) {
  const tbody = document.getElementById("monitor-participants-table");
  if (!tbody) return;

  if (parts.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-dim); padding: 1.5rem;">Aún no se han unido participantes a esta sala.</td></tr>`;
    return;
  }

  let html = "";
  parts.forEach(p => {
    html += `
      <tr>
        <td style="font-weight: 700; color: #fff;">${p.alias}</td>
        <td class="mono text-right">${formatCOP(p.bank_balance_cop)}</td>
        <td class="mono text-right" style="color: var(--accent);">${formatCOP(p.wallet_cop)}</td>
        <td class="mono text-right">${p.wallet_btc || 0}</td>
        <td class="mono text-right">${p.wallet_eth || 0}</td>
        <td class="mono text-right" style="font-weight: 700;">${p.wallet_usdt || 0}</td>
        <td class="mono text-right">${p.wallet_sol || 0}</td>
        <td class="mono text-right">${p.tx_count || 0}</td>
        <td class="text-right">
          <button class="btn btn-primary btn-sm" onclick="startInvestigationFor('${p.alias}')">
            Auditar
          </button>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
}

function renderMonitorRecentTxs(txs) {
  const tbody = document.getElementById("monitor-recent-txs-table");
  if (!tbody) return;

  if (txs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-dim); padding: 2rem;">Sin operaciones registradas recientemente.</td></tr>`;
    return;
  }

  let html = "";
  txs.forEach(t => {
    let typeBadge = `<span class="badge badge-info">${t.tx_type}</span>`;
    let origin = t.sender_alias || '-';
    let destination = t.receiver_alias || '-';
    let valCOP = 0;

    if (t.tx_type === 'DEPOSIT_INITIAL_ENDOWMENT') {
      typeBadge = `<span class="badge badge-info">Saldo Inicial</span>`;
      origin = "Sistema Central";
      valCOP = t.amount;
    } else if (t.tx_type === 'DEPOSIT_BANK_TO_WALLET') {
      typeBadge = `<span class="badge badge-success">Banco → Billetera</span>`;
      origin = "Cuenta Bancaria";
      destination = "Billetera COP";
      valCOP = t.amount;
    } else if (t.tx_type === 'WITHDRAW_WALLET_TO_BANK') {
      typeBadge = `<span class="badge badge-info">Billetera → Banco</span>`;
      origin = "Billetera COP";
      destination = "Cuenta Bancaria";
      valCOP = t.amount;
    } else if (t.tx_type === 'BUY_CRYPTO') {
      typeBadge = `<span class="badge badge-success">Compra Cripto</span>`;
      destination = "Mercado Simulado";
      valCOP = t.gross_amount_cop || (t.amount * (t.unit_price_cop || 0));
    } else if (t.tx_type === 'SELL_CRYPTO') {
      typeBadge = `<span class="badge badge-warning">Venta Cripto</span>`;
      destination = "Mercado Simulado";
      valCOP = t.gross_amount_cop || (t.amount * (t.unit_price_cop || 0));
    } else if (t.tx_type === 'TRANSFER_INTERNAL') {
      typeBadge = `<span class="badge badge-info">Transferencia P2P</span>`;
      valCOP = t.asset === 'COP' ? t.amount : (t.gross_amount_cop || 0);
    } else if (t.tx_type === 'TRANSFER_EXTERNAL') {
      typeBadge = `<span class="badge badge-danger">Salida Externa</span>`;
      destination = `${(t.receiver_alias || '').substring(0, 10)}... (Externa)`;
      valCOP = t.asset === 'COP' ? t.amount : (t.gross_amount_cop || 0);
    }

    const feeText = t.fee_cop > 0 ? formatCOP(t.fee_cop) : "0 COP";
    const statusBadge = t.status === 'CONFIRMED'
      ? (t.tx_type === 'TRANSFER_EXTERNAL' ? '<span class="badge badge-danger">Salida Perímetro</span>' : '<span class="badge badge-success">Confirmada</span>')
      : `<span class="badge badge-neutral">${t.status}</span>`;

    html += `
      <tr>
        <td style="font-size: 0.78rem; color: var(--text-dim);" class="mono">${t.created_at.replace('T', ' ').substring(0, 19)}</td>
        <td>${typeBadge}</td>
        <td style="font-weight: 600;">${origin}</td>
        <td style="font-weight: 600;">${destination}</td>
        <td style="font-weight: 700;">${t.asset}</td>
        <td class="mono text-right" style="font-weight: 700;">${t.asset === 'COP' ? formatCOP(t.amount) : formatCrypto(t.amount, t.asset)}</td>
        <td class="mono text-right" style="color: var(--text-muted);">${valCOP > 0 ? formatCOP(valCOP) : '-'}</td>
        <td class="mono text-right" style="color: var(--text-dim); font-size: 0.8rem;">${feeText}</td>
        <td>${statusBadge}</td>
        <td><span class="mono" style="font-size: 0.72rem; color: var(--accent); cursor: pointer;" title="Copiar Hash" onclick="navigator.clipboard.writeText('${t.tx_hash}')">${t.tx_hash.substring(0, 8)}...${t.tx_hash.substring(t.tx_hash.length - 6)}</span></td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
}

// FORENSICS MODULE
async function populateForensicParticipantDropdown() {
  if (!activeRoomCode && currentRooms.length > 0) activeRoomCode = currentRooms[0].code;
  if (!activeRoomCode) return;

  try {
    const res = await fetch(`/api/admin/rooms/${activeRoomCode}/stats`, {
      headers: { "Authorization": `Bearer ${adminToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();
    const select = document.getElementById("select-forensic-participant");
    if (select) {
      select.innerHTML = '<option value="">Seleccionar participante a auditar...</option>';
      (data.participants || []).forEach(p => {
        select.innerHTML += `<option value="${p.alias}">${p.alias} (Transacciones: ${p.tx_count})</option>`;
      });
    }
  } catch (e) {}
}

function startInvestigationFor(alias) {
  switchAdminTab("tab-admin-forensics");
  const select = document.getElementById("select-forensic-participant");
  if (select) {
    // Populate if empty then set
    populateForensicParticipantDropdown().then(() => {
      select.value = alias;
      runForensicInvestigation();
    });
  }
}

async function runForensicInvestigation() {
  const select = document.getElementById("select-forensic-participant");
  const alias = select ? select.value : null;
  if (!alias || !activeRoomCode) return;

  try {
    const res = await fetch(`/api/admin/rooms/${activeRoomCode}/investigate/${encodeURIComponent(alias)}`, {
      headers: { "Authorization": `Bearer ${adminToken}` }
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Error en análisis forense.");
      return;
    }

    currentInvestigationData = data;
    renderForensicDashboard(data);
  } catch (err) {
    alert("Error de red durante la investigación forense.");
  }
}

function renderForensicDashboard(data) {
  document.getElementById("forensic-results-container").style.display = "block";

  const p = data.participant;
  const fin = data.financial_summary;
  const rec = data.reconciliation;

  document.getElementById("f-target-alias").textContent = p.alias;
  document.getElementById("f-target-date").textContent = `Ingresó: ${p.created_at.substring(0, 19).replace('T', ' ')}`;
  document.getElementById("f-target-init-balance").textContent = formatCOP(fin.initial_balance_cop);
  document.getElementById("f-target-final-balance").textContent = formatCOP(fin.final_total_cop);
  document.getElementById("f-target-balances-breakdown").textContent = `Banco: ${formatCOP(fin.final_bank_cop)} | Billetera: ${formatCOP(fin.final_wallet_cop)}`;

  const recBadge = document.getElementById("f-target-reconcile-badge");
  if (rec.status === "CONCILIACIÓN_PERFECTA") {
    recBadge.innerHTML = `<span class="badge badge-success">CONCILIACIÓN CONFORME (0.00 COP)</span>`;
  } else {
    recBadge.innerHTML = `<span class="badge badge-danger">DISCREPANCIA CONTABLE</span>`;
  }

  // Render Alerts
  const alertsList = document.getElementById("f-alerts-list");
  const alertCount = document.getElementById("f-alert-count");
  const alerts = data.alerts || [];
  alertCount.textContent = `${alerts.length} Alerta(s)`;

  if (alerts.length === 0) {
    alertsList.innerHTML = `<div style="color: var(--text-dim); padding: 0.5rem;">No se detectaron patrones anómalos o alertas de riesgo para este participante.</div>`;
  } else {
    let aHtml = "";
    alerts.forEach(a => {
      const sevClass = a.severity === 'ALTO' ? 'badge-danger' : (a.severity === 'MEDIO' ? 'badge-warning' : 'badge-info');
      aHtml += `
        <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-color); border-radius: 8px; padding: 0.85rem; margin-bottom: 0.65rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
            <div style="font-weight: 700; color: #fff;">${a.title}</div>
            <span class="badge ${sevClass}">${a.severity}</span>
          </div>
          <div style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.5;">${a.description}</div>
          <div style="font-size: 0.75rem; color: var(--text-dim); margin-top: 0.3rem;">Código: <code class="mono">${a.code}</code></div>
        </div>
      `;
    });
    alertsList.innerHTML = aHtml;
  }

  // Render Graph
  renderForensicGraph(data.graph, p.alias);

  // Render Chains
  const chainsDiv = document.getElementById("f-chains-list");
  const chains = data.graph.chains || [];
  if (chains.length === 0) {
    chainsDiv.innerHTML = "No se registraron cadenas de transferencias salientes.";
  } else {
    let cHtml = "<ul style='padding-left: 1.25rem; margin-top: 0.35rem;'>";
    chains.forEach(c => {
      const pathStr = c.path.join(" → ");
      const extTag = c.reaches_external ? " <span class='badge badge-danger' style='font-size:0.65rem;'>Alcanza Destino Externo (Salida de Perímetro)</span>" : "";
      cHtml += `<li style="margin-bottom: 0.35rem;"><strong>Ruta (${c.length} saltos):</strong> <span class="mono">${pathStr}</span>${extTag}</li>`;
    });
    cHtml += "</ul>";
    chainsDiv.innerHTML = cHtml;
  }

  // Render Counterparties
  const cpTbody = document.getElementById("f-counterparties-table");
  const cpList = data.related_participants || [];
  if (cpList.length === 0) {
    cpTbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-dim); padding: 1rem;">No ha interactuado con otros participantes de la sala.</td></tr>`;
  } else {
    let cpHtml = "";
    cpList.forEach(cp => {
      cpHtml += `
        <tr>
          <td style="font-weight: 700; color: #fff;">${cp.alias}</td>
          <td class="mono">${cp.transfers_to_him}</td>
          <td class="mono">${cp.transfers_from_him}</td>
          <td class="mono" style="color: var(--accent);">${(cp.assets_involved || []).join(", ")}</td>
        </tr>
      `;
    });
    cpTbody.innerHTML = cpHtml;
  }

  // Render Findings
  const findingsDiv = document.getElementById("f-findings-list");
  let fHtml = "";
  (data.findings || []).forEach(f => {
    fHtml += `<div style="margin-bottom: 0.65rem; padding-left: 0.5rem; border-left: 2px solid var(--accent);">${f}</div>`;
  });
  findingsDiv.innerHTML = fHtml;
}

// GRAPH VISUALIZATION (Vis.js with SVG fallback)
function renderForensicGraph(graphData, targetAlias) {
  const container = document.getElementById("graph-container");
  if (!container) return;
  container.innerHTML = "";

  if (typeof vis !== "undefined" && vis.Network) {
    // Vis.js Network rendering
    const visNodes = [];
    const visEdges = [];

    (graphData.nodes || []).forEach(n => {
      let color = "#3b82f6";
      let border = "#60a5fa";
      let shape = "box";

      if (n.is_target) {
        color = "#f59e0b";
        border = "#fbbf24";
        shape = "ellipse";
      } else if (n.is_external) {
        color = "#ef4444";
        border = "#f87171";
        shape = "diamond";
      } else if (n.type === "INTERMEDIARY") {
        color = "#0d9488";
        border = "#2dd4bf";
      }

      visNodes.push({
        id: n.id,
        label: n.label,
        shape: shape,
        color: { background: color, border: border, highlight: { background: "#38bdf8", border: "#fff" } },
        font: { color: "#fff", face: "Inter", size: 14, bold: true },
        margin: 10
      });
    });

    (graphData.edges || []).forEach(e => {
      visEdges.push({
        from: e.source,
        to: e.target,
        label: e.label,
        arrows: "to",
        color: { color: e.is_external ? "#ef4444" : "#00C98D", highlight: "#fff" },
        font: { color: "#94a3b8", strokeWidth: 0, face: "JetBrains Mono", size: 11 },
        dashes: e.is_external
      });
    });

    const data = {
      nodes: new vis.DataSet(visNodes),
      edges: new vis.DataSet(visEdges)
    };

    const options = {
      layout: {
        hierarchical: {
          direction: "LR",
          sortMethod: "directed",
          levelSeparation: 160,
          nodeSpacing: 100
        }
      },
      physics: false,
      interaction: { dragNodes: true, zoomView: true, hover: true }
    };

    networkGraph = new vis.Network(container, data, options);
  } else {
    // Pure SVG Standalone Fallback
    renderSVGGraph(container, graphData);
  }
}

function renderSVGGraph(container, graphData) {
  const nodes = graphData.nodes || [];
  const edges = graphData.edges || [];

  let svg = `<svg width="100%" height="100%" viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg">`;
  svg += `<defs><marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#00C98D"/></marker></defs>`;

  // Simple layout simulation
  const nodePositions = {};
  const spacingX = 220;
  let currX = 60;

  nodes.forEach((n, idx) => {
    const x = currX;
    const y = 150 + (idx % 2 === 0 ? -40 : 40);
    nodePositions[n.id] = { x, y };
    currX += spacingX;
  });

  // Draw Edges
  edges.forEach(e => {
    const p1 = nodePositions[e.source] || { x: 100, y: 150 };
    const p2 = nodePositions[e.target] || { x: 300, y: 150 };
    svg += `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="${e.is_external ? '#ef4444' : '#00C98D'}" stroke-width="2" marker-end="url(#arrow)" stroke-dasharray="${e.is_external ? '5,5' : '0'}"/>`;
    svg += `<text x="${(p1.x + p2.x)/2}" y="${(p1.y + p2.y)/2 - 10}" fill="#94a3b8" font-size="11" font-family="JetBrains Mono" text-anchor="middle">${e.label}</text>`;
  });

  // Draw Nodes
  nodes.forEach(n => {
    const pos = nodePositions[n.id] || { x: 100, y: 150 };
    const fill = n.is_target ? '#f59e0b' : (n.is_external ? '#ef4444' : '#0d9488');
    svg += `<rect x="${pos.x - 60}" y="${pos.y - 25}" width="120" height="50" rx="8" fill="${fill}" stroke="#fff" stroke-width="1.5"/>`;
    svg += `<text x="${pos.x}" y="${pos.y + 5}" fill="#fff" font-size="13" font-weight="bold" font-family="Inter" text-anchor="middle">${n.label.substring(0, 14)}</text>`;
  });

  svg += `</svg>`;
  container.innerHTML = svg;
}

// 7-SECTION EXECUTIVE FORENSIC AUDIT REPORT GENERATION
function generateAuditReportModal() {
  if (!currentInvestigationData) {
    alert("Primero realiza la investigación de un participante.");
    return;
  }

  const d = currentInvestigationData;
  const p = d.participant;
  const r = d.room;
  const f = d.financial_summary;
  const rec = d.reconciliation;
  const meta = d.audit_meta;
  const alerts = d.alerts || [];
  const findings = d.findings || [];
  const chains = d.graph?.chains || [];
  const counterparties = d.related_participants || [];
  const chronology = d.chronology || [];
  const execSummary = d.executive_summary || {};

  // Period analyzed
  const firstTxDate = chronology.length > 0 ? chronology[0].created_at.substring(0, 19).replace('T', ' ') : p.created_at.substring(0, 19).replace('T', ' ');
  const lastTxDate = chronology.length > 0 ? chronology[chronology.length - 1].created_at.substring(0, 19).replace('T', ' ') : meta.generated_at.substring(0, 19).replace('T', ' ');
  const periodStr = `${firstTxDate} a ${lastTxDate} (COT)`;

  // Total volume moved in COP
  let totalVolumeMovedCOP = (f.total_purchases_cop || 0) + (f.total_sales_cop || 0);
  chronology.forEach(tx => {
    if (tx.asset === 'COP' && (tx.tx_type === 'TRANSFER_INTERNAL' || tx.tx_type === 'TRANSFER_EXTERNAL')) {
      totalVolumeMovedCOP += Number(tx.amount || 0);
    }
  });

  // Unique assets involved
  const assetsSet = new Set(chronology.map(tx => tx.asset));
  if (assetsSet.size === 0) assetsSet.add("COP");
  const assetsInvolved = Array.from(assetsSet).join(", ");

  // Risk Level
  const riskLevel = execSummary.risk_level || (alerts.some(a => a.severity === 'ALTO') ? 'ALTO' : (alerts.some(a => a.severity === 'MEDIO') ? 'MEDIO' : 'BAJO'));
  const riskBadgeClass = riskLevel === 'ALTO' ? 'badge-danger' : (riskLevel === 'MEDIO' ? 'badge-warning' : 'badge-success');

  // Executive HTML building
  let html = `
    <div class="exec-report">
      
      <!-- 5.1 ENCABEZADO PROFESIONAL -->
      <div class="exec-header">
        <div>
          <div class="exec-header-subtitle">CRYPTO LAB &bull; MÓDULO FORENSE DE TRANSACCIONES</div>
          <h1 class="exec-header-title">Informe de Auditoría de Transacciones</h1>
        </div>
        <div style="text-align: right; font-size: 0.78rem;">
          <div style="color: var(--text-dim); text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em;">Referencia de Auditoría</div>
          <div class="mono" style="color: var(--accent); font-weight: 700;">AUD-${p.alias}-${meta.generated_at.substring(0, 10).replace(/-/g, '')}</div>
        </div>
      </div>

      <div class="exec-meta-grid">
        <div class="exec-meta-item">
          <strong>Sala</strong>
          <span>${r.code} &bull; ${r.name}</span>
        </div>
        <div class="exec-meta-item">
          <strong>Usuario Analizado</strong>
          <span style="font-weight: 700; color: #fff;">${p.alias}</span> <span class="mono" style="color: var(--text-dim); font-size: 0.72rem;">(${p.id})</span>
        </div>
        <div class="exec-meta-item">
          <strong>Fecha y Hora de Emisión</strong>
          <span class="mono">${meta.generated_at.substring(0, 19).replace('T', ' ')} COT</span>
        </div>
        <div class="exec-meta-item">
          <strong>Periodo Analizado</strong>
          <span class="mono">${periodStr}</span>
        </div>
      </div>

      <!-- 5.2 RESUMEN EJECUTIVO -->
      <div class="exec-section">
        <div class="exec-section-title">
          <span>1. Resumen Ejecutivo</span>
          <span class="badge ${riskBadgeClass}">Riesgo General: ${riskLevel}</span>
        </div>
        <div class="exec-kpi-grid">
          <div class="exec-kpi-card">
            <div class="exec-kpi-label">Operaciones Analizadas</div>
            <div class="exec-kpi-val mono">${chronology.length}</div>
          </div>
          <div class="exec-kpi-card">
            <div class="exec-kpi-label">Activos Involucrados</div>
            <div class="exec-kpi-val mono" style="font-size: 0.95rem; color: var(--accent);">${assetsInvolved}</div>
          </div>
          <div class="exec-kpi-card">
            <div class="exec-kpi-label">Volumen Total Movilizado</div>
            <div class="exec-kpi-val mono" style="font-size: 1rem;">${formatCOP(totalVolumeMovedCOP)}</div>
          </div>
          <div class="exec-kpi-card">
            <div class="exec-kpi-label">Contrapartes Directas</div>
            <div class="exec-kpi-val mono">${counterparties.length}</div>
          </div>
          <div class="exec-kpi-card">
            <div class="exec-kpi-label">Alertas Técnicas</div>
            <div class="exec-kpi-val mono" style="color: ${alerts.length > 0 ? 'var(--warning)' : 'var(--primary)'};">${alerts.length}</div>
          </div>
          <div class="exec-kpi-card">
            <div class="exec-kpi-label">Nivel de Riesgo</div>
            <div class="exec-kpi-val" style="font-size: 0.95rem;">
              <span class="badge ${riskBadgeClass}">${riskLevel}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 5.3 RESUMEN FINANCIERO -->
      <div class="exec-section">
        <div class="exec-section-title">
          <span>2. Resumen Financiero y Conciliación</span>
          <span class="badge ${rec.status === 'CONCILIACIÓN_PERFECTA' ? 'badge-success' : 'badge-danger'}">
            ${rec.status === 'CONCILIACIÓN_PERFECTA' ? 'Conciliación Conforme (0.00 COP)' : 'Inconsistencia Contable'}
          </span>
        </div>
        <div class="table-wrapper" style="margin-bottom: 0.75rem;">
          <table class="table" style="font-size: 0.82rem;">
            <thead>
              <tr>
                <th>Concepto</th>
                <th class="text-right">Monto Registrado</th>
                <th>Detalle Operativo</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Saldo Inicial Asignado</strong></td>
                <td class="mono text-right" style="font-weight: 700;">${formatCOP(f.initial_balance_cop)}</td>
                <td style="color: var(--text-muted);">Asignación central inicial en cuenta de custodia</td>
              </tr>
              <tr>
                <td><strong>Saldo Final Consolidado</strong></td>
                <td class="mono text-right" style="font-weight: 700; color: #fff;">${formatCOP(f.final_total_cop)}</td>
                <td style="color: var(--text-muted);">Custodia Bancaria: ${formatCOP(f.final_bank_cop)} &bull; Billetera COP: ${formatCOP(f.final_wallet_cop)}</td>
              </tr>
              <tr>
                <td><strong>Total Compras Cripto</strong></td>
                <td class="mono text-right">${formatCOP(f.total_purchases_cop)}</td>
                <td style="color: var(--text-muted);">${Object.entries(f.crypto_bought || {}).map(([k,v]) => `${v} ${k}`).join(', ') || 'Sin compras'}</td>
              </tr>
              <tr>
                <td><strong>Total Ventas Cripto</strong></td>
                <td class="mono text-right">${formatCOP(f.total_sales_cop)}</td>
                <td style="color: var(--text-muted);">${Object.entries(f.crypto_sold || {}).map(([k,v]) => `${v} ${k}`).join(', ') || 'Sin ventas'}</td>
              </tr>
              <tr>
                <td><strong>Transferencias Salientes</strong></td>
                <td class="mono text-right">${f.total_internal_transfers_sent} Internas / ${f.total_external_transfers} Externas</td>
                <td style="color: var(--text-muted);">${Object.entries(f.crypto_sent || {}).map(([k,v]) => `${v} ${k}`).join(', ') || 'Sin transferencias salientes'}</td>
              </tr>
              <tr>
                <td><strong>Comisiones Pagadas (0.2%)</strong></td>
                <td class="mono text-right" style="color: var(--warning);">${formatCOP(f.total_fees_paid_cop)}</td>
                <td style="color: var(--text-muted);">Deducidas automáticamente en órdenes de mercado</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 5.4 ANÁLISIS DE RIESGOS Y ALERTAS -->
      <div class="exec-section">
        <div class="exec-section-title">
          <span>3. Análisis de Riesgos y Alertas Técnicas</span>
          <span style="font-size: 0.78rem; color: var(--text-muted); text-transform: none; font-weight: 400;">Evaluación objetiva de patrones financieros</span>
        </div>
        ${alerts.length === 0 ? '<div class="exec-conclusion-box" style="background:rgba(16, 185, 129, 0.05); border-color:rgba(16, 185, 129, 0.25);">No se detectaron alertas técnicas ni desviaciones de comportamiento para el participante analizado.</div>' : alerts.map(a => {
          const sevClass = a.severity === 'ALTO' ? 'alert-high' : (a.severity === 'MEDIO' ? 'alert-medium' : 'alert-low');
          const badgeClass = a.severity === 'ALTO' ? 'badge-danger' : (a.severity === 'MEDIO' ? 'badge-warning' : 'badge-success');
          const impactText = a.impact || 'Este patrón amerita revisión de trazabilidad y propósito económico en el contexto de la operación.';
          return `
            <div class="exec-alert-card ${sevClass}">
              <div class="exec-alert-title-row">
                <div class="exec-alert-title">Alerta: ${a.title}</div>
                <span class="badge ${badgeClass}">Nivel: ${a.severity}</span>
              </div>
              <div class="exec-alert-desc"><strong>Descripción:</strong> ${a.description}</div>
              <div class="exec-alert-impact"><strong>Impacto / Lectura Técnica:</strong> ${impactText}</div>
            </div>
          `;
        }).join('')}
      </div>

      <!-- 5.5 TRAZABILIDAD -->
      <div class="exec-section">
        <div class="exec-section-title">
          <span>4. Trazabilidad de Fondos</span>
          <span style="font-size: 0.78rem; color: var(--text-muted); text-transform: none; font-weight: 400;">Ruta esquemática de movilización de activos</span>
        </div>
        ${chains.length === 0 ? '<div style="font-size:0.85rem; color:var(--text-muted);">No se evidenciaron rutas de dispersión o saltos salientes a terceros.</div>' : `
          <div style="display: flex; flex-direction: column; gap: 0.6rem;">
            ${chains.map((c, idx) => `
              <div class="exec-trace-box">
                <span style="font-size: 0.74rem; color: var(--text-dim); margin-right: 0.3rem;">Ruta ${idx + 1}:</span>
                ${c.path.map((node, i) => {
                  const isFirst = (i === 0);
                  const isLast = (i === c.path.length - 1);
                  const isExt = c.reaches_external && isLast;
                  const stepClass = isFirst ? 'step-origin' : (isExt ? 'step-target' : '');
                  const label = isExt ? `Destino Externo (${node.substring(0, 8)}...)` : node;
                  return `
                    <span class="exec-trace-step ${stepClass}">${label}</span>
                    ${!isLast ? '<span class="exec-trace-arrow">→</span>' : ''}
                  `;
                }).join('')}
                ${c.reaches_external ? '<span class="badge badge-danger" style="font-size: 0.68rem; margin-left: auto;">Fin de Visibilidad Interna</span>' : ''}
              </div>
            `).join('')}
          </div>
        `}
      </div>

      <!-- 5.6 HALLAZGOS PRINCIPALES -->
      <div class="exec-section">
        <div class="exec-section-title">
          <span>5. Hallazgos Principales</span>
          <span style="font-size: 0.78rem; color: var(--text-muted); text-transform: none; font-weight: 400;">Observaciones fácticas clave</span>
        </div>
        <ul class="exec-findings-list">
          ${findings.slice(0, 6).map(f => {
            const cleanText = f.replace(/^[0-9]+\.\s*/, '');
            return `<li class="exec-findings-item">${cleanText}</li>`;
          }).join('')}
        </ul>
      </div>

      <!-- 5.7 CONCLUSIÓN BREVE -->
      <div class="exec-section" style="margin-bottom: 0;">
        <div class="exec-section-title">
          <span>6. Conclusión de Auditoría</span>
        </div>
        <div class="exec-conclusion-box">
          ${d.executive_conclusion || 'Con base en los movimientos analizados, se identificaron patrones de transferencia que justifican revisión adicional desde la perspectiva de trazabilidad financiera. No se evidenciaron inconsistencias contables en la conciliación del usuario analizado.'}
        </div>
      </div>

      <!-- SIGNATURE SECTION -->
      <div style="margin-top: 2rem; padding-top: 1.25rem; border-top: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: flex-end; font-size: 0.78rem; color: var(--text-dim);">
        <div>
          <div style="color: var(--text-muted); font-weight: 600; margin-bottom: 0.2rem;">RESPONSABLE DEL ANÁLISIS</div>
          <div>Auditoría Forense &bull; Crypto Lab Surveillance</div>
        </div>
        <div style="text-align: right;">
          <div>Identificador Criptográfico: <span class="mono" style="color: var(--accent);">${meta.generated_at.replace(/[-:T]/g, '').substring(0, 14)}-${p.alias.substring(0, 6)}</span></div>
          <div>Registro Contable Conforme &bull; Base de Datos Inmutable</div>
        </div>
      </div>

    </div>
  `;

  document.getElementById("report-printable-area").innerHTML = html;
  document.getElementById("modal-audit-report").classList.add("open");
}

function closeModal(id) {
  document.getElementById(id).classList.remove("open");
}

// MARKET REPLAY CONTROLLER (D-015)
let adminReplayInterval = null;

async function adminReplayAction(action) {
  if (!adminToken) return;
  try {
    const res = await fetch(`/api/admin/replay/${action}`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${adminToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      updateAdminReplayUI(data.state);
    }
  } catch (e) {
    console.error("Error executing replay action:", e);
  }
}

async function adminReplaySetSpeed(speed) {
  if (!adminToken) return;
  try {
    const res = await fetch(`/api/admin/replay/speed?speed=${speed}`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${adminToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      updateAdminReplayUI(data.state);
    }
  } catch (e) {}
}

async function pollAdminReplayStatus() {
  try {
    const res = await fetch("/api/market/replay-status");
    if (res.ok) {
      const state = await res.json();
      updateAdminReplayUI(state);
    }
  } catch (e) {}
}

function updateAdminReplayUI(state) {
  if (!state) return;

  const badge = document.getElementById("admin-replay-badge");
  const btnReset = document.getElementById("btn-admin-replay-reset");

  if (badge) {
    if (state.is_completed) {
      badge.className = "badge badge-danger";
      badge.textContent = "MERCADO FINALIZADO";
      if (btnReset) {
        btnReset.className = "btn btn-primary btn-sm";
        btnReset.textContent = "Reiniciar Reproducción";
        btnReset.title = "Reinicia la serie temporal desde 00:00:00 COT conservando todas las transacciones";
      }
    } else if (state.status === "RUNNING") {
      badge.className = "badge badge-success";
      badge.textContent = `EN EJECUCIÓN ${state.speed}X`;
      if (btnReset) {
        btnReset.className = "btn btn-secondary btn-sm";
        btnReset.textContent = "Reiniciar";
      }
    } else if (state.status === "PAUSED") {
      badge.className = "badge badge-warning";
      badge.textContent = `PAUSADO (${state.speed}X)`;
      if (btnReset) {
        btnReset.className = "btn btn-secondary btn-sm";
        btnReset.textContent = "Reiniciar";
      }
    } else {
      badge.className = "badge badge-info";
      badge.textContent = `DETENIDO`;
    }
  }

  const simTime = document.getElementById("admin-replay-sim-time");
  if (simTime) {
    simTime.textContent = state.simulated_datetime_formatted || state.simulated_datetime_iso;
  }

  const bar = document.getElementById("admin-replay-prog-bar");
  if (bar) {
    bar.style.width = `${state.progress_percent}%`;
  }

  const elapsedText = document.getElementById("admin-replay-elapsed-text");
  if (elapsedText) {
    elapsedText.textContent = `${state.elapsed_formatted} (${state.progress_percent}%)`;
  }
}

// Start admin replay polling
setInterval(pollAdminReplayStatus, 2500);
