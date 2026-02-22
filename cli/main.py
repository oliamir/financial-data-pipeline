"""Finance CLI -- Typer application entry point.

Usage:
    finance list [--type TYPE] [--priority PRIORITY]
    finance status [SLUG] [--failed]
    finance run <SLUG> [--step STEPS] [--test-mode] [--reprocess] [--provider P]
    finance run-all [--priority PRIORITY] [--years N]
    finance build-model <SLUG>
    finance provider status|models
    finance validate [SLUG]
    finance company add|edit|remove
    finance web [--port PORT]
    finance scheduler start|status|stop
    finance dashboard [--watch N]
    finance universe [COMMAND]
"""

import typer
from typing import Optional, List

app = typer.Typer(
    name="finance",
    help="Financial data pipeline -- TASE company analysis",
    no_args_is_help=True,
)


@app.command()
def list_companies(
    company_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by type: us_traded, tase_traded, private"),
    priority: Optional[str] = typer.Option(None, "--priority", "-p", help="Filter by priority: high, low"),
) -> None:
    """List all registered companies."""
    from cli.commands.list_cmd import run_list
    run_list(company_type=company_type, priority=priority)


@app.command(name="status")
def show_status(
    slug: Optional[str] = typer.Argument(None, help="Company slug"),
    failed: bool = typer.Option(False, "--failed", help="Show only failed companies"),
) -> None:
    """Show pipeline status for companies."""
    from cli.commands.status import run_status
    run_status(slug=slug, failed_only=failed)


@app.command(name="run")
def run(
    slug: str = typer.Argument(..., help="Company slug to process"),
    years: int = typer.Option(5, "--years", "-y", help="Years of history to fetch"),
    step: Optional[str] = typer.Option(None, "--step", "-s", help="Comma-separated steps: download,parse,model,memo,initial_research"),
    test_mode: bool = typer.Option(False, "--test-mode", help="E2E test: 1-year download + model + full web-research memo"),
    reprocess: bool = typer.Option(False, "--reprocess", help="Re-analyze already-processed files"),
    skip_scrape: bool = typer.Option(False, "--skip-scrape", help="Skip scraping/download"),
    skip_analyze: bool = typer.Option(False, "--skip-analyze", help="Skip AI analysis"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Force specific AI provider"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Log actions without executing"),
    initial_research: bool = typer.Option(False, "--initial-research", help="Run deep strategic research prompts (Gemini)"),
) -> None:
    """Run the pipeline for a specific company.

    Examples:
        finance run sofwave                          # Full pipeline (5 years)
        finance run sofwave --step download           # Download only
        finance run sofwave --step parse,model        # Parse + build Excel model
        finance run sofwave --step memo               # Memo only (web research)
        finance run sofwave --test-mode               # Quick E2E test (1 year)
        finance run sofwave --reprocess               # Re-analyze all files
        finance run sofwave --provider gemini         # Force Gemini provider
    """
    from cli.commands.run import run_pipeline

    # Test mode: 1-year download + model + full-research memo
    if test_mode:
        years = 1
        step = "download,parse,model,memo"
        initial_research = True

    # Parse step list
    requested_steps = None
    if step:
        requested_steps = [s.strip() for s in step.split(",") if s.strip()]

    run_pipeline(
        slug=slug,
        years_back=years,
        skip_scrape=skip_scrape,
        skip_analyze=skip_analyze,
        provider=provider,
        dry_run=dry_run,
        initial_research=initial_research,
        requested_steps=requested_steps,
        reprocess=reprocess,
    )


@app.command(name="run-all")
def run_all(
    priority: Optional[str] = typer.Option(None, "--priority", "-p", help="Filter by priority tier"),
    years: int = typer.Option(5, "--years", "-y", help="Years of history"),
) -> None:
    """Run the pipeline for all companies."""
    from cli.commands.run import run_all_companies
    run_all_companies(priority=priority, years_back=years)


@app.command(name="build-model")
def build_model(
    slug: str = typer.Argument(..., help="Company slug"),
) -> None:
    """Build Excel financial model for a company."""
    from src.excel import ExcelModelBuilder

    builder = ExcelModelBuilder(slug)
    path = builder.build()
    typer.echo(f"Model saved: {path}")


# ---------------------------------------------------------------------------
# Provider commands
# ---------------------------------------------------------------------------

provider_app = typer.Typer(help="AI provider management.")
app.add_typer(provider_app, name="provider")


@provider_app.command(name="status")
def provider_status() -> None:
    """Show AI provider status and health checks."""
    from rich.console import Console
    from rich.table import Table
    from src.ai.registry import ProviderRegistry
    from src.config.loader import load_providers_config

    console = Console()
    config = load_providers_config()
    registry = ProviderRegistry(config)

    table = Table(title="AI Provider Status")
    table.add_column("Provider", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Model")
    table.add_column("Health")

    # Show all configured providers
    all_providers = config.get("providers", {})
    health = registry.health_check_all()

    for name, cfg in all_providers.items():
        enabled = cfg.get("enabled", True)
        available = registry.has(name)
        model = cfg.get("model", "?")

        if not enabled:
            status = "[dim]disabled[/dim]"
            health_str = "-"
        elif available:
            status = "[green]active[/green]"
            is_healthy = health.get(name, False)
            health_str = "[green]OK[/green]" if is_healthy else "[red]FAIL[/red]"
        else:
            status = "[red]unavailable[/red]"
            health_str = "[red]no API key[/red]"

        table.add_row(name, status, model, health_str)

    console.print(table)

    # Show routing table
    routing = config.get("routing", {})
    if routing:
        console.print("\n[bold]Task Routing:[/bold]")
        for task, route in routing.items():
            primary = route.get("primary", "?")
            fallback = route.get("fallback", [])
            console.print(f"  {task}: {primary} → {', '.join(fallback) if fallback else 'none'}")


@provider_app.command(name="models")
def provider_models() -> None:
    """List available models (including Ollama auto-detect)."""
    from rich.console import Console
    from rich.table import Table
    from src.ai.registry import ProviderRegistry

    console = Console()
    registry = ProviderRegistry()

    table = Table(title="Available Models")
    table.add_column("Provider", style="cyan")
    table.add_column("Model")
    table.add_column("Type")

    for name in registry.available():
        provider = registry.get(name)
        model_name = getattr(provider, "model", "unknown")
        provider_type = type(provider).__name__
        table.add_row(name, model_name, provider_type)

    console.print(table)

    # Try to list Ollama models if available
    if registry.has("ollama"):
        try:
            from src.ai.ollama_provider import OllamaProvider
            ollama = registry.get("ollama")
            if isinstance(ollama, OllamaProvider):
                console.print("\n[bold]Ollama Models (auto-detected):[/bold]")
                import requests
                host = getattr(ollama, "host", "http://localhost:11434")
                resp = requests.get(f"{host}/api/tags", timeout=5)
                if resp.ok:
                    models = resp.json().get("models", [])
                    for m in models:
                        size_gb = m.get("size", 0) / 1e9
                        console.print(f"  {m['name']} ({size_gb:.1f} GB)")
                else:
                    console.print("  [red]Could not list models[/red]")
        except Exception as e:
            console.print(f"  [red]Ollama error: {e}[/red]")


# ---------------------------------------------------------------------------
# Validate command
# ---------------------------------------------------------------------------

@app.command(name="validate")
def validate(
    slug: Optional[str] = typer.Argument(None, help="Company slug (or all if omitted)"),
) -> None:
    """Validate pipeline outputs for a company (or all)."""
    from rich.console import Console
    from rich.table import Table
    from src.config.loader import load_companies
    from src.storage.file_manager import FileManager

    console = Console()
    companies = load_companies()

    if slug:
        if slug not in companies:
            console.print(f"[red]Company '{slug}' not found[/red]")
            raise typer.Exit(1)
        slugs = [slug]
    else:
        slugs = list(companies.keys())

    table = Table(title="Validation Results")
    table.add_column("Company", style="cyan")
    table.add_column("Reports", justify="right")
    table.add_column("Processed", justify="right")
    table.add_column("Financials", justify="right")
    table.add_column("KPIs")
    table.add_column("Memo")
    table.add_column("Model")
    table.add_column("Issues")

    for s in slugs:
        fm = FileManager(s)
        meta = fm.load_meta()
        financials = fm.load_financials()
        kpis = fm.load_kpis()
        memo = fm.load_memo()

        reports_dir = fm.paths.reports_dir
        total_reports = len(list(reports_dir.glob("*.pdf"))) if reports_dir.exists() else 0
        processed = len(meta.get("processed_files", []))

        issues = []
        if total_reports > 0 and processed == 0:
            issues.append("no files processed")
        if total_reports > 0 and not financials:
            issues.append("no financials extracted")
        if financials and not kpis:
            issues.append("missing KPIs")
        if total_reports > 0 and not memo:
            issues.append("no memo")
        if not fm.paths.model_xlsx.exists():
            if financials:
                issues.append("no Excel model")

        issue_str = "; ".join(issues) if issues else "[green]OK[/green]"
        kpi_str = "[green]✓[/green]" if kpis else "[red]✗[/red]"
        memo_str = "[green]✓[/green]" if memo else "[red]✗[/red]"
        model_str = "[green]✓[/green]" if fm.paths.model_xlsx.exists() else "[red]✗[/red]"

        table.add_row(
            s, str(total_reports), str(processed),
            str(len(financials)), kpi_str, memo_str, model_str,
            issue_str,
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Company management commands
# ---------------------------------------------------------------------------

company_app = typer.Typer(help="Company management (add/edit/remove).")
app.add_typer(company_app, name="company")


@company_app.command(name="add")
def company_add(
    slug: str = typer.Argument(..., help="Company slug (lowercase, e.g., 'sofwave')"),
    name: str = typer.Option(..., "--name", "-n", help="Company display name"),
    company_type: str = typer.Option("tase_traded", "--type", "-t", help="Type: us_traded, tase_traded, private"),
    sector: str = typer.Option("", "--sector", help="Industry sector"),
    priority: str = typer.Option("low", "--priority", "-p", help="Priority: high, low"),
    tase_id: Optional[str] = typer.Option(None, "--tase-id", help="TASE company ID"),
    ir_url: Optional[str] = typer.Option(None, "--ir-url", help="IR website URL"),
) -> None:
    """Add a new company to the registry."""
    import yaml
    from pathlib import Path
    from rich.console import Console

    console = Console()
    config_path = Path("config/companies.yaml")

    if not config_path.exists():
        console.print("[red]config/companies.yaml not found[/red]")
        raise typer.Exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    companies = config.get("companies", {})
    if slug in companies:
        console.print(f"[red]Company '{slug}' already exists[/red]")
        raise typer.Exit(1)

    new_company = {
        "name": name,
        "company_type": company_type,
        "sector": sector,
        "priority": priority,
    }
    if tase_id:
        new_company["tase_company_id"] = tase_id
    if ir_url:
        new_company["ir_website_url"] = ir_url

    companies[slug] = new_company
    config["companies"] = companies

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    console.print(f"[green]Added company: {name} ({slug})[/green]")


@company_app.command(name="remove")
def company_remove(
    slug: str = typer.Argument(..., help="Company slug to remove"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Remove a company from the registry."""
    import yaml
    from pathlib import Path
    from rich.console import Console

    console = Console()
    config_path = Path("config/companies.yaml")

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    companies = config.get("companies", {})
    if slug not in companies:
        console.print(f"[red]Company '{slug}' not found[/red]")
        raise typer.Exit(1)

    if not confirm:
        confirmed = typer.confirm(f"Remove {companies[slug].get('name', slug)}?")
        if not confirmed:
            raise typer.Abort()

    del companies[slug]
    config["companies"] = companies

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    console.print(f"[green]Removed company: {slug}[/green]")


@company_app.command(name="edit")
def company_edit(
    slug: str = typer.Argument(..., help="Company slug to edit"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New display name"),
    priority: Optional[str] = typer.Option(None, "--priority", "-p", help="New priority: high, low"),
    sector: Optional[str] = typer.Option(None, "--sector", help="New sector"),
    tase_id: Optional[str] = typer.Option(None, "--tase-id", help="New TASE company ID"),
    ir_url: Optional[str] = typer.Option(None, "--ir-url", help="New IR website URL"),
) -> None:
    """Edit an existing company's configuration."""
    import yaml
    from pathlib import Path
    from rich.console import Console

    console = Console()
    config_path = Path("config/companies.yaml")

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    companies = config.get("companies", {})
    if slug not in companies:
        console.print(f"[red]Company '{slug}' not found[/red]")
        raise typer.Exit(1)

    changes = []
    if name is not None:
        companies[slug]["name"] = name
        changes.append(f"name={name}")
    if priority is not None:
        companies[slug]["priority"] = priority
        changes.append(f"priority={priority}")
    if sector is not None:
        companies[slug]["sector"] = sector
        changes.append(f"sector={sector}")
    if tase_id is not None:
        companies[slug]["tase_company_id"] = tase_id
        changes.append(f"tase_id={tase_id}")
    if ir_url is not None:
        companies[slug]["ir_website_url"] = ir_url
        changes.append(f"ir_url={ir_url}")

    if not changes:
        console.print("[yellow]No changes specified[/yellow]")
        return

    config["companies"] = companies

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    console.print(f"[green]Updated {slug}: {', '.join(changes)}[/green]")


# ---------------------------------------------------------------------------
# Scheduler commands (sub-app)
# ---------------------------------------------------------------------------

scheduler_app = typer.Typer(help="Pipeline scheduler management.")
app.add_typer(scheduler_app, name="scheduler")


@scheduler_app.command(name="start")
def scheduler_start() -> None:
    """Start the pipeline scheduler (blocking)."""
    from src.scheduler import PipelineScheduler

    sched = PipelineScheduler()
    typer.echo("Starting scheduler... Press Ctrl+C to stop.")
    try:
        sched.start()
    except KeyboardInterrupt:
        sched.stop()
        typer.echo("Scheduler stopped.")


@scheduler_app.command(name="status")
def scheduler_status() -> None:
    """Show scheduler status and job queue."""
    from rich.console import Console
    from rich.table import Table
    from src.scheduler import PipelineScheduler

    console = Console()
    sched = PipelineScheduler()
    status = sched.get_status()

    console.print(f"\n[bold]Scheduler Status[/bold]")
    console.print(f"  Enabled: {status['enabled']}")
    console.print(f"  Pending jobs: {status['queue']['pending']}")
    console.print(f"  Running jobs: {status['queue']['running']}")

    if status.get("cron_schedules"):
        console.print("\n[bold]Cron Schedules:[/bold]")
        for tier, expr in status["cron_schedules"].items():
            console.print(f"  {tier}: {expr}")

    if status.get("jobs"):
        table = Table(title="Job Queue")
        table.add_column("ID", style="cyan")
        table.add_column("Company")
        table.add_column("Priority")
        table.add_column("Status")
        table.add_column("Duration")
        table.add_column("Error")

        for job in status["jobs"]:
            duration = f"{job['elapsed_seconds']:.0f}s" if job.get("elapsed_seconds") else "-"
            table.add_row(
                job["job_id"], job["company_slug"],
                job["priority"], job["status"],
                duration, job.get("error", "") or "",
            )
        console.print(table)


# ---------------------------------------------------------------------------
# Web dashboard
# ---------------------------------------------------------------------------

@app.command(name="web")
def web(
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind to"),
    port: int = typer.Option(8050, "--port", help="Port to listen on"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
) -> None:
    """Start the web dashboard."""
    from src.web import run_dashboard
    run_dashboard(host=host, port=port, debug=debug)


# ---------------------------------------------------------------------------
# TASE fetch
# ---------------------------------------------------------------------------

@app.command(name="tase-fetch")
def tase_fetch(
    companies: Optional[str] = typer.Option(
        None, "--companies", "-c",
        help="Comma-separated company slugs (default: priority pilot list)",
    ),
    all_companies: bool = typer.Option(
        False, "--all-companies",
        help="Fetch for all TASE companies with a configured tase_company_id",
    ),
    years: int = typer.Option(
        1, "--years", "-y", min=1, max=10,
        help="Backfill years when no explicit --from-date is provided (1-10)",
    ),
    from_date: Optional[str] = typer.Option(
        None, "--from-date",
        help="Start date (YYYY-MM-DD). If omitted, uses incremental state or --years.",
    ),
    to_date: Optional[str] = typer.Option(
        None, "--to-date",
        help="End date (YYYY-MM-DD). Defaults to today.",
    ),
    incremental: bool = typer.Option(
        True, "--incremental/--no-incremental",
        help="Default on: start from each company's last successful run when available.",
    ),
    output_root: str = typer.Option(
        "data/companies", "--output-root",
        help="Root output directory for downloaded files",
    ),
    max_pages: int = typer.Option(
        120, "--max-pages", min=1,
        help="Maximum paginated list pages to scan per company",
    ),
    headless: bool = typer.Option(
        True, "--headless/--headed",
        help="Run browser in headless mode (default: headless)",
    ),
) -> None:
    """Fetch Maya event PDFs/text using headless web scraping."""
    from cli.commands.tase_fetch import run_tase_fetch

    run_tase_fetch(
        companies=companies,
        all_companies=all_companies,
        years=years,
        from_date=from_date,
        to_date=to_date,
        incremental=incremental,
        output_root=output_root,
        max_pages=max_pages,
        headless=headless,
    )


# ---------------------------------------------------------------------------
# Terminal dashboard
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


# ---------------------------------------------------------------------------
# Universe management
# ---------------------------------------------------------------------------

universe_app_cli = typer.Typer(help="Manage TASE company universe and priority list.")
app.add_typer(universe_app_cli, name="universe")

@universe_app_cli.command(name="import")
def cmd_universe_import(
    csv_path: str = typer.Argument(..., help="Path to TASE companies CSV file"),
) -> None:
    """Import companies from CSV into the universe."""
    from src.universe.universe import parse_csv, save_universe, get_sectors
    companies = parse_csv(csv_path)
    path = save_universe(companies)
    typer.echo(f"Imported {len(companies)} companies into {path}")
    typer.echo(f"Found {len(get_sectors(companies))} normalized sectors.")

@universe_app_cli.command(name="serve")
def cmd_universe_serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
    port: int = typer.Option(5050, "--port", help="Port to listen on"),
) -> None:
    """Launch the universe web UI for browsing and priority management."""
    from cli.universe_app import run_server
    run_server(host=host, port=port, debug=False)

@universe_app_cli.command(name="list-priority")
def cmd_universe_list_priority() -> None:
    """List all companies currently marked as high priority."""
    from src.universe.universe import PriorityList
    pl = PriorityList()
    comps = pl.companies
    if not comps:
        typer.echo("Priority list is empty.")
    else:
        typer.echo(f"Priority List ({len(comps)} companies):")
        for c in comps:
            typer.echo(f"  - {c}")


if __name__ == "__main__":
    app()
