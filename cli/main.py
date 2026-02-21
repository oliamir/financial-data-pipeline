#!/usr/bin/env python3
"""Financial Data Pipeline CLI (Typer).

Usage:
    python -m cli.main run <SLUG> [--years N] [--skip-scrape] [--skip-analyze]
    python -m cli.main run-all [--tier TIER] [--years N]
    python -m cli.main status [SLUG] [--failed]
    python -m cli.main list [--tier TIER]
    python -m cli.main validate [SLUG]
    python -m cli.main provider [ACTION]
    python -m cli.main company <ACTION> [SLUG] [--name NAME] [--tase-id ID]
    python -m cli.main dashboard [SLUG] [--watch N] [--tier TIER]
"""

import sys
import os
from typing import Optional

import typer

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

app = typer.Typer(
    name="finance",
    help="Financial data pipeline -- TASE company analysis",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

@app.command(name="run")
def run(
    slug: str = typer.Argument(..., help="Company slug to process"),
    years: int = typer.Option(5, "--years", "-y", help="Years of history to fetch"),
    skip_scrape: bool = typer.Option(False, "--skip-scrape", help="Skip scraping/download"),
    skip_analyze: bool = typer.Option(False, "--skip-analyze", help="Skip AI analysis"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Force specific AI provider"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Log actions without executing"),
    initial_research: bool = typer.Option(False, "--initial-research", help="Run deep strategic research prompts (Gemini)"),
    step: Optional[str] = typer.Option(None, "--step", "-s", help="Run specific steps only (comma-separated: download,parse,model,memo)"),
    test_mode: bool = typer.Option(False, "--test-mode", help="E2E test: 1 year download+model, full memo"),
    reprocess: bool = typer.Option(False, "--reprocess", help="Force re-extraction of already processed files"),
) -> None:
    """Run the pipeline for a specific company."""
    from cli.commands.run import run_pipeline

    # Test mode overrides
    if test_mode:
        years = 1
        step = "download,parse,model,memo"

    run_pipeline(
        slug=slug,
        years_back=years,
        skip_scrape=skip_scrape,
        skip_analyze=skip_analyze,
        provider=provider,
        dry_run=dry_run,
        initial_research=initial_research,
        step=step,
        test_mode=test_mode,
        reprocess=reprocess,
    )


# ---------------------------------------------------------------------------
# run-all
# ---------------------------------------------------------------------------

@app.command(name="run-all")
def run_all(
    tier: Optional[str] = typer.Option(None, "--tier", "-t", help="Filter by priority: high or low"),
    years: int = typer.Option(5, "--years", "-y", help="Years of history"),
) -> None:
    """Run the pipeline for all companies (or by tier)."""
    from cli.commands.run import run_all_companies
    run_all_companies(priority=tier, years_back=years)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

@app.command(name="status")
def show_status(
    slug: Optional[str] = typer.Argument(None, help="Company slug"),
    failed: bool = typer.Option(False, "--failed", help="Show only failed companies"),
) -> None:
    """Show pipeline status for companies."""
    from src.registry.company import CompanyRegistry
    from src.storage.file_manager import FileManager

    registry = CompanyRegistry()
    companies = registry.all()

    if slug:
        companies = [registry.get(slug)]

    print(f"\n{'COMPANY':<30} | {'PRIORITY':<8} | {'LAST SCRAPE':<20} | {'REPORTS':<8} | {'METRICS':<8} | {'MEMO':<6}")
    print("-" * 95)

    for c in companies:
        fm = FileManager(c.slug)
        meta = fm.load_meta()
        financials = fm.load_financials()
        memo = fm.load_memo()

        last_scrape = meta.get("last_scrape", "Never")
        if last_scrape and last_scrape != "Never":
            last_scrape = last_scrape[:16]

        reports = meta.get("reports_downloaded", 0)
        has_memo = "YES" if memo else "NO"

        if failed and meta.get("last_scrape_status") != "failed":
            continue

        print(f"{c.name:<30} | {c.priority:<8} | {last_scrape:<20} | {reports:<8} | {len(financials):<8} | {has_memo:<6}")

    print()


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

@app.command(name="list")
def list_companies(
    tier: Optional[str] = typer.Option(None, "--tier", "-t", help="Filter by priority: high or low"),
) -> None:
    """List all registered companies."""
    from src.registry.company import CompanyRegistry

    registry = CompanyRegistry()
    companies = registry.all()

    if tier:
        companies = registry.list_by_priority(tier)

    print(f"\n{'SLUG':<15} | {'NAME':<35} | {'PRIORITY':<8} | {'TASE ID':<10} | {'CURRENCY':<8}")
    print("-" * 90)

    for c in companies:
        print(f"{c.slug:<15} | {c.name:<35} | {c.priority:<8} | {(c.tase_id or '-'):<10} | {c.reporting_currency:<8}")

    print(f"\nTotal: {len(companies)} companies\n")


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

@app.command(name="validate")
def validate(
    slug: Optional[str] = typer.Argument(None, help="Company slug (all if omitted)"),
) -> None:
    """Validate extracted data quality."""
    from cli.commands.validate import run_validate
    run_validate(slug=slug)


# ---------------------------------------------------------------------------
# provider
# ---------------------------------------------------------------------------

@app.command(name="provider")
def provider_cmd(
    action: str = typer.Argument("status", help="Action: status or models"),
) -> None:
    """Check AI provider health and list available models."""
    from cli.commands.provider import run_provider_status

    if action in ("status", "models"):
        run_provider_status()
    else:
        typer.echo(f"Unknown action: {action}. Use: status, models")


# ---------------------------------------------------------------------------
# company
# ---------------------------------------------------------------------------

@app.command(name="company")
def company_cmd(
    action: str = typer.Argument(..., help="Action: add, remove, or list"),
    slug: Optional[str] = typer.Argument(None, help="Company slug"),
    name: Optional[str] = typer.Option(None, "--name", help="Company name"),
    tase_id: Optional[str] = typer.Option(None, "--tase-id", help="TASE ID"),
    sector: str = typer.Option("other", "--sector", help="Sector"),
    priority: str = typer.Option("low", "--priority", help="Priority: high or low"),
    company_type: str = typer.Option("tase_traded", "--type", help="Type: us_traded, tase_traded, private"),
    us_ticker: Optional[str] = typer.Option(None, "--us-ticker", help="US ticker symbol"),
) -> None:
    """Manage the company registry (add, remove, list)."""
    from cli.commands.company import run_company_add, run_company_remove, run_company_list

    if action == "list":
        run_company_list()
    elif action == "add":
        if not all([slug, name, tase_id]):
            typer.echo("Error: slug, --name, and --tase-id are required for 'add'")
            raise typer.Exit(1)
        run_company_add(slug, name, tase_id, sector, priority, company_type, us_ticker)
    elif action == "remove":
        if not slug:
            typer.echo("Error: slug is required for 'remove'")
            raise typer.Exit(1)
        run_company_remove(slug)
    else:
        typer.echo(f"Unknown action: {action}. Use: add, remove, list")


# ---------------------------------------------------------------------------
# dashboard
# ---------------------------------------------------------------------------

@app.command(name="dashboard")
def dashboard(
    company: Optional[str] = typer.Argument(None, help="Filter to one company slug"),
    watch: Optional[int] = typer.Option(None, "--watch", "-w", help="Auto-refresh interval in seconds"),
    tier: Optional[str] = typer.Option(None, "--tier", help="Filter by priority: high or low"),
) -> None:
    """Rich terminal dashboard showing pipeline progress."""
    from cli.dashboard import run_dashboard
    run_dashboard(slug=company, priority=tier, watch=watch)


if __name__ == "__main__":
    app()
