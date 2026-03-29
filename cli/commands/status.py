"""finance status -- Show pipeline status."""

from typing import Optional
from rich.console import Console
from rich.table import Table

from src.config.loader import load_companies
from src.storage.file_manager import FileManager

console = Console()


def run_status(slug: Optional[str] = None, failed_only: bool = False) -> None:
    """Display pipeline status in a Rich table."""
    companies = load_companies()

    if slug:
        if slug not in companies:
            console.print(f"[red]Company '{slug}' not found[/red]")
            return
        targets = {slug: companies[slug]}
    else:
        targets = companies

    table = Table(title="Pipeline Status")
    table.add_column("Company", style="cyan")
    table.add_column("Priority")
    table.add_column("Last Scrape")
    table.add_column("Reports", justify="right")
    table.add_column("Financials", justify="right")
    table.add_column("Memo")
    table.add_column("Status")

    for company_slug, company in sorted(targets.items()):
        fm = FileManager(company_slug)
        meta = fm.load_meta()

        last_scrape = meta.get("last_scrape", "Never")
        if last_scrape and last_scrape != "Never":
            last_scrape = last_scrape[:16]

        reports_count = meta.get("reports_downloaded", 0)
        financials = fm.load_financials()
        memo = fm.load_memo()

        scrape_status = meta.get("last_scrape_status", "-")
        if failed_only and scrape_status != "failed":
            continue

        status_style = "green" if scrape_status == "success" else "red" if scrape_status == "failed" else "dim"

        table.add_row(
            company.name,
            company.priority.value,
            str(last_scrape),
            str(reports_count),
            str(len(financials)),
            "[green]YES[/green]" if memo else "[dim]NO[/dim]",
            f"[{status_style}]{scrape_status}[/{status_style}]",
        )

    console.print(table)
