"""CLI command for headless TASE Maya event downloads."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from src.config.loader import load_companies
from src.models.company import Company, CompanyType
from src.tase_maya import DEFAULT_PRIORITY_SLUGS, TaseMayaDownloader

console = Console()


def _parse_date(value: Optional[str], option_name: str) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(f"{option_name} must be in YYYY-MM-DD format") from exc


def _select_companies(requested_slugs: Optional[str], all_companies: bool) -> list[Company]:
    companies = load_companies()

    if all_companies:
        selected = [
            company
            for company in companies.values()
            if company.company_type == CompanyType.TASE_TRADED and company.tase_company_id
        ]
        return sorted(selected, key=lambda company: company.slug)

    if requested_slugs:
        slugs = [value.strip().lower() for value in requested_slugs.split(",") if value.strip()]
    else:
        slugs = DEFAULT_PRIORITY_SLUGS

    selected: list[Company] = []
    missing: list[str] = []
    for slug in slugs:
        company = companies.get(slug)
        if company and company.tase_company_id:
            selected.append(company)
        else:
            missing.append(slug)

    for slug in missing:
        console.print(f"[yellow]Skipping unknown/missing-TASE company: {slug}[/yellow]")

    return selected


def run_tase_fetch(
    *,
    companies: Optional[str],
    all_companies: bool,
    years: int,
    from_date: Optional[str],
    to_date: Optional[str],
    incremental: bool,
    output_root: str,
    max_pages: int,
    headless: bool,
) -> None:
    """Run headless Maya event download workflow."""
    from_date_parsed = _parse_date(from_date, "--from-date")
    to_date_parsed = _parse_date(to_date, "--to-date")

    if from_date_parsed and to_date_parsed and from_date_parsed > to_date_parsed:
        raise typer.BadParameter("--from-date cannot be after --to-date")

    selected_companies = _select_companies(companies, all_companies)
    if not selected_companies:
        console.print("[red]No companies selected.[/red]")
        raise typer.Exit(code=1)

    console.print(
        f"[bold]TASE Maya fetch[/bold] for {len(selected_companies)} companies "
        f"(years={years}, incremental={incremental})"
    )

    downloader = TaseMayaDownloader(
        output_root=output_root,
        headless=headless,
        max_pages=max_pages,
    )
    summaries = asyncio.run(
        downloader.run(
            companies=selected_companies,
            years=years,
            from_date=from_date_parsed,
            to_date=to_date_parsed,
            incremental=incremental,
        )
    )

    table = Table(title="TASE Maya Download Summary")
    table.add_column("Company", style="cyan")
    table.add_column("Date Window")
    table.add_column("Events")
    table.add_column("PDF Events")
    table.add_column("PDF Files")
    table.add_column("Text Fallback")
    table.add_column("Status")

    failures = 0
    for summary in summaries:
        status = summary.status
        if status != "success":
            failures += 1

        date_window = f"{summary.from_date.isoformat()} -> {summary.to_date.isoformat()}"
        table.add_row(
            summary.company_slug,
            date_window,
            str(summary.events_found),
            str(summary.events_with_pdf),
            str(summary.pdf_files_downloaded),
            str(summary.text_fallback_events),
            status if not summary.error else f"{status}: {summary.error}",
        )

    console.print(table)
    console.print(f"Output root: {downloader.output_root}")
    console.print(f"State file: {downloader.state_path}")

    if failures:
        raise typer.Exit(code=1)

