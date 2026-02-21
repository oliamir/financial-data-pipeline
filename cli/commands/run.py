"""CLI 'run' command — execute the pipeline for companies."""

import asyncio
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def run_pipeline(
    slug: str = typer.Argument(..., help="Company slug to process"),
    years_back: int = typer.Option(5, "--years", "-y", help="Years of history to fetch"),
    skip_scrape: bool = typer.Option(False, "--skip-scrape", help="Skip scraping/download"),
    skip_analyze: bool = typer.Option(False, "--skip-analyze", help="Skip AI analysis"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Force specific AI provider"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Log actions without executing"),
    initial_research: bool = False,
    requested_steps: Optional[List[str]] = None,
    reprocess: bool = False,
) -> None:
    """Run the pipeline for a specific company."""
    from src.pipeline.runner import run_company

    console.print(f"[bold]Running pipeline for: {slug}[/bold]")

    if requested_steps:
        console.print(f"  Steps: {', '.join(requested_steps)}")
    if reprocess:
        console.print(f"  [yellow]Mode: REPROCESS (re-analyzing processed files)[/yellow]")

    try:
        job = asyncio.run(run_company(
            slug=slug,
            years_back=years_back,
            skip_scrape=skip_scrape,
            skip_analyze=skip_analyze,
            provider_override=provider,
            dry_run=dry_run,
            initial_research=initial_research,
            requested_steps=requested_steps,
            reprocess=reprocess,
        ))

        # Display results
        table = Table(title=f"Pipeline Results: {slug}")
        table.add_column("Step", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Detail")

        for step in job.steps:
            status_style = "green" if step.status == "success" else "red" if step.status == "failed" else "yellow"
            table.add_row(step.step.value, f"[{status_style}]{step.status}[/{status_style}]", step.detail or "")

        console.print(table)

        if job.status == "complete":
            console.print("[green]Pipeline completed successfully[/green]")
        else:
            console.print(f"[red]Pipeline {job.status}[/red]")
            if job.error:
                console.print(f"[red]Error: {job.error}[/red]")

    except KeyError as e:
        console.print(f"[red]Error: {e}[/red]")
    except ValueError as e:
        console.print(f"[red]Invalid step: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Pipeline error: {e}[/red]")


def run_all_companies(
    priority: Optional[str] = typer.Option(None, "--priority", "-p", help="Filter by priority tier"),
    years_back: int = typer.Option(5, "--years", "-y", help="Years of history"),
) -> None:
    """Run the pipeline for all companies (or by priority)."""
    from src.pipeline.runner import run_all

    console.print(f"[bold]Running pipeline for {'all' if not priority else priority + '-priority'} companies[/bold]")

    jobs = asyncio.run(run_all(priority=priority, years_back=years_back))

    # Summary table
    table = Table(title="Pipeline Summary")
    table.add_column("Company", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Steps")

    for job in jobs:
        status_style = "green" if job.status == "complete" else "red"
        table.add_row(
            job.company_slug,
            f"[{status_style}]{job.status}[/{status_style}]",
            str(len(job.steps)),
        )

    console.print(table)
