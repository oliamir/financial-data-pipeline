"""Web dashboard — Flask app with REST API, WebSocket, and real-time updates.

Provides a web interface for monitoring pipeline runs, viewing
company data, managing providers, and triggering pipeline execution
with real-time progress via WebSocket (Flask-SocketIO).
"""

import json
import asyncio
import threading
from pathlib import Path
from flask import Flask, jsonify, render_template_string, request

from ..config.loader import load_companies, load_providers_config
from ..storage.file_manager import FileManager
from ..utils.logging import get_logger

logger = get_logger(__name__)

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
# EventBus → WebSocket bridge
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
        logger.info("EventBus → WebSocket bridge established")
    except ImportError:
        logger.debug("Progress module not available, skipping event bridge")


# ---------------------------------------------------------------------------
# Dashboard HTML template (enhanced with WebSocket + provider selector)
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Finance Pipeline Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: #0f172a; color: #e2e8f0; }
        .header { background: linear-gradient(135deg, #1e3a5f, #0f172a);
                   padding: 2rem; border-bottom: 1px solid #334155;
                   display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 1.8rem; color: #60a5fa; }
        .header p { color: #94a3b8; margin-top: 0.5rem; }
        .header-right { display: flex; gap: 1rem; align-items: center; }
        .container { max-width: 1400px; margin: 0 auto; padding: 2rem; }

        /* Tabs */
        .tabs { display: flex; gap: 0; margin-bottom: 2rem; border-bottom: 1px solid #334155; }
        .tab { padding: 0.75rem 1.5rem; cursor: pointer; color: #94a3b8;
               border-bottom: 2px solid transparent; transition: all 0.2s; }
        .tab:hover { color: #e2e8f0; }
        .tab.active { color: #60a5fa; border-bottom-color: #60a5fa; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        /* Cards */
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
                 gap: 1.5rem; }
        .card { background: #1e293b; border-radius: 12px; padding: 1.5rem;
                 border: 1px solid #334155; transition: transform 0.2s; }
        .card:hover { transform: translateY(-2px); border-color: #60a5fa; }
        .card h3 { color: #60a5fa; font-size: 1.1rem; margin-bottom: 0.5rem; }
        .card .slug { color: #94a3b8; font-size: 0.85rem; }
        .stat { display: flex; justify-content: space-between; padding: 0.5rem 0;
                 border-bottom: 1px solid #334155; }
        .stat:last-child { border-bottom: none; }
        .stat-label { color: #94a3b8; }
        .stat-value { color: #e2e8f0; font-weight: 600; }

        /* Badges */
        .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px;
                  font-size: 0.75rem; font-weight: 600; }
        .badge-high { background: #dc2626; color: white; }
        .badge-low { background: #334155; color: #94a3b8; }
        .badge-success { background: #16a34a; color: white; }
        .badge-running { background: #f59e0b; color: #1e293b; }
        .badge-failed { background: #dc2626; color: white; }

        /* Controls */
        .btn { background: #3b82f6; color: white; border: none; padding: 0.5rem 1rem;
                border-radius: 6px; cursor: pointer; font-size: 0.85rem; transition: 0.2s; }
        .btn:hover { background: #2563eb; }
        .btn-sm { padding: 0.3rem 0.6rem; font-size: 0.75rem; }
        .btn-danger { background: #dc2626; }
        .btn-danger:hover { background: #b91c1c; }
        .btn-outline { background: transparent; border: 1px solid #3b82f6; }
        .btn-outline:hover { background: #3b82f6; }

        select { background: #1e293b; color: #e2e8f0; border: 1px solid #334155;
                 border-radius: 6px; padding: 0.5rem; font-size: 0.85rem; }

        /* Provider panel */
        .provider-panel { background: #1e293b; border-radius: 12px; padding: 1.5rem;
                          border: 1px solid #334155; margin-bottom: 1.5rem; }
        .provider-row { display: flex; align-items: center; gap: 1rem;
                        padding: 0.5rem 0; border-bottom: 1px solid #334155; }
        .provider-row:last-child { border-bottom: none; }
        .provider-name { font-weight: 600; min-width: 100px; }
        .provider-model { color: #94a3b8; flex: 1; }
        .provider-status { min-width: 60px; text-align: right; }

        /* Progress bar */
        .progress { height: 4px; background: #334155; border-radius: 2px; overflow: hidden; }
        .progress-bar { height: 100%; background: #3b82f6; transition: width 0.5s ease; }

        /* Event log */
        .event-log { background: #0f172a; border: 1px solid #334155; border-radius: 8px;
                     padding: 1rem; max-height: 300px; overflow-y: auto; font-family: monospace;
                     font-size: 0.8rem; }
        .event-item { padding: 0.25rem 0; border-bottom: 1px solid #1e293b; }
        .event-time { color: #64748b; }
        .event-type { color: #60a5fa; font-weight: 600; margin: 0 0.5rem; }
        .event-msg { color: #e2e8f0; }

        /* Connection indicator */
        .ws-indicator { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
        .ws-connected { background: #16a34a; }
        .ws-disconnected { background: #dc2626; }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>Finance Pipeline Dashboard</h1>
            <p>Financial Data Pipeline v3 — Real-Time Monitor</p>
        </div>
        <div class="header-right">
            <span class="ws-indicator" id="wsIndicator"></span>
            <span id="wsStatus" style="color: #94a3b8; font-size: 0.85rem;"></span>
            <button class="btn" onclick="location.reload()">Refresh</button>
        </div>
    </div>
    <div class="container">
        <div class="tabs">
            <div class="tab active" onclick="showTab('companies')">Companies</div>
            <div class="tab" onclick="showTab('providers')">Providers</div>
            <div class="tab" onclick="showTab('events')">Live Events</div>
        </div>

        <!-- Companies Tab -->
        <div class="tab-content active" id="tab-companies">
            <div class="grid" id="companies"></div>
        </div>

        <!-- Providers Tab -->
        <div class="tab-content" id="tab-providers">
            <div class="provider-panel" id="providers"></div>
        </div>

        <!-- Events Tab -->
        <div class="tab-content" id="tab-events">
            <div class="event-log" id="eventLog">
                <div style="color: #64748b;">Waiting for events...</div>
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js"></script>
    <script>
        // -- Tab switching --
        function showTab(name) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + name).classList.add('active');
        }

        // -- Load companies --
        function loadCompanies() {
            fetch('/api/companies')
                .then(r => r.json())
                .then(data => {
                    const grid = document.getElementById('companies');
                    grid.innerHTML = '';
                    data.forEach(c => {
                        const card = document.createElement('div');
                        card.className = 'card';
                        card.innerHTML = `
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <div>
                                    <h3>${c.name}</h3>
                                    <span class="slug">${c.slug}</span>
                                </div>
                                <span class="badge badge-${c.priority}">${c.priority}</span>
                            </div>
                            <div style="margin-top: 1rem">
                                <div class="stat">
                                    <span class="stat-label">Reports</span>
                                    <span class="stat-value">${c.reports_count}</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-label">Periods</span>
                                    <span class="stat-value">${c.periods}</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-label">Financials</span>
                                    <span class="stat-value">${c.has_financials ? '&#10003;' : '&#10007;'}</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-label">Memo</span>
                                    <span class="stat-value">${c.has_memo ? '&#10003;' : '&#10007;'}</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-label">Last Scrape</span>
                                    <span class="stat-value">${c.last_scrape ? new Date(c.last_scrape).toLocaleDateString() : 'Never'}</span>
                                </div>
                            </div>
                            <div style="margin-top: 1rem; display: flex; gap: 0.5rem;">
                                <button class="btn btn-sm" onclick="runPipeline('${c.slug}')">Run</button>
                                <select id="provider-${c.slug}" class="btn-sm" style="font-size: 0.75rem;">
                                    <option value="">auto</option>
                                </select>
                                <select id="step-${c.slug}" class="btn-sm" style="font-size: 0.75rem;">
                                    <option value="">all steps</option>
                                    <option value="download">download</option>
                                    <option value="parse">parse</option>
                                    <option value="model">model</option>
                                    <option value="memo">memo</option>
                                </select>
                            </div>
                            <div class="progress" style="margin-top: 0.5rem;" id="progress-${c.slug}">
                                <div class="progress-bar" style="width: 0%"></div>
                            </div>
                        `;
                        grid.appendChild(card);
                    });
                    loadProviderOptions();
                });
        }

        // -- Load providers --
        function loadProviders() {
            fetch('/api/providers')
                .then(r => r.json())
                .then(data => {
                    const panel = document.getElementById('providers');
                    panel.innerHTML = '<h3 style="margin-bottom: 1rem; color: #60a5fa;">AI Providers</h3>';
                    data.forEach(p => {
                        const row = document.createElement('div');
                        row.className = 'provider-row';
                        const statusClass = p.available ? 'badge-success' : 'badge-failed';
                        row.innerHTML = `
                            <span class="provider-name">${p.name}</span>
                            <span class="provider-model">${p.model}</span>
                            <span class="provider-status">
                                <span class="badge ${statusClass}">${p.available ? 'active' : 'off'}</span>
                            </span>
                        `;
                        panel.appendChild(row);
                    });

                    // Routing table
                    fetch('/api/providers/routing')
                        .then(r => r.json())
                        .then(routing => {
                            const routeDiv = document.createElement('div');
                            routeDiv.style.marginTop = '1.5rem';
                            routeDiv.innerHTML = '<h3 style="margin-bottom: 1rem; color: #60a5fa;">Task Routing</h3>';
                            Object.entries(routing).forEach(([task, route]) => {
                                const row = document.createElement('div');
                                row.className = 'provider-row';
                                row.innerHTML = `
                                    <span class="provider-name">${task}</span>
                                    <span class="provider-model">${route.primary} &#8594; ${(route.fallback || []).join(', ') || 'none'}</span>
                                `;
                                routeDiv.appendChild(row);
                            });
                            panel.appendChild(routeDiv);
                        });
                });
        }

        function loadProviderOptions() {
            fetch('/api/providers')
                .then(r => r.json())
                .then(providers => {
                    document.querySelectorAll('select[id^="provider-"]').forEach(sel => {
                        providers.forEach(p => {
                            if (p.available) {
                                const opt = document.createElement('option');
                                opt.value = p.name;
                                opt.textContent = p.name;
                                sel.appendChild(opt);
                            }
                        });
                    });
                });
        }

        // -- Run pipeline --
        function runPipeline(slug) {
            const providerSel = document.getElementById('provider-' + slug);
            const stepSel = document.getElementById('step-' + slug);
            const provider = providerSel ? providerSel.value : '';
            const step = stepSel ? stepSel.value : '';

            const body = {};
            if (provider) body.provider = provider;
            if (step) body.steps = step;

            fetch(`/api/company/${slug}/run`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body),
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    alert('Error: ' + data.error);
                } else {
                    addEvent('pipeline.started', slug, 'Pipeline started');
                }
            })
            .catch(err => alert('Request failed: ' + err));
        }

        // -- WebSocket --
        let socket = null;
        function connectWebSocket() {
            const indicator = document.getElementById('wsIndicator');
            const status = document.getElementById('wsStatus');

            if (typeof io === 'undefined') {
                indicator.className = 'ws-indicator ws-disconnected';
                status.textContent = 'WebSocket unavailable';
                return;
            }

            socket = io();

            socket.on('connect', () => {
                indicator.className = 'ws-indicator ws-connected';
                status.textContent = 'Connected';
            });

            socket.on('disconnect', () => {
                indicator.className = 'ws-indicator ws-disconnected';
                status.textContent = 'Disconnected';
            });

            socket.on('pipeline_event', (event) => {
                addEvent(event.event_type, event.company_slug, event.message);

                // Update progress bar if available
                if (event.company_slug) {
                    const progressEl = document.getElementById('progress-' + event.company_slug);
                    if (progressEl && event.data && event.data.progress_pct) {
                        progressEl.querySelector('.progress-bar').style.width = event.data.progress_pct + '%';
                    }
                }
            });
        }

        function addEvent(type, slug, message) {
            const log = document.getElementById('eventLog');
            const first = log.querySelector('div:first-child');
            if (first && first.textContent.includes('Waiting')) first.remove();

            const item = document.createElement('div');
            item.className = 'event-item';
            const time = new Date().toLocaleTimeString();
            item.innerHTML = `
                <span class="event-time">${time}</span>
                <span class="event-type">${type}</span>
                <span style="color: #94a3b8;">[${slug}]</span>
                <span class="event-msg">${message}</span>
            `;
            log.prepend(item);

            // Limit to 100 events
            while (log.children.length > 100) log.lastChild.remove();
        }

        // -- Init --
        loadCompanies();
        loadProviders();
        connectWebSocket();
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
    """Get active pipeline progress from ProgressTracker."""
    try:
        from ..progress import ProgressTracker
        trackers = ProgressTracker.get_active()
        return jsonify({
            slug: tracker.to_dict()
            for slug, tracker in trackers.items()
        })
    except ImportError:
        return jsonify({})


@app.route("/api/progress/<slug>")
def api_progress_detail(slug: str):
    """Get progress for a specific company."""
    try:
        from ..progress import ProgressTracker
        tracker = ProgressTracker.get_tracker(slug)
        if tracker:
            return jsonify(tracker.to_dict())
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

    logger.info(f"Starting dashboard on {host}:{port}")
    logger.info(f"WebSocket: {'enabled' if HAS_SOCKETIO else 'disabled'}")

    if HAS_SOCKETIO:
        socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
    else:
        app.run(host=host, port=port, debug=debug)
