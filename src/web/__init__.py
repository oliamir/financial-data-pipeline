"""Web dashboard — Flask app with REST API, WebSocket, and real-time updates.

Provides a web interface for monitoring pipeline runs, viewing
company data, managing providers, and triggering pipeline execution
with real-time progress via WebSocket (Flask-SocketIO).
"""

import csv
import json
import re
import asyncio
import threading
from pathlib import Path
from flask import Flask, jsonify, render_template_string, request

import yaml

from ..config.loader import load_companies, load_providers_config, _find_project_root
from ..storage.file_manager import FileManager
from ..utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# TASE companies CSV loader (cached in memory)
# ---------------------------------------------------------------------------

_tase_companies_cache: list[dict] | None = None


def _load_tase_companies() -> list[dict]:
    """Load and cache all TASE companies from tasecompanies.csv."""
    global _tase_companies_cache
    if _tase_companies_cache is not None:
        return _tase_companies_cache

    csv_path = _find_project_root() / "tasecompanies.csv"
    if not csv_path.exists():
        logger.warning(f"TASE companies CSV not found: {csv_path}")
        _tase_companies_cache = []
        return _tase_companies_cache

    companies = []
    with open(csv_path, "r", encoding="utf-8") as f:
        # Skip 2 header rows ("List of TASE Companies" + "As of ...")
        next(f)
        next(f)
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Name") or "").strip()
            if not name:
                continue
            companies.append({
                "name": name,
                "full_name": (row.get("Full Name") or "").strip(),
                "sector": (row.get("TASE Sector") or "").strip(),
                "issuer_no": (row.get("Issuer No.") or "").strip(),
                "corporate_no": (row.get("Corporate No.") or "").strip(),
                "website": (row.get("Website") or "").strip(),
                "market_cap": (row.get("Market Cap (K ILS)") or "").strip(),
            })

    _tase_companies_cache = companies
    logger.info(f"Loaded {len(companies)} TASE companies from CSV")
    return _tase_companies_cache


def _generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from a company name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug.strip("-")


def _map_tase_sector(tase_sector: str) -> str:
    """Map verbose TASE sector string to a simplified sector slug."""
    s = tase_sector.lower()
    if "energy" in s or "oil" in s or "gas" in s:
        return "energy"
    if "tech" in s or "software" in s or "it service" in s or "defence" in s:
        return "technology"
    if "real-estate" in s or "real estate" in s or "construction" in s:
        return "real_estate"
    if "bank" in s or "financial" in s or "insurance" in s:
        return "financial"
    if "pharma" in s or "bio" in s or "medical" in s:
        return "healthcare"
    if "food" in s or "retail" in s or "commerce" in s:
        return "consumer"
    if "telecom" in s or "communication" in s:
        return "telecom"
    if "industry" in s or "metal" in s or "chemical" in s:
        return "industrial"
    if "investment" in s or "holding" in s:
        return "investment"
    return "other"


app = Flask(__name__)

# Try to import SocketIO (optional dependency)
try:
    from flask_socketio import SocketIO, emit
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
    HAS_SOCKETIO = True
except ImportError:
    socketio = None
    HAS_SOCKETIO = False
    logger.warning("flask-socketio not installed. WebSocket disabled. Install: pip install flask-socketio")


# ---------------------------------------------------------------------------
# EventBus -> WebSocket bridge
# ---------------------------------------------------------------------------

def _setup_event_bridge():
    """Subscribe to EventBus events and forward to WebSocket clients."""
    if not HAS_SOCKETIO:
        return

    try:
        from ..progress import EventBus, PipelineEvent

        def forward_event(event: PipelineEvent):
            """Forward pipeline events to WebSocket clients."""
            socketio.emit("pipeline_event", event.to_dict())

        bus = EventBus.instance()
        bus.subscribe(None, forward_event)  # Subscribe to all events
        logger.info("EventBus -> WebSocket bridge established")
    except ImportError:
        logger.debug("Progress module not available, skipping event bridge")


# ---------------------------------------------------------------------------
# Dashboard HTML template — two tabs: Dashboard + Priority List
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Finance Pipeline</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: #0f172a; color: #e2e8f0; }

        /* Header */
        .header { background: linear-gradient(135deg, #1e3a5f, #0f172a);
                   padding: 1.1rem 2rem; border-bottom: 1px solid #334155;
                   display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 1.4rem; color: #60a5fa; }
        .header p { color: #94a3b8; margin-top: 0.2rem; font-size: 0.8rem; }
        .header-right { display: flex; gap: 1rem; align-items: center; }
        .container { max-width: 1400px; margin: 0 auto; padding: 1.25rem 2rem; }

        /* Tabs */
        .tabs { display: flex; gap: 0; margin-bottom: 1.25rem; border-bottom: 1px solid #334155; }
        .tab { padding: 0.7rem 1.5rem; cursor: pointer; color: #94a3b8;
               border-bottom: 2px solid transparent; transition: all 0.2s;
               font-weight: 500; font-size: 0.9rem; user-select: none; }
        .tab:hover { color: #e2e8f0; }
        .tab.active { color: #60a5fa; border-bottom-color: #60a5fa; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        /* ===== DASHBOARD TAB ===== */

        /* Provider status bar */
        .provider-bar { display: flex; gap: 0.75rem; margin-bottom: 1.25rem;
                        background: #1e293b; border-radius: 10px; padding: 0.65rem 1rem;
                        border: 1px solid #334155; align-items: center; flex-wrap: wrap; }
        .provider-bar-label { color: #64748b; font-size: 0.75rem; font-weight: 600;
                              text-transform: uppercase; letter-spacing: 0.05em; margin-right: 0.25rem; }
        .provider-chip { display: inline-flex; align-items: center; gap: 0.35rem;
                          padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.78rem;
                          background: #0f172a; border: 1px solid #334155; }
        .provider-chip .dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
        .dot-active { background: #16a34a; }
        .dot-off { background: #475569; }
        .provider-chip .model { color: #64748b; font-size: 0.68rem; margin-left: 0.2rem; }
        .routing-sep { width: 1px; height: 18px; background: #334155; margin: 0 0.15rem; }
        .route-chip { display: inline-flex; align-items: center; gap: 0.25rem;
                       font-size: 0.72rem; color: #94a3b8; padding: 0.2rem 0.5rem;
                       background: #0f172a; border-radius: 4px; border: 1px solid #1e293b; }
        .route-chip .rt { color: #60a5fa; font-weight: 500; }

        /* Summary cards row */
        .summary-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.75rem;
                       margin-bottom: 1.25rem; }
        .summary-card { background: #1e293b; border-radius: 10px; padding: 0.9rem 1rem;
                        border: 1px solid #334155; text-align: center; }
        .summary-card .num { font-size: 1.6rem; font-weight: 700; color: #60a5fa; line-height: 1; }
        .summary-card .label { color: #64748b; font-size: 0.7rem; text-transform: uppercase;
                                letter-spacing: 0.05em; margin-top: 0.3rem; }

        /* Two-column layout: left overview + right activity */
        .dash-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
        .dash-panel { background: #1e293b; border-radius: 10px; padding: 1.25rem;
                      border: 1px solid #334155; }
        .dash-panel h3 { color: #60a5fa; font-size: 0.85rem; font-weight: 600;
                          text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.75rem; }

        /* Coverage bars */
        .coverage-row { display: flex; align-items: center; gap: 0.75rem; padding: 0.45rem 0;
                        border-bottom: 1px solid #0f172a; }
        .coverage-row:last-child { border-bottom: none; }
        .cov-label { min-width: 110px; font-size: 0.82rem; color: #cbd5e1; }
        .cov-bar-bg { flex: 1; height: 6px; background: #334155; border-radius: 3px; overflow: hidden; }
        .cov-bar { height: 100%; border-radius: 3px; transition: width 0.4s ease; }
        .cov-bar-blue { background: #3b82f6; }
        .cov-bar-green { background: #16a34a; }
        .cov-bar-amber { background: #f59e0b; }
        .cov-val { min-width: 36px; text-align: right; font-size: 0.78rem; color: #94a3b8;
                   font-variant-numeric: tabular-nums; }

        /* Top companies mini-table */
        .top-table { width: 100%; border-collapse: collapse; }
        .top-table th { text-align: left; padding: 0.35rem 0.5rem; color: #64748b;
                         font-size: 0.7rem; font-weight: 600; text-transform: uppercase;
                         letter-spacing: 0.04em; border-bottom: 1px solid #334155; }
        .top-table td { padding: 0.4rem 0.5rem; border-bottom: 1px solid #0f172a; font-size: 0.82rem; }
        .top-table tr:hover { background: #0f172a; }
        .top-table .nm { color: #e2e8f0; font-weight: 500; }
        .top-table .sl { color: #64748b; font-size: 0.7rem; }
        .top-table .n { text-align: center; font-variant-numeric: tabular-nums; }
        .ck-y { color: #16a34a; }
        .ck-n { color: #475569; }

        /* Activity log */
        .event-log { max-height: 340px; overflow-y: auto; }
        .event-item { padding: 0.3rem 0; border-bottom: 1px solid #0f172a;
                       display: flex; gap: 0.5rem; align-items: baseline; font-size: 0.78rem; }
        .event-item:hover { background: #0f172a; border-radius: 3px; }
        .ev-time { color: #475569; min-width: 62px; font-size: 0.72rem; font-family: ui-monospace, monospace; }
        .ev-type { color: #60a5fa; font-weight: 600; min-width: 120px; font-size: 0.72rem; }
        .ev-slug { color: #94a3b8; min-width: 70px; font-size: 0.72rem; }
        .ev-msg { color: #cbd5e1; flex: 1; }
        .event-empty { color: #475569; text-align: center; padding: 1.5rem; font-size: 0.82rem; }

        /* ===== PRIORITY LIST TAB ===== */

        /* Priority group headers */
        .priority-header { display: flex; align-items: center; gap: 0.75rem; margin: 1.25rem 0 0.6rem;
                           padding-bottom: 0.4rem; border-bottom: 1px solid #334155; }
        .priority-header:first-child { margin-top: 0; }
        .priority-header h2 { font-size: 0.82rem; font-weight: 600; text-transform: uppercase;
                               letter-spacing: 0.05em; }
        .priority-header .count { color: #64748b; font-size: 0.78rem; }
        .ph-high h2 { color: #f87171; }
        .ph-low h2 { color: #94a3b8; }

        /* Company table */
        .co-table { width: 100%; border-collapse: collapse; }
        .co-table th { text-align: left; padding: 0.45rem 0.7rem; color: #64748b;
                        font-size: 0.72rem; font-weight: 600; text-transform: uppercase;
                        letter-spacing: 0.04em; border-bottom: 1px solid #334155; }
        .co-table td { padding: 0.55rem 0.7rem; border-bottom: 1px solid #1e293b;
                        font-size: 0.88rem; vertical-align: middle; }
        .co-table tr { transition: background 0.12s; }
        .co-table tr:hover { background: #1e293b; }
        .co-table .name-col { display: flex; flex-direction: column; }
        .co-table .name-col .nm { color: #e2e8f0; font-weight: 600; }
        .co-table .name-col .sl { color: #64748b; font-size: 0.72rem; }
        .co-table .n { text-align: center; font-variant-numeric: tabular-nums; }
        .co-table .ck { text-align: center; font-size: 1rem; }
        .date-cell { color: #94a3b8; font-size: 0.78rem; white-space: nowrap; }

        /* TASE filter bar */
        .tase-filter-bar { display: flex; gap: 0.75rem; margin-bottom: 1.25rem; align-items: center; }
        .tase-filter-input { flex: 1; padding: 0.55rem 1rem; font-size: 0.88rem;
                             background: #1e293b; border: 1px solid #334155; border-radius: 8px;
                             color: #e2e8f0; outline: none; transition: border-color 0.2s; }
        .tase-filter-input:focus { border-color: #3b82f6; }
        .tase-filter-input::placeholder { color: #64748b; }
        .tase-count { color: #64748b; font-size: 0.78rem; white-space: nowrap; }

        /* Priority search dropdown */
        .prio-search-wrap { position: relative; margin-bottom: 1rem; }
        .prio-search-input { width: 100%; padding: 0.55rem 1rem; font-size: 0.88rem;
                             background: #1e293b; border: 1px solid #334155; border-radius: 8px;
                             color: #e2e8f0; outline: none; transition: border-color 0.2s; }
        .prio-search-input:focus { border-color: #3b82f6; }
        .prio-search-input::placeholder { color: #64748b; }
        .prio-dropdown { position: absolute; top: 100%; left: 0; right: 0; z-index: 50;
                         background: #1e293b; border: 1px solid #334155; border-top: none;
                         border-radius: 0 0 8px 8px; max-height: 320px; overflow-y: auto;
                         display: none; }
        .prio-dropdown.open { display: block; }
        .prio-dd-item { display: flex; align-items: center; justify-content: space-between;
                        padding: 0.5rem 1rem; border-bottom: 1px solid #0f172a; transition: background 0.1s; }
        .prio-dd-item:hover { background: #0f172a; }
        .prio-dd-item:last-child { border-bottom: none; }
        .prio-dd-info { flex: 1; min-width: 0; }
        .prio-dd-name { color: #e2e8f0; font-weight: 600; font-size: 0.85rem; }
        .prio-dd-detail { color: #64748b; font-size: 0.72rem; margin-top: 0.1rem; }
        .prio-dd-empty { padding: 0.75rem 1rem; color: #64748b; font-size: 0.82rem; text-align: center; }

        /* Add / tracked badges */
        .btn-add { background: #16a34a; font-size: 0.72rem; padding: 0.22rem 0.55rem;
                   border: none; color: white; border-radius: 5px; cursor: pointer;
                   font-weight: 500; white-space: nowrap; transition: 0.12s; }
        .btn-add:hover { background: #15803d; }
        .badge-tracked { font-size: 0.68rem; padding: 0.18rem 0.45rem; border-radius: 4px;
                         background: #1e3a5f; color: #60a5fa; border: 1px solid #334155;
                         white-space: nowrap; }
        .badge-high { background: #3b1c1c; color: #f87171; border-color: #5c2020; cursor: pointer;
                      transition: background 0.15s; }
        .badge-high:hover { background: #5c2020; }

        /* Run controls */
        .run-controls { display: flex; gap: 0.3rem; align-items: center; }
        .btn { background: #3b82f6; color: white; border: none; padding: 0.3rem 0.65rem;
                border-radius: 5px; cursor: pointer; font-size: 0.78rem; transition: 0.12s;
                font-weight: 500; white-space: nowrap; }
        .btn:hover { background: #2563eb; }
        .btn-sm { padding: 0.22rem 0.45rem; font-size: 0.72rem; }
        select { background: #0f172a; color: #e2e8f0; border: 1px solid #334155;
                 border-radius: 5px; padding: 0.25rem 0.35rem; font-size: 0.72rem; cursor: pointer; }
        select:focus { outline: 1px solid #3b82f6; }

        /* Inline progress bar */
        .progress { height: 3px; background: #334155; border-radius: 2px; overflow: hidden; }
        .progress-bar { height: 100%; background: #3b82f6; transition: width 0.5s ease; }

        /* Connection indicator */
        .ws-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
        .ws-on { background: #16a34a; }
        .ws-off { background: #dc2626; }

        /* Responsive */
        @media (max-width: 1000px) {
            .dash-grid { grid-template-columns: 1fr; }
            .summary-row { grid-template-columns: repeat(3, 1fr); }
        }
        @media (max-width: 700px) {
            .co-table .hide-m { display: none; }
            .summary-row { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>Finance Pipeline</h1>
            <p>v3 Dashboard</p>
        </div>
        <div class="header-right">
            <span class="ws-dot" id="wsDot"></span>
            <span id="wsLabel" style="color:#94a3b8;font-size:0.78rem;"></span>
            <button class="btn" onclick="location.reload()">Refresh</button>
        </div>
    </div>
    <div class="container">
        <div class="tabs">
            <div class="tab active" onclick="showTab('dashboard')">Dashboard</div>
            <div class="tab" onclick="showTab('priority')">Priority List</div>
        </div>

        <!-- ============ DASHBOARD TAB ============ -->
        <div class="tab-content active" id="tab-dashboard">
            <div class="provider-bar" id="providerBar">
                <span class="provider-bar-label">Providers</span>
            </div>
            <div class="summary-row" id="summaryRow"></div>
            <div class="dash-grid">
                <div class="dash-panel">
                    <h3>Coverage</h3>
                    <div id="coverageBars"></div>
                    <h3 style="margin-top:1.25rem;">Tracked Companies</h3>
                    <table class="top-table">
                        <thead><tr>
                            <th>Company</th><th class="n">Rpts</th><th class="n">Fin</th>
                            <th style="width:45%; text-align:left;">Actions & Status</th>
                        </tr></thead>
                        <tbody id="trackedCompanies"></tbody>
                    </table>
                </div>
                <div class="dash-panel">
                    <h3>Activity</h3>
                    <div class="event-log" id="eventLog">
                        <div class="event-empty">No events yet. Run a pipeline to see activity here.</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- ============ PRIORITY LIST TAB ============ -->
        <div class="tab-content" id="tab-priority">
            <div class="prio-search-wrap">
                <input type="text" class="prio-search-input" id="prioSearchInput"
                       placeholder="Search TASE companies to add to High Priority..." autocomplete="off">
                <div class="prio-dropdown" id="prioDropdown"></div>
            </div>
            <div id="prioritySection"></div>
            <div class="tase-filter-bar">
                <input type="text" class="tase-filter-input" id="taseFilterInput"
                       placeholder="Filter companies..." autocomplete="off">
                <span class="tase-count" id="taseCount"></span>
            </div>
            <table class="co-table" id="taseTable">
                <thead><tr>
                    <th style="width:22%">Company</th>
                    <th style="width:28%">Sector</th>
                    <th class="n" style="width:12%">Market Cap</th>
                    <th style="width:18%">Website</th>
                    <th class="n" style="width:10%">Status</th>
                </tr></thead>
                <tbody id="taseBody"></tbody>
            </table>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js"></script>
    <script>
        let allCompanies = [];

        function showTab(name) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + name).classList.add('active');
        }

        // ─── Dashboard tab ───

        function renderSummary(companies) {
            const el = document.getElementById('summaryRow');
            const total = companies.length;
            const rpts = companies.reduce((s,c) => s + c.reports_count, 0);
            const periods = companies.reduce((s,c) => s + c.periods, 0);
            const fins = companies.filter(c => c.has_financials).length;
            const memos = companies.filter(c => c.has_memo).length;
            el.innerHTML =
                '<div class="summary-card"><div class="num">' + total + '</div><div class="label">Companies</div></div>' +
                '<div class="summary-card"><div class="num">' + rpts + '</div><div class="label">Reports</div></div>' +
                '<div class="summary-card"><div class="num">' + periods + '</div><div class="label">Periods</div></div>' +
                '<div class="summary-card"><div class="num">' + fins + '</div><div class="label">Financials</div></div>' +
                '<div class="summary-card"><div class="num">' + memos + '</div><div class="label">Memos</div></div>';
        }

        function renderCoverage(companies) {
            const el = document.getElementById('coverageBars');
            const total = companies.length || 1;
            const scraped = companies.filter(c => c.last_scrape).length;
            const withReports = companies.filter(c => c.reports_count > 0).length;
            const withFin = companies.filter(c => c.has_financials).length;
            const withMemo = companies.filter(c => c.has_memo).length;

            const bars = [
                { label: 'Scraped', val: scraped, pct: Math.round(scraped/total*100), cls: 'cov-bar-blue' },
                { label: 'Has Reports', val: withReports, pct: Math.round(withReports/total*100), cls: 'cov-bar-blue' },
                { label: 'Financials', val: withFin, pct: Math.round(withFin/total*100), cls: 'cov-bar-green' },
                { label: 'Memos', val: withMemo, pct: Math.round(withMemo/total*100), cls: 'cov-bar-amber' },
            ];
            el.innerHTML = bars.map(b =>
                '<div class="coverage-row">' +
                    '<span class="cov-label">' + b.label + '</span>' +
                    '<div class="cov-bar-bg"><div class="cov-bar ' + b.cls + '" style="width:' + b.pct + '%"></div></div>' +
                    '<span class="cov-val">' + b.val + '/' + total + '</span>' +
                '</div>'
            ).join('');
        }

        function renderTrackedCompanies(companies) {
            const tbody = document.getElementById('trackedCompanies');
            // Sort to show high priority first, then alphabetically
            const sorted = [...companies].sort((a,b) => {
                if (a.priority === 'high' && b.priority !== 'high') return -1;
                if (a.priority !== 'high' && b.priority === 'high') return 1;
                return a.name.localeCompare(b.name);
            });

            tbody.innerHTML = sorted.map(c =>
                '<tr>' +
                    '<td><span class="nm">' + c.name + '</span> <span class="sl">' + c.slug + '</span></td>' +
                    '<td class="n">' + c.reports_count + '</td>' +
                    '<td class="n">' + (c.has_financials ? '<span class="ck-y">&#10003;</span>' : '<span class="ck-n">&#8212;</span>') + '</td>' +
                    '<td>' +
                        '<div class="run-controls" style="gap:0.4rem; justify-content:flex-start;">' +
                            '<button class="btn btn-sm" onclick="runPipeline(\\''+c.slug+'\\', \\'download\\')" style="background:#0f766e">Download</button>' +
                            '<button class="btn btn-sm" onclick="runPipeline(\\''+c.slug+'\\', \\'parse\\')" style="background:#5b21b6">AI Scrape</button>' +
                            '<div style="flex:1; margin-left:8px; min-width:80px;">' +
                                '<div class="progress" style="width:100%" id="dash-prog-'+c.slug+'"><div class="progress-bar" style="width:0%"></div></div>' +
                                '<div id="dash-stat-'+c.slug+'" style="font-size:0.65rem; color:#94a3b8; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="Ready">Ready</div>' +
                            '</div>' +
                        '</div>' +
                    '</td>' +
                '</tr>'
            ).join('');
            
            // Fetch initial progress
            fetch('/api/progress').then(r => r.json()).then(data => {
                Object.keys(data).forEach(slug => {
                    const prog = data[slug];
                    updateDashboardProgress(slug, prog.progress_pct, prog.current_step);
                });
            });
        }


        // ─── Priority List tab ───

        let allTaseCompanies = [];

        function renderPrioritySection(companies) {
            const container = document.getElementById('prioritySection');
            const highList = companies.filter(c => c.priority === 'high');
            if (highList.length === 0) { container.innerHTML = ''; return; }

            highList.sort((a, b) => {
                const sa = a.reports_count + a.periods*10 + (a.has_memo?50:0);
                const sb = b.reports_count + b.periods*10 + (b.has_memo?50:0);
                if (sb !== sa) return sb - sa;
                return a.name.localeCompare(b.name);
            });

            container.innerHTML =
                '<div class="priority-header ph-high">' +
                    '<h2>High Priority</h2>' +
                    '<span class="count">' + highList.length + ' companies</span>' +
                '</div>' +
                '<table class="co-table">' +
                    '<thead><tr>' +
                        '<th style="width:22%">Company</th>' +
                        '<th class="n" style="width:7%">Reports</th>' +
                        '<th class="n" style="width:7%">Periods</th>' +
                        '<th class="ck" style="width:5%">Fin</th>' +
                        '<th class="ck" style="width:5%">Memo</th>' +
                        '<th class="hide-m" style="width:11%">Last Scrape</th>' +
                        '<th style="width:43%">Actions</th>' +
                    '</tr></thead>' +
                    '<tbody id="ptb-high"></tbody>' +
                '</table>';

            const tbody = document.getElementById('ptb-high');
            highList.forEach(c => {
                const tr = document.createElement('tr');
                const sd = c.last_scrape ? new Date(c.last_scrape).toLocaleDateString() : '<span style="color:#475569">Never</span>';
                tr.innerHTML =
                    '<td><div class="name-col"><span class="nm">' + c.name + '</span><span class="sl">' + c.slug + '</span></div></td>' +
                    '<td class="n">' + c.reports_count + '</td>' +
                    '<td class="n">' + c.periods + '</td>' +
                    '<td class="ck">' + (c.has_financials ? '<span class="ck-y">&#10003;</span>' : '<span class="ck-n">&#8212;</span>') + '</td>' +
                    '<td class="ck">' + (c.has_memo ? '<span class="ck-y">&#10003;</span>' : '<span class="ck-n">&#8212;</span>') + '</td>' +
                    '<td class="hide-m date-cell">' + sd + '</td>' +
                    '<td><div class="run-controls">' +
                        '<button class="btn btn-sm" onclick="runPipeline(\\''+c.slug+'\\')">Run</button>' +
                        '<select id="prov-'+c.slug+'"><option value="">auto</option></select>' +
                        '<select id="step-'+c.slug+'">' +
                            '<option value="">all steps</option>' +
                            '<option value="download">download</option>' +
                            '<option value="parse">parse</option>' +
                            '<option value="model">model</option>' +
                            '<option value="memo">memo</option>' +
                        '</select>' +
                        '<div class="progress" style="width:55px" id="progress-'+c.slug+'"><div class="progress-bar" style="width:0%"></div></div>' +
                    '</div></td>';
                tbody.appendChild(tr);
            });
        }

        function loadTaseCompanies() {
            fetch('/api/tase-companies').then(r => r.json()).then(data => {
                allTaseCompanies = data;
                renderTaseTable(data);
            });
        }

        function renderTaseTable(list) {
            const tbody = document.getElementById('taseBody');
            const countEl = document.getElementById('taseCount');
            const esc = s => s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');

            countEl.textContent = list.length + ' companies';
            tbody.innerHTML = list.map(c => {
                const mcap = c.market_cap && c.market_cap !== '0'
                    ? (parseInt(c.market_cap) / 1000).toFixed(1) + 'M'
                    : '';
                const site = c.website
                    ? '<a href="' + (c.website.startsWith('http') ? '' : 'https://') + esc(c.website) + '" target="_blank" style="color:#60a5fa;font-size:0.78rem;text-decoration:none">' + esc(c.website.replace(/https?:\\/\\//, '').slice(0,25)) + '</a>'
                    : '<span style="color:#475569">-</span>';

                let status;
                if (c.priority === 'high') {
                    status = '<span class="badge-tracked badge-high" data-issuer="' + esc(c.issuer_no) +
                        '" onclick="removePriority(event)">&times; High Priority</span>';
                } else {
                    status = '<button class="btn-add" data-issuer="' + esc(c.issuer_no) +
                        '" data-name="' + esc(c.full_name || c.name) +
                        '" data-sector="' + esc(c.sector) +
                        '" data-website="' + esc(c.website) +
                        '" data-priority="high"' +
                        ' onclick="addTaseCompany(event)">+ High Priority</button>';
                }

                return '<tr>' +
                    '<td><div class="name-col"><span class="nm">' + esc(c.name) + '</span>' +
                        '<span class="sl">' + esc(c.full_name && c.full_name !== c.name ? c.full_name : '') + '</span></div></td>' +
                    '<td style="font-size:0.78rem;color:#94a3b8">' + esc(c.sector) + '</td>' +
                    '<td class="n" style="font-size:0.82rem">' + mcap + '</td>' +
                    '<td>' + site + '</td>' +
                    '<td class="n">' + status + '</td>' +
                '</tr>';
            }).join('');
        }

        function filterTaseTable() {
            const q = document.getElementById('taseFilterInput').value.trim().toLowerCase();
            if (!q) { renderTaseTable(allTaseCompanies); return; }
            const filtered = allTaseCompanies.filter(c =>
                c.name.toLowerCase().includes(q) ||
                c.full_name.toLowerCase().includes(q) ||
                c.sector.toLowerCase().includes(q)
            );
            renderTaseTable(filtered);
        }

        document.getElementById('taseFilterInput').addEventListener('input', function() {
            clearTimeout(this._timer);
            this._timer = setTimeout(filterTaseTable, 200);
        });

        // ─── Providers bar ───

        function loadProviders() {
            Promise.all([
                fetch('/api/providers').then(r => r.json()),
                fetch('/api/providers/routing').then(r => r.json())
            ]).then(([providers, routing]) => {
                const bar = document.getElementById('providerBar');
                bar.innerHTML = '<span class="provider-bar-label">Providers</span>';

                providers.forEach(p => {
                    const chip = document.createElement('span');
                    chip.className = 'provider-chip';
                    chip.innerHTML = '<span class="dot ' + (p.available ? 'dot-active' : 'dot-off') + '"></span>' + p.name + '<span class="model">' + p.model + '</span>';
                    bar.appendChild(chip);
                });

                if (Object.keys(routing).length > 0) {
                    bar.appendChild(Object.assign(document.createElement('span'), { className: 'routing-sep' }));
                    const rl = document.createElement('span');
                    rl.className = 'provider-bar-label'; rl.textContent = 'Routing';
                    bar.appendChild(rl);

                    Object.entries(routing).forEach(([task, route]) => {
                        const chip = document.createElement('span');
                        chip.className = 'route-chip';
                        const fb = (route.fallback||[]).length > 0 ? ' \\u2192 ' + route.fallback.join(', ') : '';
                        chip.innerHTML = '<span class="rt">' + task + '</span>' + route.primary + fb;
                        bar.appendChild(chip);
                    });
                }

                // Fill provider dropdowns in priority list
                document.querySelectorAll('select[id^="prov-"]').forEach(sel => {
                    providers.forEach(p => {
                        if (p.available) {
                            const opt = document.createElement('option');
                            opt.value = p.name; opt.textContent = p.name;
                            sel.appendChild(opt);
                        }
                    });
                });
            });
        }

        // ─── Load all ───

        function loadCompanies() {
            fetch('/api/companies').then(r => r.json()).then(data => {
                allCompanies = data;
                renderSummary(data);
                renderCoverage(data);
                renderTrackedCompanies(data);
                renderPrioritySection(data);
                loadProviders();
            });
        }

        // ─── Run pipeline ───

        function runPipeline(slug, forceStep) {
            const pSel = document.getElementById('prov-' + slug);
            const sSel = document.getElementById('step-' + slug);
            const body = {};
            if (pSel && pSel.value) body.provider = pSel.value;
            if (forceStep) {
                body.steps = forceStep;
            } else if (sSel && sSel.value) {
                body.steps = sSel.value;
            }

            fetch('/api/company/' + slug + '/run', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body),
            }).then(r => r.json()).then(data => {
                if (data.error) alert('Error: ' + data.error);
                else addEvent('pipeline.started', slug, 'Pipeline started: ' + (body.steps || 'all steps'));
            }).catch(err => alert('Failed: ' + err));
        }

        function updateDashboardProgress(slug, pct, statusText) {
            const pg = document.getElementById('dash-prog-' + slug);
            if (pg && pct !== undefined) {
                pg.querySelector('.progress-bar').style.width = pct + '%';
            }
            const st = document.getElementById('dash-stat-' + slug);
            if (st && statusText) {
                st.textContent = statusText;
                st.title = statusText;
            }
        }

        // ─── WebSocket ───

        let socket = null;
        function connectWS() {
            const dot = document.getElementById('wsDot');
            const lbl = document.getElementById('wsLabel');

            if (typeof io === 'undefined') {
                dot.className = 'ws-dot ws-off'; lbl.textContent = 'WS off'; return;
            }
            socket = io();
            socket.on('connect', () => { dot.className = 'ws-dot ws-on'; lbl.textContent = 'Live'; });
            socket.on('disconnect', () => { dot.className = 'ws-dot ws-off'; lbl.textContent = 'Offline'; });
            socket.on('pipeline_event', (evt) => {
                addEvent(evt.event_type, evt.company_slug, evt.message);
                if (evt.company_slug) {
                    const pg = document.getElementById('progress-' + evt.company_slug);
                    if (pg && evt.data && evt.data.progress_pct !== undefined)
                        pg.querySelector('.progress-bar').style.width = evt.data.progress_pct + '%';
                        
                    if (evt.data && evt.data.progress_pct !== undefined) {
                        updateDashboardProgress(evt.company_slug, evt.data.progress_pct, evt.data.current_step || evt.message);
                    } else {
                        updateDashboardProgress(evt.company_slug, undefined, evt.message);
                    }
                }
                // Refresh data when a pipeline step completes or pipeline finishes
                const t = evt.event_type || '';
                if (t.includes('completed') || t.includes('finished') || t.includes('failed')) {
                    loadCompanies();
                }
            });
        }

        function addEvent(type, slug, message) {
            const log = document.getElementById('eventLog');
            const empty = log.querySelector('.event-empty');
            if (empty) empty.remove();

            const item = document.createElement('div');
            item.className = 'event-item';
            const t = new Date().toLocaleTimeString();
            item.innerHTML = '<span class="ev-time">' + t + '</span>'
                + '<span class="ev-type">' + type + '</span>'
                + '<span class="ev-slug">' + (slug||'') + '</span>'
                + '<span class="ev-msg">' + (message||'') + '</span>';
            log.prepend(item);
            while (log.children.length > 200) log.lastChild.remove();
        }

        // ─── Priority search (add to high priority) ───

        const prioInput = document.getElementById('prioSearchInput');
        const prioDropdown = document.getElementById('prioDropdown');
        let prioTimer = null;

        prioInput.addEventListener('input', function() {
            clearTimeout(prioTimer);
            const q = this.value.trim().toLowerCase();
            if (q.length < 2) { prioDropdown.classList.remove('open'); return; }
            prioTimer = setTimeout(() => {
                // Filter from already-loaded TASE list, exclude already high-priority
                const highIds = new Set(allCompanies.filter(c => c.priority === 'high').map(c => c.slug));
                const matches = allTaseCompanies.filter(c => {
                    if (c.priority === 'high') return false;
                    return c.name.toLowerCase().includes(q) ||
                           c.full_name.toLowerCase().includes(q) ||
                           c.sector.toLowerCase().includes(q);
                }).slice(0, 10);

                const esc = s => s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
                if (matches.length === 0) {
                    prioDropdown.innerHTML = '<div class="prio-dd-empty">No matches found</div>';
                } else {
                    prioDropdown.innerHTML = matches.map(c => {
                        const mcap = c.market_cap && c.market_cap !== '0'
                            ? (parseInt(c.market_cap)/1000).toFixed(1) + 'M' : '';
                        return '<div class="prio-dd-item">' +
                            '<div class="prio-dd-info">' +
                                '<div class="prio-dd-name">' + esc(c.name) + '</div>' +
                                '<div class="prio-dd-detail">' + esc(c.sector) +
                                    (mcap ? ' &middot; ' + mcap : '') + '</div>' +
                            '</div>' +
                            '<button class="btn-add" data-issuer="' + esc(c.issuer_no) +
                                '" data-name="' + esc(c.full_name || c.name) +
                                '" data-sector="' + esc(c.sector) +
                                '" data-website="' + esc(c.website) +
                                '" data-priority="high"' +
                                ' onclick="addTaseCompany(event)">+ High Priority</button>' +
                        '</div>';
                    }).join('');
                }
                prioDropdown.classList.add('open');
            }, 250);
        });

        prioInput.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') { prioDropdown.classList.remove('open'); this.blur(); }
        });
        document.addEventListener('click', function(e) {
            if (!e.target.closest('.prio-search-wrap')) prioDropdown.classList.remove('open');
        });

        // ─── Add TASE company ───

        function addTaseCompany(evt) {
            const btn = evt.target;
            const d = btn.dataset;
            const origText = btn.textContent;
            btn.disabled = true; btn.textContent = '...';

            fetch('/api/tase-companies/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    issuer_no: d.issuer,
                    name: d.name,
                    sector: d.sector,
                    website: d.website,
                    priority: d.priority || 'low',
                }),
            }).then(r => r.json()).then(data => {
                if (data.error) { alert('Error: ' + data.error); btn.disabled = false; btn.textContent = origText; return; }
                prioDropdown.classList.remove('open');
                prioInput.value = '';
                loadCompanies();
                loadTaseCompanies();
            }).catch(err => { alert('Failed: ' + err); btn.disabled = false; btn.textContent = origText; });
        }

        function removePriority(evt) {
            const el = evt.target;
            const issuer = el.dataset.issuer;
            el.style.opacity = '0.5'; el.style.pointerEvents = 'none';

            fetch('/api/tase-companies/remove', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ issuer_no: issuer }),
            }).then(r => r.json()).then(data => {
                if (data.error) { alert('Error: ' + data.error); el.style.opacity = ''; el.style.pointerEvents = ''; return; }
                loadCompanies();
                loadTaseCompanies();
            }).catch(err => { alert('Failed: ' + err); el.style.opacity = ''; el.style.pointerEvents = ''; });
        }

        // ─── Auto-refresh ───

        let autoRefreshInterval = null;

        function startAutoRefresh() {
            // Refresh company data every 30 seconds
            if (autoRefreshInterval) clearInterval(autoRefreshInterval);
            autoRefreshInterval = setInterval(loadCompanies, 30000);
        }

        // ─── Init ───
        loadCompanies();
        loadTaseCompanies();
        connectWS();
        startAutoRefresh();
    </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    """Serve the dashboard page."""
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/companies")
def api_companies():
    """List all companies with their status."""
    companies = load_companies()
    result = []

    for slug, company in companies.items():
        fm = FileManager(slug)
        meta = fm.load_meta()
        financials = fm.load_financials()
        memo = fm.load_memo()

        result.append({
            "slug": slug,
            "name": company.name,
            "sector": company.sector,
            "priority": company.priority.value,
            "company_type": company.company_type.value,
            "reports_count": meta.get("reports_downloaded", 0),
            "last_scrape": meta.get("last_scrape"),
            "has_financials": len(financials) > 0,
            "has_memo": memo is not None,
            "periods": len(financials),
        })

    return jsonify(result)


@app.route("/api/tase-companies")
def api_tase_all():
    """Return all TASE companies with tracked/priority status."""
    existing = load_companies()
    # Map issuer_no -> company info for tracked companies
    tracked_map = {}
    for c in existing.values():
        if c.tase_company_id:
            tracked_map[c.tase_company_id] = {
                "slug": c.slug,
                "priority": c.priority.value,
            }

    tase = _load_tase_companies()
    results = []
    for c in tase:
        info = tracked_map.get(c["issuer_no"])
        results.append({
            **c,
            "tracked": info is not None,
            "priority": info["priority"] if info else None,
            "slug": info["slug"] if info else None,
        })
    return jsonify(results)


@app.route("/api/tase-companies/add", methods=["POST"])
def api_tase_add():
    """Add a TASE company to companies.yaml, or update priority if already tracked."""
    data = request.get_json(silent=True) or {}
    issuer_no = data.get("issuer_no", "").strip()
    name = data.get("name", "").strip()
    if not issuer_no or not name:
        return jsonify({"error": "issuer_no and name are required"}), 400

    priority = data.get("priority", "low")
    yaml_path = _find_project_root() / "config" / "companies.yaml"

    # Check if already tracked — if so, update priority
    existing = load_companies()
    for c in existing.values():
        if c.tase_company_id == issuer_no:
            if c.priority.value == priority:
                return jsonify({"error": f"Company already tracked as '{c.slug}' with {priority} priority"}), 409
            # Update priority in YAML
            with open(yaml_path, "r") as f:
                raw = yaml.safe_load(f)
            for entry in raw.get("companies", []):
                if entry.get("tase_company_id") == issuer_no:
                    entry["priority"] = priority
                    break
            with open(yaml_path, "w") as f:
                yaml.dump(raw, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            logger.info(f"Updated priority for {c.slug} to {priority}")
            return jsonify({"slug": c.slug, "priority": priority, "updated": True}), 200

    slug = _generate_slug(name)
    # Ensure slug uniqueness
    if slug in existing:
        slug = slug + "-" + issuer_no

    tase_sector = data.get("sector", "")
    sector = _map_tase_sector(tase_sector)
    website = data.get("website", "").strip() or None

    new_entry = {
        "slug": slug,
        "name": name,
        "company_type": "tase_traded",
        "tase_company_id": issuer_no,
        "priority": priority,
        "sector": sector,
        "reporting_currency": "ILS",
    }
    if website:
        new_entry["website"] = website

    # Append to companies.yaml
    with open(yaml_path, "r") as f:
        raw = yaml.safe_load(f)
    raw.setdefault("companies", []).append(new_entry)
    with open(yaml_path, "w") as f:
        yaml.dump(raw, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info(f"Added TASE company: {slug} (issuer {issuer_no})")
    return jsonify(new_entry), 201


@app.route("/api/tase-companies/remove", methods=["POST"])
def api_tase_remove():
    """Remove a company from high priority (delete from companies.yaml)."""
    data = request.get_json(silent=True) or {}
    issuer_no = data.get("issuer_no", "").strip()
    if not issuer_no:
        return jsonify({"error": "issuer_no is required"}), 400

    yaml_path = _find_project_root() / "config" / "companies.yaml"
    with open(yaml_path, "r") as f:
        raw = yaml.safe_load(f)

    companies_list = raw.get("companies", [])
    original_len = len(companies_list)
    raw["companies"] = [e for e in companies_list if str(e.get("tase_company_id")) != str(issuer_no)]

    if len(raw["companies"]) == original_len:
        return jsonify({"error": "Company not found in config"}), 404

    with open(yaml_path, "w") as f:
        yaml.dump(raw, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info(f"Removed company with issuer {issuer_no} from companies.yaml")
    return jsonify({"removed": issuer_no}), 200


@app.route("/api/company/<slug>")
def api_company_detail(slug: str):
    """Get detailed company data."""
    companies = load_companies()
    if slug not in companies:
        return jsonify({"error": "Company not found"}), 404

    company = companies[slug]
    fm = FileManager(slug)
    meta = fm.load_meta()
    financials = fm.load_financials()
    kpis = fm.load_kpis()
    memo = fm.load_memo()

    return jsonify({
        "company": company.model_dump(mode="json"),
        "meta": meta,
        "financials": [p.model_dump(mode="json") for p in financials],
        "kpis": kpis.model_dump(mode="json") if kpis else None,
        "memo": memo.model_dump(mode="json") if memo else None,
    })


@app.route("/api/company/<slug>/run", methods=["POST"])
def api_run_pipeline(slug: str):
    """Trigger a pipeline run for a company (runs in background thread)."""
    data = request.get_json(silent=True) or {}
    provider_override = data.get("provider")
    steps_str = data.get("steps", "")
    requested_steps = [s.strip() for s in steps_str.split(",") if s.strip()] if steps_str else None

    def _run_in_background():
        from ..pipeline.runner import run_company
        try:
            asyncio.run(run_company(
                slug=slug,
                years_back=data.get("years_back", 5),
                provider_override=provider_override,
                requested_steps=requested_steps,
            ))
        except Exception as e:
            logger.error(f"Background pipeline run failed for {slug}: {e}")

    thread = threading.Thread(target=_run_in_background, daemon=True, name=f"pipeline-{slug}")
    thread.start()

    return jsonify({
        "status": "started",
        "slug": slug,
        "provider": provider_override,
        "steps": requested_steps,
    })


@app.route("/api/providers")
def api_providers():
    """List AI providers with status."""
    from ..ai.registry import ProviderRegistry
    config = load_providers_config()
    registry = ProviderRegistry(config)

    result = []
    all_providers = config.get("providers", {})
    health = registry.health_check_all()

    for name, cfg in all_providers.items():
        enabled = cfg.get("enabled", True)
        available = registry.has(name)
        result.append({
            "name": name,
            "model": cfg.get("model", "?"),
            "type": cfg.get("type", name),
            "enabled": enabled,
            "available": available,
            "healthy": health.get(name, False) if available else False,
        })

    return jsonify(result)


@app.route("/api/providers/routing")
def api_providers_routing():
    """Get the task routing configuration."""
    config = load_providers_config()
    routing = config.get("routing", {})
    return jsonify(routing)


@app.route("/api/progress")
def api_progress():
    """Get active pipeline progress from ProgressTracker (returns dict)."""
    try:
        from ..progress import ProgressTracker
        trackers = ProgressTracker.get_active()
        return jsonify(trackers)
    except ImportError:
        return jsonify({})


@app.route("/api/progress/<slug>")
def api_progress_detail(slug: str):
    """Get progress for a specific company."""
    try:
        from ..progress import ProgressTracker
        tracker = ProgressTracker.get_tracker(slug)
        if tracker:
            return jsonify(tracker)
        return jsonify({"error": "No active tracker"}), 404
    except ImportError:
        return jsonify({"error": "Progress module not available"}), 500


@app.route("/api/events")
def api_events():
    """Get recent pipeline events."""
    try:
        from ..progress import EventBus
        bus = EventBus.instance()
        slug = request.args.get("slug")
        limit = int(request.args.get("limit", 50))
        events = bus.recent_events(limit=limit, company_slug=slug)
        return jsonify([e.to_dict() for e in events])
    except ImportError:
        return jsonify([])


@app.route("/api/scheduler/status")
def api_scheduler_status():
    """Get scheduler status."""
    try:
        from ..scheduler import PipelineScheduler
        sched = PipelineScheduler()
        return jsonify(sched.get_status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Cross-Process Live Polling Thread
# ---------------------------------------------------------------------------
def _start_ipc_polling_thread():
    """Poll the file-based IPC progress states to notify WS clients."""
    if not HAS_SOCKETIO:
        return

    def poll_loop():
        try:
            from ..progress import ProgressTracker
        except ImportError:
            return
            
        last_states = {}
        
        while True:
            try:
                # Read disk + memory states
                current = ProgressTracker.get_active()
                
                for slug, tracker_data in current.items():
                    # Simplified change detection
                    curr_str = json.dumps(tracker_data, sort_keys=True)
                    prev_str = last_states.get(slug)
                    
                    if curr_str != prev_str:
                        last_states[slug] = curr_str
                        
                        # Emit synthetic progress update to clients
                        socketio.emit("pipeline_event", {
                            "event_type": "progress.update",
                            "company_slug": slug,
                            "step_name": tracker_data.get("current_step", ""),
                            "message": tracker_data.get("current_step", "Running..."),
                            "data": {
                                "progress_pct": tracker_data.get("progress_pct", 0),
                                "current_step": tracker_data.get("current_step", ""),
                            },
                        })
                        
                        # If completed/failed, emit synthetic completion to trigger reload
                        status = tracker_data.get("status")
                        if status in ("completed", "failed") and prev_str:
                            socketio.emit("pipeline_event", {
                                "event_type": f"pipeline.{status}",
                                "company_slug": slug,
                                "message": f"Pipeline {status}",
                                "data": {},
                            })
                            
            except Exception as e:
                logger.debug(f"IPC poll error: {e}")
                
            time.sleep(1.0)  # Poll once per second

    t = threading.Thread(target=poll_loop, daemon=True, name="ipc-poller")
    t.start()


# ---------------------------------------------------------------------------
# WebSocket events (if SocketIO available)
# ---------------------------------------------------------------------------

if HAS_SOCKETIO:
    @socketio.on("connect")
    def handle_connect():
        logger.debug("WebSocket client connected")

    @socketio.on("disconnect")
    def handle_disconnect():
        logger.debug("WebSocket client disconnected")

    @socketio.on("request_progress")
    def handle_progress_request(data):
        """Client requesting progress update for a company."""
        try:
            from ..progress import ProgressTracker
            slug = data.get("slug")
            if slug:
                tracker = ProgressTracker.get_tracker(slug)
                if tracker:
                    emit("progress_update", tracker.to_dict())
        except ImportError:
            pass


# ---------------------------------------------------------------------------
# App startup
# ---------------------------------------------------------------------------

def run_dashboard(host: str = "0.0.0.0", port: int = 8050, debug: bool = False):
    """Start the web dashboard."""
    _setup_event_bridge()
    _start_ipc_polling_thread()

    logger.info(f"Starting dashboard on {host}:{port}")
    logger.info(f"WebSocket: {'enabled' if HAS_SOCKETIO else 'disabled'}")

    if HAS_SOCKETIO:
        socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
    else:
        app.run(host=host, port=port, debug=debug)
