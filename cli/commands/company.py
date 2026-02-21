"""CLI company management -- add, edit, remove companies from registry."""

import yaml
import os
from typing import Optional

from rich.console import Console
from rich.table import Table

console = Console()


def _config_path() -> str:
    """Return absolute path to companies.yaml config file."""
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    return os.path.join(project_root, "config", "companies.yaml")


def _load_config() -> dict:
    """Load the companies YAML config.

    Returns:
        Parsed YAML dict.
    """
    with open(_config_path(), "r") as f:
        return yaml.safe_load(f)


def _save_config(data: dict) -> None:
    """Save the companies YAML config.

    Args:
        data: Config dict to serialize.
    """
    with open(_config_path(), "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def run_company_add(
    slug: str,
    name: str,
    tase_id: str,
    sector: str = "other",
    priority: str = "low",
    company_type: str = "tase_traded",
    us_ticker: Optional[str] = None,
) -> None:
    """Add a new company to the registry.

    Args:
        slug: Unique slug for the company.
        name: Human-readable company name.
        tase_id: TASE identifier.
        sector: Business sector.
        priority: Priority tier (high/low).
        company_type: Type classification.
        us_ticker: Optional US ticker symbol.
    """
    config = _load_config()

    # Check if slug already exists
    for c in config.get("companies", []):
        if c["slug"] == slug:
            console.print(f"[red]Company '{slug}' already exists[/red]")
            return

    entry: dict = {
        "slug": slug,
        "name": name,
        "tase_id": tase_id,
        "tase_company_id": None,
        "ir_url": None,
        "ir_platform": None,
        "sector": sector,
        "priority": priority,
        "reporting_currency": "ILS",
        "dual_listed": bool(us_ticker),
    }
    if us_ticker:
        entry["us_ticker"] = us_ticker

    config.setdefault("companies", []).append(entry)
    _save_config(config)
    console.print(f"[green]Added company: {name} ({slug})[/green]")


def run_company_remove(slug: str) -> None:
    """Remove a company from the registry.

    Args:
        slug: Company slug to remove.
    """
    config = _load_config()
    original_count = len(config.get("companies", []))
    config["companies"] = [
        c for c in config.get("companies", []) if c["slug"] != slug
    ]

    if len(config["companies"]) == original_count:
        console.print(f"[red]Company '{slug}' not found[/red]")
        return

    _save_config(config)
    console.print(f"[green]Removed company: {slug}[/green]")


def run_company_list() -> None:
    """List all companies in the registry."""
    config = _load_config()
    table = Table(title="Company Registry")
    table.add_column("Slug", style="cyan")
    table.add_column("Name")
    table.add_column("Priority")
    table.add_column("TASE ID")
    table.add_column("Sector")
    table.add_column("Currency")
    table.add_column("Dual Listed")

    for c in config.get("companies", []):
        table.add_row(
            c["slug"],
            c["name"],
            c.get("priority", "low"),
            str(c.get("tase_id", "-") or "-"),
            c.get("sector", ""),
            c.get("reporting_currency", "ILS"),
            "Yes" if c.get("dual_listed") else "No",
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(config.get('companies', []))} companies[/dim]")
