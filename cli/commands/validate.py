"""CLI validate command -- validate company data quality."""

import os
import json
from typing import Optional

from rich.console import Console
from rich.table import Table

console = Console()


def run_validate(slug: Optional[str] = None) -> None:
    """Validate extracted data for a company or all companies.

    Checks financials CSV, memo JSON, and report processing status
    for each company and displays a summary table with issues.

    Args:
        slug: Optional company slug. If None, validates all companies.
    """
    from src.registry.company import CompanyRegistry
    from src.storage.file_manager import FileManager
    from src.storage import paths

    registry = CompanyRegistry()

    if slug:
        try:
            companies = [registry.get(slug)]
        except KeyError:
            console.print(f"[red]Company '{slug}' not found in registry[/red]")
            return
    else:
        companies = registry.all()

    table = Table(title="Data Validation Results")
    table.add_column("Company", style="cyan")
    table.add_column("Financials")
    table.add_column("Rows")
    table.add_column("Memo")
    table.add_column("Reports")
    table.add_column("Issues", style="red")

    for company in companies:
        s = company.slug
        fm = FileManager(s)
        issues = []

        # Check financials CSV
        csv_path = paths.financials_csv(s)
        financials = fm.load_financials()
        if financials:
            fin_status = f"[green]{len(financials)} rows[/green]"

            # Check for rows with revenue
            rows_with_revenue = [
                f for f in financials
                if f.get("metric_name") == "revenue" and f.get("value") is not None
            ]
            if not rows_with_revenue:
                issues.append("No revenue data extracted")

            # Check for suspicious values (wrong units)
            for row in financials:
                val = row.get("value")
                metric = row.get("metric_name", "")
                fy = row.get("fiscal_year", "")
                if val is not None and isinstance(val, (int, float)):
                    if metric == "revenue" and abs(val) > 1_000_000_000:
                        issues.append(
                            f"FY{fy} revenue {val:,.0f} looks like wrong units"
                        )
                    if metric == "total_equity" and val < -1_000_000:
                        issues.append(
                            f"FY{fy} equity {val:,.0f} looks like wrong units"
                        )
        elif os.path.exists(csv_path):
            fin_status = "[yellow]Empty[/yellow]"
            issues.append("Financials CSV exists but is empty")
        else:
            fin_status = "[red]Missing[/red]"

        rows_detail = str(len(financials)) if financials else "0"

        # Check memo
        memo = fm.load_memo()
        if memo:
            rec = memo.get("recommendation", "?")
            memo_status = f"[green]{rec}[/green]"
            if not memo.get("executive_summary"):
                issues.append("Memo missing executive_summary")
        else:
            memo_status = "[red]None[/red]"

        # Check reports processing status
        meta = fm.load_meta()
        report_dir = paths.reports_dir(s)
        total_reports = 0
        if os.path.exists(report_dir):
            total_reports = len([
                f for f in os.listdir(report_dir)
                if not f.startswith(".") and os.path.isfile(os.path.join(report_dir, f))
            ])
        processed = len(meta.get("processed_files", []))

        if total_reports > 0:
            reports_status = f"{processed}/{total_reports}"
            if processed < total_reports:
                issues.append(
                    f"{total_reports - processed}/{total_reports} reports unprocessed"
                )
        else:
            reports_status = "[dim]0[/dim]"

        issue_str = "; ".join(issues) if issues else "[green]OK[/green]"
        table.add_row(
            company.name, fin_status, rows_detail,
            memo_status, reports_status, issue_str,
        )

    console.print(table)
