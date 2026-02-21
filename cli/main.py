"""Finance CLI -- Typer application entry point.

Usage:
    finance list [--type TYPE] [--priority PRIORITY]
    finance status [SLUG] [--failed]
    finance run <SLUG> [--years N] [--skip-scrape] [--skip-analyze] [--provider PROVIDER]
    finance run-all [--priority PRIORITY] [--years N]
    finance build-model <SLUG>
    finance web [--port PORT]
    finance scheduler
"""

import typer
from typing import Optional

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
    skip_scrape: bool = typer.Option(False, "--skip-scrape", help="Skip scraping/download"),
    skip_analyze: bool = typer.Option(False, "--skip-analyze", help="Skip AI analysis"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Force specific AI provider"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Log actions without executing"),
) -> None:
    """Run the pipeline for a specific company."""
    from cli.commands.run import run_pipeline
    run_pipeline(slug=slug, years_back=years, skip_scrape=skip_scrape,
                 skip_analyze=skip_analyze, provider=provider, dry_run=dry_run)


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


@app.command(name="web")
def web(
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind to"),
    port: int = typer.Option(8050, "--port", help="Port to listen on"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
) -> None:
    """Start the web dashboard."""
    from src.web import run_dashboard
    run_dashboard(host=host, port=port, debug=debug)


@app.command(name="scheduler")
def scheduler() -> None:
    """Start the pipeline scheduler."""
    from src.scheduler import PipelineScheduler

    sched = PipelineScheduler()
    typer.echo("Starting scheduler... Press Ctrl+C to stop.")
    try:
        sched.start()
    except KeyboardInterrupt:
        sched.stop()
        typer.echo("Scheduler stopped.")


if __name__ == "__main__":
    app()
