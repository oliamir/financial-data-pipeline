"""Web dashboard — Flask app with REST API and real-time updates.

Provides a web interface for monitoring pipeline runs, viewing
company data, and triggering pipeline execution.
"""

import json
from pathlib import Path
from flask import Flask, jsonify, render_template_string, request

from ..config.loader import load_companies
from ..storage.file_manager import FileManager
from ..utils.logging import get_logger

logger = get_logger(__name__)

app = Flask(__name__)

# Minimal dashboard HTML template
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
                   padding: 2rem; border-bottom: 1px solid #334155; }
        .header h1 { font-size: 1.8rem; color: #60a5fa; }
        .header p { color: #94a3b8; margin-top: 0.5rem; }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
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
        .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px;
                  font-size: 0.75rem; font-weight: 600; }
        .badge-high { background: #dc2626; color: white; }
        .badge-low { background: #334155; color: #94a3b8; }
        .badge-success { background: #16a34a; color: white; }
        .badge-missing { background: #dc2626; color: white; }
        .actions { margin-top: 1rem; display: flex; gap: 0.5rem; }
        .btn { background: #3b82f6; color: white; border: none; padding: 0.5rem 1rem;
                border-radius: 6px; cursor: pointer; font-size: 0.85rem; }
        .btn:hover { background: #2563eb; }
        .refresh-bar { text-align: right; margin-bottom: 1rem; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Finance Pipeline Dashboard</h1>
        <p>Financial Data Pipeline v3 — Company Analysis Monitor</p>
    </div>
    <div class="container">
        <div class="refresh-bar">
            <button class="btn" onclick="location.reload()">🔄 Refresh</button>
        </div>
        <div class="grid" id="companies"></div>
    </div>
    <script>
        fetch('/api/companies')
            .then(r => r.json())
            .then(data => {
                const grid = document.getElementById('companies');
                data.forEach(c => {
                    const card = document.createElement('div');
                    card.className = 'card';
                    card.innerHTML = `
                        <h3>${c.name}</h3>
                        <span class="slug">${c.slug}</span>
                        <span class="badge badge-${c.priority}">${c.priority}</span>
                        <div style="margin-top: 1rem">
                            <div class="stat">
                                <span class="stat-label">Reports</span>
                                <span class="stat-value">${c.reports_count}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Last Scrape</span>
                                <span class="stat-value">${c.last_scrape || 'Never'}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Financials</span>
                                <span class="stat-value">${c.has_financials ? '✅' : '❌'}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Memo</span>
                                <span class="stat-value">${c.has_memo ? '✅' : '❌'}</span>
                            </div>
                        </div>
                    `;
                    grid.appendChild(card);
                });
            });
    </script>
</body>
</html>
"""


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
    """Trigger a pipeline run for a company."""
    import asyncio
    from ..pipeline.runner import run_company

    try:
        job = asyncio.run(run_company(slug=slug, years_back=5))
        return jsonify({
            "status": job.status,
            "steps": len(job.steps),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def run_dashboard(host: str = "0.0.0.0", port: int = 8050, debug: bool = False):
    """Start the web dashboard."""
    logger.info(f"Starting dashboard on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
