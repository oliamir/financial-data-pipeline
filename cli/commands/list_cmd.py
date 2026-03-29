"""finance list -- List registered companies."""

from typing import Optional
from rich.console import Console
from rich.table import Table

from src.config.loader import load_companies

console = Console()


def run_list(company_type: Optional[str] = None, priority: Optional[str] = None) -> None:
    """Display companies in a Rich table."""
    companies = load_companies()

    # Filter
    filtered = list(companies.values())
    if company_type:
        filtered = [c for c in filtered if c.company_type.value == company_type]
    if priority:
        filtered = [c for c in filtered if c.priority.value == priority]

    # Build table
    table = Table(title="Registered Companies")
    table.add_column("Slug", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Type", style="yellow")
    table.add_column("Priority", style="green")
    table.add_column("Currency")
    table.add_column("Ticker")
    table.add_column("Sector")

    for c in sorted(filtered, key=lambda x: (x.priority.value, x.slug)):
        table.add_row(
            c.slug,
            c.name,
            c.company_type.value,
            c.priority.value,
            c.reporting_currency,
            c.us_ticker or "-",
            c.sector,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(filtered)} companies[/dim]")
