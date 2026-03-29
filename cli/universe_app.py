"""Flask web application for TASE company universe browsing and priority list management."""

from __future__ import annotations

import logging
from flask import Flask, jsonify, request, Response

from src.universe.universe import (
    load_universe,
    search_companies,
    get_sectors,
    PriorityList,
    TASECompany,
)

log = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# State (loaded once on startup)
# ---------------------------------------------------------------------------
_universe: list[TASECompany] = []
_priority: PriorityList | None = None


def _ensure_loaded():
    global _universe, _priority
    if not _universe:
        _universe = load_universe()
        _priority = PriorityList()


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    _ensure_loaded()
    return Response(_HTML, content_type="text/html; charset=utf-8")


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.route("/api/companies")
def api_companies():
    _ensure_loaded()
    q = request.args.get("q", "").strip()
    sector = request.args.get("sector", "").strip()
    results = search_companies(_universe, query=q, sector=sector)
    # Return priority status for each company
    data = []
    for c in results:
        d = c.model_dump()
        d["is_priority"] = _priority.has_company(c.name)
        data.append(d)
    return jsonify(data)


@app.route("/api/sectors")
def api_sectors():
    _ensure_loaded()
    sectors = get_sectors(_universe)
    sector_data = []
    for s in sectors:
        count = len([c for c in _universe if c.sector == s])
        sector_data.append({
            "name": s,
            "count": count,
            "is_priority": _priority.has_sector(s),
        })
    return jsonify(sector_data)


@app.route("/api/priority")
def api_priority():
    _ensure_loaded()
    priority_companies = _priority.get_priority_companies(_universe)
    data = []
    for c in priority_companies:
        d = c.model_dump()
        d["is_priority"] = True
        data.append(d)
    return jsonify({
        "companies": data,
        "sectors": _priority.sectors,
        "count": _priority.count(),
    })


@app.route("/api/priority/company", methods=["POST"])
def api_add_company():
    _ensure_loaded()
    body = request.get_json(force=True)
    name = body.get("name", "")
    added = _priority.add_company(name)
    return jsonify({"added": added, "count": _priority.count()})


@app.route("/api/priority/company", methods=["DELETE"])
def api_remove_company():
    _ensure_loaded()
    body = request.get_json(force=True)
    name = body.get("name", "")
    removed = _priority.remove_company(name)
    return jsonify({"removed": removed, "count": _priority.count()})


@app.route("/api/priority/sector", methods=["POST"])
def api_add_sector():
    _ensure_loaded()
    body = request.get_json(force=True)
    sector = body.get("sector", "")
    count = _priority.add_sector(sector, _universe)
    return jsonify({"added_count": count, "total": _priority.count()})


@app.route("/api/priority/sector", methods=["DELETE"])
def api_remove_sector():
    _ensure_loaded()
    body = request.get_json(force=True)
    sector = body.get("sector", "")
    count = _priority.remove_sector(sector, _universe)
    return jsonify({"removed_count": count, "total": _priority.count()})


@app.route("/api/stats")
def api_stats():
    _ensure_loaded()
    sectors = get_sectors(_universe)
    return jsonify({
        "total_companies": len(_universe),
        "total_sectors": len(sectors),
        "priority_count": _priority.count(),
        "priority_sectors": len(_priority.sectors),
    })


# ---------------------------------------------------------------------------
# Launcher
# ---------------------------------------------------------------------------

def run_server(host: str = "127.0.0.1", port: int = 5050, debug: bool = True):
    """Launch the universe browser."""
    global _universe, _priority
    _universe = load_universe()
    _priority = PriorityList()
    log.info(f"Universe loaded: {len(_universe)} companies, {len(get_sectors(_universe))} sectors")
    log.info(f"Priority list: {_priority.count()} companies")
    print(f"\n  🌐  Universe Browser: http://{host}:{port}\n")
    app.run(host=host, port=port, debug=debug)


# ---------------------------------------------------------------------------
# Inline HTML (single-page app)
# ---------------------------------------------------------------------------

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TASE Universe · Priority Manager</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0e1a;
    --bg-card: rgba(20, 27, 45, 0.7);
    --bg-card-hover: rgba(30, 40, 65, 0.85);
    --bg-glass: rgba(255,255,255,0.04);
    --border: rgba(255,255,255,0.07);
    --border-hover: rgba(255,255,255,0.15);
    --text: #e4e8f1;
    --text-dim: #8892a8;
    --text-bright: #ffffff;
    --accent: #6366f1;
    --accent-glow: rgba(99,102,241,0.25);
    --green: #22c55e;
    --green-dim: rgba(34,197,94,0.15);
    --red: #ef4444;
    --red-dim: rgba(239,68,68,0.15);
    --gold: #f59e0b;
    --gold-dim: rgba(245,158,11,0.12);
    --radius: 14px;
    --radius-sm: 8px;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    overflow-x: hidden;
  }
  /* Animated gradient background */
  body::before {
    content: '';
    position: fixed; top:-50%; left:-50%; width:200%; height:200%;
    background: radial-gradient(circle at 30% 40%, rgba(99,102,241,0.08), transparent 50%),
                radial-gradient(circle at 70% 60%, rgba(34,197,94,0.06), transparent 50%),
                radial-gradient(circle at 50% 80%, rgba(245,158,11,0.04), transparent 50%);
    animation: drift 30s ease-in-out infinite;
    z-index: 0;
  }
  @keyframes drift {
    0%,100% { transform: translate(0,0) rotate(0deg); }
    33% { transform: translate(2%,-1%) rotate(1deg); }
    66% { transform: translate(-1%,2%) rotate(-1deg); }
  }
  /* Header */
  .header {
    position: relative; z-index:10;
    display: flex; align-items: center; justify-content: space-between;
    padding: 20px 32px;
    border-bottom: 1px solid var(--border);
    backdrop-filter: blur(20px);
    background: rgba(10,14,26,0.6);
  }
  .header h1 {
    font-size: 22px; font-weight: 700; letter-spacing: -0.5px;
    background: linear-gradient(135deg, #e4e8f1, #6366f1);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }
  .header-stats {
    display: flex; gap: 20px; align-items: center;
  }
  .stat-pill {
    display: flex; align-items: center; gap: 6px;
    padding: 6px 14px; border-radius: 100px;
    background: var(--bg-glass); border: 1px solid var(--border);
    font-size: 13px; color: var(--text-dim); font-weight: 500;
  }
  .stat-pill .num {
    font-weight: 700; color: var(--text-bright); font-size: 14px;
  }
  .stat-pill.priority .num { color: var(--gold); }
  /* Layout */
  .container {
    position: relative; z-index:10;
    display: grid;
    grid-template-columns: 1fr 380px;
    gap: 0;
    height: calc(100vh - 73px);
  }
  /* Left panel — Universe */
  .panel {
    display: flex; flex-direction: column;
    border-right: 1px solid var(--border);
    overflow: hidden;
  }
  .panel-header {
    padding: 18px 24px 14px;
    border-bottom: 1px solid var(--border);
    background: rgba(10,14,26,0.4);
    backdrop-filter: blur(10px);
  }
  .panel-title {
    font-size: 15px; font-weight: 600; color: var(--text-dim);
    text-transform: uppercase; letter-spacing: 1px;
    margin-bottom: 12px;
  }
  .search-row {
    display: flex; gap: 10px; align-items: center;
  }
  .search-input {
    flex: 1;
    padding: 10px 14px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border);
    background: var(--bg-glass);
    color: var(--text-bright);
    font-size: 14px; font-family: inherit;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .search-input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-glow);
  }
  .search-input::placeholder { color: var(--text-dim); }
  .sector-select {
    width: 200px;
    padding: 10px 12px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border);
    background: var(--bg-card);
    color: var(--text);
    font-size: 13px; font-family: inherit;
    outline: none; cursor: pointer;
    transition: border-color 0.2s;
  }
  .sector-select:focus { border-color: var(--accent); }
  .btn-add-sector {
    padding: 10px 16px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--green);
    background: var(--green-dim);
    color: var(--green);
    font-size: 13px; font-weight: 600; font-family: inherit;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s;
  }
  .btn-add-sector:hover { background: rgba(34,197,94,0.25); transform: translateY(-1px); }
  .btn-add-sector:disabled { opacity: 0.4; cursor: default; transform: none; }
  /* Company list */
  .company-list {
    flex: 1; overflow-y: auto; padding: 12px;
  }
  .company-list::-webkit-scrollbar { width: 6px; }
  .company-list::-webkit-scrollbar-track { background: transparent; }
  .company-list::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
  .company-card {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 16px;
    margin-bottom: 6px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border);
    background: var(--bg-card);
    transition: all 0.2s;
    cursor: default;
  }
  .company-card:hover {
    background: var(--bg-card-hover);
    border-color: var(--border-hover);
    transform: translateX(2px);
  }
  .company-card.is-priority {
    border-color: rgba(245,158,11,0.25);
    background: rgba(245,158,11,0.04);
  }
  .card-info { flex: 1; min-width: 0; }
  .card-name {
    font-size: 14px; font-weight: 600; color: var(--text-bright);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .card-meta {
    display: flex; align-items: center; gap: 8px; margin-top: 4px;
    font-size: 12px; color: var(--text-dim);
  }
  .sector-badge {
    padding: 2px 8px;
    border-radius: 100px;
    background: var(--bg-glass);
    border: 1px solid var(--border);
    font-size: 11px; font-weight: 500;
    color: var(--accent);
    white-space: nowrap;
  }
  .mcap {
    font-variant-numeric: tabular-nums;
    color: var(--text-dim);
  }
  .card-website a {
    color: var(--text-dim); text-decoration: none; font-size: 12px;
    transition: color 0.2s;
  }
  .card-website a:hover { color: var(--accent); }
  .card-actions { visibility: hidden; width: 0; }
  /* Results summary */
    padding: 6px 14px;
    border-radius: 6px;
    border: 1px solid transparent;
    font-size: 12px; font-weight: 600; font-family: inherit;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-prio.add {
    background: var(--accent-glow);
    border-color: var(--accent);
    color: var(--accent);
  }
  .btn-prio.add:hover { background: rgba(99,102,241,0.35); transform: scale(1.05); }
  .btn-prio.remove {
    background: var(--red-dim);
    border-color: var(--red);
    color: var(--red);
  }
  .btn-prio.remove:hover { background: rgba(239,68,68,0.25); transform: scale(1.05); }
  .results-bar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 8px 16px;
    font-size: 12px; color: var(--text-dim);
    border-bottom: 1px solid var(--border);
    background: rgba(10,14,26,0.3);
  }
  
  /* Priority button next to search */
  .btn-prio-search {
    padding: 8px 14px;
    border-radius: var(--radius-sm);
    border: 1px solid transparent;
    font-size: 13px; font-weight: 600; font-family: inherit;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
  }
  .btn-prio-search.add {
    background: var(--accent-glow);
    border-color: var(--accent);
    color: var(--accent);
  }
  .btn-prio-search.add:hover { background: rgba(99,102,241,0.35); transform: translateY(-1px); }
  .btn-prio-search.remove {
    background: var(--red-dim);
    border-color: var(--red);
    color: var(--red);
  }
  .btn-prio-search.remove:hover { background: rgba(239,68,68,0.25); transform: translateY(-1px); }
  .btn-prio-search:disabled { opacity: 0.4; cursor: default; transform: none; }
  
  /* Right panel — Priority List */
  .priority-panel {
    display: flex; flex-direction: column;
    background: rgba(10,14,26,0.3);
    overflow: hidden;
  }
  .priority-header {
    padding: 18px 20px 14px;
    border-bottom: 1px solid var(--border);
    background: rgba(245,158,11,0.03);
  }
  .priority-title {
    display: flex; align-items: center; gap: 10px;
    font-size: 15px; font-weight: 600; color: var(--gold);
    text-transform: uppercase; letter-spacing: 1px;
  }
  .priority-count-badge {
    padding: 2px 10px;
    border-radius: 100px;
    background: var(--gold-dim);
    font-size: 13px; font-weight: 700;
    color: var(--gold);
  }
  .priority-sectors {
    display: flex; flex-wrap: wrap; gap: 6px;
    padding: 10px 20px;
    border-bottom: 1px solid var(--border);
    min-height: 20px;
  }
  .priority-sector-tag {
    display: flex; align-items: center; gap: 4px;
    padding: 4px 10px;
    border-radius: 100px;
    background: var(--gold-dim);
    border: 1px solid rgba(245,158,11,0.2);
    font-size: 11px; font-weight: 500; color: var(--gold);
    cursor: default;
  }
  .priority-sector-tag .remove-sector {
    cursor: pointer; margin-left: 2px; opacity: 0.6;
    transition: opacity 0.2s;
  }
  .priority-sector-tag .remove-sector:hover { opacity: 1; }
  .priority-list {
    flex: 1; overflow-y: auto; padding: 10px;
  }
  .priority-list::-webkit-scrollbar { width: 6px; }
  .priority-list::-webkit-scrollbar-track { background: transparent; }
  .priority-list::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
  .priority-card {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 14px;
    margin-bottom: 4px;
    border-radius: var(--radius-sm);
    border: 1px solid rgba(245,158,11,0.12);
    background: rgba(245,158,11,0.03);
    transition: all 0.2s;
  }
  .priority-card:hover {
    background: rgba(245,158,11,0.07);
    border-color: rgba(245,158,11,0.25);
  }
  .prio-name {
    font-size: 13px; font-weight: 500; color: var(--text-bright);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    flex: 1;
  }
  .prio-sector {
    font-size: 11px; color: var(--text-dim);
    white-space: nowrap; margin: 0 8px;
  }
  .btn-remove-sm {
    padding: 4px 10px;
    border-radius: 4px;
    border: 1px solid rgba(239,68,68,0.3);
    background: transparent;
    color: var(--red);
    font-size: 11px; font-weight: 600; font-family: inherit;
    cursor: pointer;
    transition: all 0.2s;
    flex-shrink: 0;
  }
  .btn-remove-sm:hover { background: var(--red-dim); }
  /* Loading & empty states */
  .empty-state {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    padding: 40px; text-align: center; color: var(--text-dim);
  }
  .empty-state .icon { font-size: 40px; margin-bottom: 12px; opacity: 0.4; }
  .empty-state p { font-size: 13px; line-height: 1.5; }
  /* Animation */
  @keyframes fadeIn { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
  .company-card, .priority-card { animation: fadeIn 0.25s ease-out; }
  /* Toast */
  .toast-container {
    position: fixed; bottom: 24px; right: 24px; z-index: 1000;
    display: flex; flex-direction: column; gap: 8px;
  }
  .toast {
    padding: 12px 20px;
    border-radius: var(--radius-sm);
    background: var(--bg-card);
    border: 1px solid var(--border);
    backdrop-filter: blur(20px);
    font-size: 13px; color: var(--text);
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    animation: slideIn 0.3s ease-out;
  }
  .toast.success { border-color: var(--green); color: var(--green); }
  .toast.info { border-color: var(--accent); color: var(--accent); }
  @keyframes slideIn { from { opacity:0; transform:translateX(20px); } to { opacity:1; transform:translateX(0); } }
</style>
</head>
<body>
  <header class="header">
    <h1>⚡ TASE Universe</h1>
    <div class="header-stats">
      <div class="stat-pill"><span>Companies</span><span class="num" id="stat-total">—</span></div>
      <div class="stat-pill"><span>Sectors</span><span class="num" id="stat-sectors">—</span></div>
      <div class="stat-pill priority"><span>Priority</span><span class="num" id="stat-priority">—</span></div>
    </div>
  </header>

  <div class="container">
    <!-- LEFT: Universe Browser -->
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">Company Universe</div>
        <div class="search-row">
          <input type="text" class="search-input" id="search" placeholder="Search company name..." autocomplete="off">
          <button class="btn-prio-search add" id="btn-toggle-prio" disabled>+ Priority</button>
          <select class="sector-select" id="sector-filter">
            <option value="">All Sectors</option>
          </select>
          <button class="btn-add-sector" id="btn-add-sector" disabled>+ Add Sector</button>
        </div>
      </div>
      <div class="results-bar">
        <span id="results-count">Loading...</span>
        <span id="results-hint"></span>
      </div>
      <div class="company-list" id="company-list"></div>
    </div>

    <!-- RIGHT: Priority List -->
    <div class="priority-panel">
      <div class="priority-header">
        <div class="priority-title">
          ⭐ Priority List
          <span class="priority-count-badge" id="priority-badge">0</span>
        </div>
      </div>
      <div class="priority-sectors" id="priority-sectors"></div>
      <div class="priority-list" id="priority-list"></div>
    </div>
  </div>

  <div class="toast-container" id="toasts"></div>

<script>
// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let allSectors = [];
let currentResults = [];
let debounceTimer = null;

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
async function api(url, opts = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  return res.json();
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------
function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.getElementById('toasts').appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 2500);
}

// ---------------------------------------------------------------------------
// Format market cap
// ---------------------------------------------------------------------------
function formatMcap(kILS) {
  if (!kILS || kILS === 0) return '';
  const m = kILS / 1000;
  if (m >= 1000) return `₪${(m/1000).toFixed(1)}B`;
  if (m >= 1) return `₪${m.toFixed(0)}M`;
  return `₪${kILS}K`;
}

// ---------------------------------------------------------------------------
// Render company card
// ---------------------------------------------------------------------------
function renderCompanyCard(c) {
  const mcap = formatMcap(c.market_cap_k_ils);
  const webLink = c.website ? `<span class="card-website"><a href="${c.website.startsWith('http') ? c.website : 'https://'+c.website}" target="_blank">↗ ${c.website.replace(/https?:\/\//, '').replace(/\/$/, '').substring(0,30)}</a></span>` : '';
  
  return `
    <div class="company-card ${c.is_priority ? 'is-priority' : ''}" data-name="${esc(c.name)}">
      <div class="card-info">
        <div class="card-name">${esc(c.name)}</div>
        <div class="card-meta">
          <span class="sector-badge">${esc(c.sector)}</span>
          ${mcap ? `<span class="mcap">${mcap}</span>` : ''}
          ${webLink}
        </div>
      </div>
    </div>`;
}

function updateSearchPrioButton() {
  const q = document.getElementById('search').value.trim().toLowerCase();
  const btn = document.getElementById('btn-toggle-prio');
  
  // Find exact match in current results
  const exactMatch = currentResults.find(c => c.name.toLowerCase() === q || c.full_name.toLowerCase() === q);
  
  if (exactMatch) {
    btn.disabled = false;
    if (exactMatch.is_priority) {
      btn.textContent = "✕ Remove";
      btn.className = "btn-prio-search remove";
      btn.onclick = () => removePriority(exactMatch.name);
    } else {
      btn.textContent = "+ Priority";
      btn.className = "btn-prio-search add";
      btn.onclick = () => addPriority(exactMatch.name);
    }
  } else {
    btn.disabled = true;
    btn.textContent = "+ Priority";
    btn.className = "btn-prio-search add";
    btn.onclick = null;
  }
}

function esc(s) { return s.replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/</g, '&lt;'); }

// ---------------------------------------------------------------------------
// Load companies
// ---------------------------------------------------------------------------
async function loadCompanies() {
  const q = document.getElementById('search').value;
  const sector = document.getElementById('sector-filter').value;
  currentResults = await api(`/api/companies?q=${encodeURIComponent(q)}&sector=${encodeURIComponent(sector)}`);
  document.getElementById('results-count').textContent = `${currentResults.length} companies`;
  const listEl = document.getElementById('company-list');
  if (currentResults.length === 0) {
    listEl.innerHTML = `<div class="empty-state"><div class="icon">🔍</div><p>No companies found<br>Try a different search</p></div>`;
  } else {
    listEl.innerHTML = currentResults.map(renderCompanyCard).join('');
  }
  updateSearchPrioButton();
}

// ---------------------------------------------------------------------------
// Load sectors
// ---------------------------------------------------------------------------
async function loadSectors() {
  allSectors = await api('/api/sectors');
  const sel = document.getElementById('sector-filter');
  sel.innerHTML = '<option value="">All Sectors</option>' +
    allSectors.map(s => `<option value="${s.name}">${s.name} (${s.count})</option>`).join('');
}

// ---------------------------------------------------------------------------
// Load priority list
// ---------------------------------------------------------------------------
async function loadPriority() {
  const data = await api('/api/priority');
  document.getElementById('priority-badge').textContent = data.count;
  document.getElementById('stat-priority').textContent = data.count;

  // Sector tags
  const sectorsEl = document.getElementById('priority-sectors');
  if (data.sectors.length === 0) {
    sectorsEl.innerHTML = '<span style="font-size:11px;color:var(--text-dim);padding:4px;">No sector filters</span>';
  } else {
    sectorsEl.innerHTML = data.sectors.map(s =>
      `<span class="priority-sector-tag">${s}<span class="remove-sector" onclick="removeSector('${esc(s)}')">✕</span></span>`
    ).join('');
  }

  // Company list
  const listEl = document.getElementById('priority-list');
  if (data.companies.length === 0) {
    listEl.innerHTML = `<div class="empty-state"><div class="icon">⭐</div><p>No priority companies yet<br>Search and add companies from the left panel</p></div>`;
  } else {
    listEl.innerHTML = data.companies.map(c => `
      <div class="priority-card">
        <span class="prio-name">${esc(c.name)}</span>
        <span class="prio-sector">${esc(c.sector)}</span>
        <button class="btn-remove-sm" onclick="removePriority('${esc(c.name)}')">Remove</button>
      </div>`).join('');
  }
}

// ---------------------------------------------------------------------------
// Load stats
// ---------------------------------------------------------------------------
async function loadStats() {
  const s = await api('/api/stats');
  document.getElementById('stat-total').textContent = s.total_companies;
  document.getElementById('stat-sectors').textContent = s.total_sectors;
  document.getElementById('stat-priority').textContent = s.priority_count;
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------
async function addPriority(name) {
  await api('/api/priority/company', { method: 'POST', body: JSON.stringify({ name }) });
  toast(`Added ${name}`, 'success');
  await Promise.all([loadCompanies(), loadPriority(), loadStats()]);
}

async function removePriority(name) {
  await api('/api/priority/company', { method: 'DELETE', body: JSON.stringify({ name }) });
  toast(`Removed ${name}`, 'info');
  await Promise.all([loadCompanies(), loadPriority(), loadStats()]);
}

async function addSector() {
  const sector = document.getElementById('sector-filter').value;
  if (!sector) return;
  const res = await api('/api/priority/sector', { method: 'POST', body: JSON.stringify({ sector }) });
  toast(`Added ${res.added_count} companies from "${sector}"`, 'success');
  await Promise.all([loadCompanies(), loadPriority(), loadStats(), loadSectors()]);
}

async function removeSector(sector) {
  const res = await api('/api/priority/sector', { method: 'DELETE', body: JSON.stringify({ sector }) });
  toast(`Removed sector "${sector}" (${res.removed_count} companies)`, 'info');
  await Promise.all([loadCompanies(), loadPriority(), loadStats(), loadSectors()]);
}

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------
document.getElementById('search').addEventListener('input', () => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(loadCompanies, 200);
});
document.getElementById('sector-filter').addEventListener('change', () => {
  const val = document.getElementById('sector-filter').value;
  document.getElementById('btn-add-sector').disabled = !val;
  loadCompanies();
});
document.getElementById('btn-add-sector').addEventListener('click', addSector);

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
(async () => {
  await Promise.all([loadSectors(), loadStats()]);
  await loadCompanies();
  await loadPriority();
})();
</script>
</body>
</html>
"""
