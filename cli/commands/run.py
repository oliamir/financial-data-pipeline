"""CLI 'run' command -- execute the pipeline for companies."""

import asyncio
from typing import Optional, List

from rich.console import Console
from rich.table import Table

console = Console()


def run_pipeline(
    slug: str,
    years_back: int = 5,
    skip_scrape: bool = False,
    skip_analyze: bool = False,
    provider: Optional[str] = None,
    dry_run: bool = False,
    initial_research: bool = False,
    step: Optional[str] = None,
    test_mode: bool = False,
    reprocess: bool = False,
) -> None:
    """Run the pipeline for a specific company.

    Args:
        slug: Company slug to process.
        years_back: Years of history to fetch.
        skip_scrape: Skip scraping/download phase.
        skip_analyze: Skip AI analysis phase.
        provider: Force a specific AI provider name.
        dry_run: Log actions without executing.
        initial_research: Run deep strategic research prompts.
        step: Comma-separated list of steps to run (download,parse,model,memo).
        test_mode: E2E test mode (1 year, all steps).
        reprocess: Force re-extraction of already processed files.
    """
    from src.pipeline.orchestrator import run_pipeline as _run_pipeline

    # Parse step filter into a list
    steps: Optional[List[str]] = None
    if step:
        steps = [s.strip() for s in step.split(",") if s.strip()]

    # Test mode overrides
    if test_mode:
        years_back = 1
        steps = ["download", "parse", "model", "memo"]
        console.print("[bold yellow]TEST MODE:[/bold yellow] 1 year, full pipeline")

    console.print(f"[bold]Running pipeline for: {slug}[/bold]")

    if steps:
        console.print(f"  Steps: {', '.join(steps)}")
    if reprocess:
        console.print("  [yellow]Reprocess mode: clearing processed files list[/yellow]")

    try:
        asyncio.run(_run_pipeline(
            company_slug=slug,
            years_back=years_back,
            skip_scrape=skip_scrape,
            skip_analyze=skip_analyze,
            dry_run=dry_run,
            provider_override=provider,
            steps=steps,
            reprocess=reprocess,
        ))
    except KeyError as e:
        console.print(f"[red]Error: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Pipeline error: {e}[/red]")


def run_all_companies(
    priority: Optional[str] = None,
    years_back: int = 5,
) -> None:
    """Run the pipeline for all companies (or filtered by priority).

    Args:
        priority: Filter by priority tier (high/low).
        years_back: Years of history to fetch.
    """
    from src.pipeline.orchestrator import run_tier

    label = f"{priority}-priority" if priority else "all"
    console.print(f"[bold]Running pipeline for {label} companies[/bold]")

    try:
        asyncio.run(run_tier(
            priority=priority or "high",
            years_back=years_back,
        ))
    except Exception as e:
        console.print(f"[red]Pipeline error: {e}[/red]")
