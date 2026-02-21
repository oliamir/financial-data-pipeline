#!/usr/bin/env python3
"""Rich terminal dashboard for the Financial Data Pipeline.

Polls the filesystem (meta.json, financials.json, memo.json, kpi.json,
and the reports/ directory) every N seconds to display real-time pipeline
status.  This is a standalone monitoring tool that reads state from disk
-- it does NOT need to be integrated into the pipeline orchestrator.

Usage (standalone):
    python -m cli.dashboard                        # All companies, single snapshot
    python -m cli.dashboard --watch                # Auto-refresh every 5s
    python -m cli.dashboard --watch 2              # Auto-refresh every 2s
    python -m cli.dashboard --company sofwave      # Filter to one company

Usage (via argparse CLI in cli/main.py):
    python -m cli.main dashboard                   # All companies, live (default 5s)
    python -m cli.main dashboard --watch 2         # Custom refresh interval
    python -m cli.main dashboard --company sofwave # Single company
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Sequence

# ---------------------------------------------------------------------------
# Rich imports
# ---------------------------------------------------------------------------
from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.registry.company import Company, CompanyRegistry  # noqa: E402
from src.storage import paths  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PRIORITY_STYLE: Dict[str, str] = {"high": "bold yellow", "low": "dim white"}
_STATUS_STYLE: Dict[str, str] = {
    "idle": "dim",
    "downloading": "bold cyan",
    "parsing": "bold magenta",
    "complete": "bold green",
    "failed": "bold red",
}
_LOG_MAX_LINES: int = 15
_PARSE_STEPS: List[str] = ["classify", "extract", "kpi", "memo"]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CompanySnapshot:
    """Point-in-time snapshot of a single company's on-disk state."""

    company: Company

    # From meta.json
    meta: Dict[str, Any] = field(default_factory=dict)
    last_scrape: Optional[str] = None
    last_scrape_status: Optional[str] = None
    reports_found: int = 0
    reports_downloaded: int = 0
    failed_downloads: List[str] = field(default_factory=list)

    # File counts from reports/ directory
    total_files: int = 0
    pdf_files: List[str] = field(default_factory=list)
    pdf_count: int = 0

    # Processing state (derived from meta + file listing)
    processed_files: List[str] = field(default_factory=list)
    unprocessed_files: List[str] = field(default_factory=list)

    # Artifacts
    financials_count: int = 0
    memo_exists: bool = False
    recommendation: Optional[str] = None
    conviction: Optional[str] = None
    kpi_exists: bool = False

    # Derived pipeline status
    pipeline_status: str = "idle"


@dataclass
class DashboardState:
    """Aggregated, mutable state persisted across poll cycles."""

    snapshots: List[CompanySnapshot] = field(default_factory=list)
    activity_log: Deque[str] = field(
        default_factory=lambda: deque(maxlen=_LOG_MAX_LINES)
    )
    collected_at: Optional[datetime] = None

    # Previous poll meta -- used to detect changes between ticks
    _prev_meta: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Accumulated classification stats
    classification_financial: int = 0
    classification_nonfinancial: int = 0
    extraction_success: int = 0


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def _load_json(filepath: str) -> Optional[Dict[str, Any]]:
    """Safely load a JSON file; return ``None`` on any error."""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, IOError, OSError):
        return None


def _count_reports(slug: str) -> tuple[int, int, list[str]]:
    """Return ``(total_files, pdf_count, pdf_names)`` for a company."""
    report_dir = paths.reports_dir(slug)
    if not os.path.isdir(report_dir):
        return 0, 0, []
    all_files = [
        f
        for f in os.listdir(report_dir)
        if not f.startswith(".") and os.path.isfile(os.path.join(report_dir, f))
    ]
    pdfs = [f for f in all_files if f.lower().endswith(".pdf")]
    return len(all_files), len(pdfs), pdfs


def _count_financials(slug: str) -> int:
    """Count FinancialPeriod entries in ``financials.json``."""
    data_path = os.path.join(paths.company_dir(slug), "financials.json")
    raw = _load_json(data_path)
    if isinstance(raw, list):
        return len(raw)
    return 0


def _read_memo(slug: str) -> tuple[bool, Optional[str], Optional[str]]:
    """Return ``(exists, recommendation, conviction)`` from ``memo.json``."""
    raw = _load_json(paths.memo_json(slug))
    if raw is None:
        return False, None, None
    return True, raw.get("recommendation"), raw.get("conviction")


def _kpi_exists(slug: str) -> bool:
    return os.path.isfile(os.path.join(paths.company_dir(slug), "kpi.json"))


# ---------------------------------------------------------------------------
# Snapshot collection
# ---------------------------------------------------------------------------


def _collect_snapshot(
    company: Company,
    prev_meta: Optional[Dict[str, Any]],
) -> CompanySnapshot:
    """Build a ``CompanySnapshot`` by reading the filesystem."""
    slug = company.slug
    meta = _load_json(paths.meta_json(slug)) or {}
    total_files, pdf_count, pdf_names = _count_reports(slug)
    financials_count = _count_financials(slug)
    memo_exists, recommendation, conviction = _read_memo(slug)
    kpi_exists = _kpi_exists(slug)

    processed_set = set(meta.get("processed_files", []))
    report_dir = paths.reports_dir(slug)

    processed: list[str] = []
    unprocessed: list[str] = []
    for pdf in pdf_names:
        full_path = os.path.join(report_dir, pdf)
        if full_path in processed_set or pdf in processed_set:
            processed.append(pdf)
        else:
            unprocessed.append(pdf)

    # Derive pipeline_status by comparing to previous poll
    status = "idle"
    if prev_meta is not None:
        prev_dl = prev_meta.get("reports_downloaded", 0)
        cur_dl = meta.get("reports_downloaded", 0)
        prev_proc = set(prev_meta.get("processed_files", []))
        if cur_dl > prev_dl:
            status = "downloading"
        elif processed_set - prev_proc:
            status = "parsing"

    if meta.get("last_scrape_status") == "failed":
        status = "failed"
    elif processed and not unprocessed and pdf_count > 0:
        status = "complete"

    return CompanySnapshot(
        company=company,
        meta=meta,
        last_scrape=meta.get("last_scrape"),
        last_scrape_status=meta.get("last_scrape_status"),
        reports_found=meta.get("reports_found", 0),
        reports_downloaded=meta.get("reports_downloaded", 0),
        failed_downloads=meta.get("failed_downloads", []),
        total_files=total_files,
        pdf_files=pdf_names,
        pdf_count=pdf_count,
        processed_files=processed,
        unprocessed_files=unprocessed,
        financials_count=financials_count,
        memo_exists=memo_exists,
        recommendation=recommendation,
        conviction=conviction,
        kpi_exists=kpi_exists,
        pipeline_status=status,
    )


def collect_all(
    companies: Sequence[Company],
    state: DashboardState,
) -> DashboardState:
    """Poll the filesystem for every company and update *state* in-place."""
    snapshots: list[CompanySnapshot] = []
    new_prev: Dict[str, Dict[str, Any]] = {}

    classification_financial = 0
    extraction_success = 0

    for company in companies:
        prev = state._prev_meta.get(company.slug)
        snap = _collect_snapshot(company, prev_meta=prev)
        snapshots.append(snap)
        new_prev[company.slug] = snap.meta

        classification_financial += len(snap.processed_files)
        extraction_success += snap.financials_count

        # Detect new activity since last poll
        if prev is not None:
            old_processed = set(prev.get("processed_files", []))
            new_processed = set(snap.meta.get("processed_files", [])) - old_processed
            for fp in new_processed:
                basename = os.path.basename(fp)
                ts = datetime.now().strftime("%H:%M:%S")
                state.activity_log.append(
                    f"[dim]{ts}[/dim]  [green]Processed[/green] "
                    f"{company.slug}/{basename}"
                )

            old_dl = prev.get("reports_downloaded", 0)
            new_dl = snap.reports_downloaded
            if new_dl > old_dl:
                ts = datetime.now().strftime("%H:%M:%S")
                state.activity_log.append(
                    f"[dim]{ts}[/dim]  [cyan]Downloaded[/cyan] "
                    f"{new_dl - old_dl} report(s) for {company.slug}"
                )

    state.snapshots = snapshots
    state._prev_meta = new_prev
    state.collected_at = datetime.now()
    state.classification_financial = classification_financial
    state.extraction_success = extraction_success
    return state


# ---------------------------------------------------------------------------
# Rich rendering helpers
# ---------------------------------------------------------------------------


def _format_time_ago(iso_str: Optional[str]) -> Text:
    """Human-friendly relative timestamp."""
    if not iso_str:
        return Text("never", style="dim")
    try:
        dt = datetime.fromisoformat(iso_str)
        delta = datetime.now() - dt
        secs = int(delta.total_seconds())
        if secs < 0:
            label = "just now"
        elif secs < 60:
            label = f"{secs}s ago"
        elif secs < 3600:
            label = f"{secs // 60}m ago"
        elif secs < 86400:
            label = f"{secs // 3600}h ago"
        else:
            label = f"{secs // 86400}d ago"
        return Text(label)
    except (ValueError, TypeError):
        return Text("?", style="dim")


def _status_badge(status: str) -> Text:
    """Colored, reversed-background status badge."""
    style = _STATUS_STYLE.get(status, "dim")
    return Text(f" {status.upper()} ", style=f"{style} reverse")


def _scrape_badge(status: Optional[str]) -> Text:
    """Colored scrape-result badge."""
    if status == "success":
        return Text("OK", style="bold green")
    if status == "failed":
        return Text("FAIL", style="bold red")
    if status == "no_reports":
        return Text("EMPTY", style="yellow")
    if status is None:
        return Text("--", style="dim")
    return Text(status, style="yellow")


def _mini_bar(current: int, total: int, width: int = 14) -> Text:
    """Compact block-character progress bar."""
    if total == 0:
        return Text("." * width, style="dim")
    filled = int(width * min(current, total) / total)
    bar_str = "\u2588" * filled + "\u2591" * (width - filled)
    pct = current / total * 100
    if pct >= 100:
        style = "green"
    elif pct > 0:
        style = "yellow"
    else:
        style = "dim"
    return Text(bar_str, style=style)


# ---------------------------------------------------------------------------
# Panel 1 -- Company Overview
# ---------------------------------------------------------------------------


def _build_company_table(snapshots: Sequence[CompanySnapshot]) -> Table:
    """Rich Table showing every company with key metrics."""
    table = Table(
        title="Company Overview",
        title_style="bold cyan",
        border_style="bright_black",
        show_header=True,
        header_style="bold",
        expand=True,
        pad_edge=True,
        padding=(0, 1),
    )

    table.add_column("Company", style="white", no_wrap=True, min_width=18, ratio=3)
    table.add_column("Sector", style="dim", no_wrap=True, ratio=2)
    table.add_column("Pri", justify="center", no_wrap=True, width=5)
    table.add_column("Scrape", justify="center", no_wrap=True, width=7)
    table.add_column("Last Run", justify="right", no_wrap=True, width=9)
    table.add_column("DL", justify="right", no_wrap=True, width=5)
    table.add_column("Parsed", justify="right", no_wrap=True, width=8)
    table.add_column("Progress", justify="center", no_wrap=True, width=16)
    table.add_column("Fin", justify="right", no_wrap=True, width=4)
    table.add_column("KPI", justify="center", no_wrap=True, width=4)
    table.add_column("Memo", justify="center", no_wrap=True, width=6)
    table.add_column("Status", justify="center", no_wrap=True, width=14)

    for snap in snapshots:
        c = snap.company
        parsed = len(snap.processed_files)
        total_parse = snap.pdf_count
        pri_style = _PRIORITY_STYLE.get(c.priority, "dim")

        dl_text = Text(
            str(snap.pdf_count),
            style="white" if snap.pdf_count > 0 else "dim",
        )
        parse_text = Text(
            f"{parsed}/{total_parse}",
            style=(
                "green"
                if parsed == total_parse and total_parse > 0
                else ("yellow" if parsed > 0 else "dim")
            ),
        )
        fin_text = Text(
            str(snap.financials_count),
            style="white" if snap.financials_count > 0 else "dim",
        )
        kpi_text = (
            Text("Y", style="green") if snap.kpi_exists else Text("-", style="dim")
        )

        memo_text: Text
        if snap.memo_exists:
            rec = (snap.recommendation or "?").upper()
            rec_style = {"BUY": "bold green", "SELL": "bold red", "HOLD": "yellow"}.get(
                rec, "white"
            )
            memo_text = Text(rec, style=rec_style)
        else:
            memo_text = Text("-", style="dim")

        table.add_row(
            Text(c.name[:24]),
            Text(c.sector[:16]),
            Text(c.priority.upper(), style=pri_style),
            _scrape_badge(snap.last_scrape_status),
            _format_time_ago(snap.last_scrape),
            dl_text,
            parse_text,
            _mini_bar(parsed, total_parse),
            fin_text,
            kpi_text,
            memo_text,
            _status_badge(snap.pipeline_status),
        )

    return table


# ---------------------------------------------------------------------------
# Panel 2 -- Download Progress
# ---------------------------------------------------------------------------


def _build_download_panel(snapshots: Sequence[CompanySnapshot]) -> Panel:
    """Download progress panel -- shows active downloads or a summary."""
    downloading = [s for s in snapshots if s.pipeline_status == "downloading"]
    if downloading:
        lines = _render_active_downloads(downloading)
    else:
        lines = _render_download_summary(snapshots)

    content = (
        Group(*lines) if lines else Text("No download activity detected.", style="dim")
    )
    return Panel(
        content,
        title="[bold cyan]Download Progress[/bold cyan]",
        border_style="bright_black",
        padding=(1, 2),
    )


def _render_active_downloads(downloading: Sequence[CompanySnapshot]) -> list[Any]:
    """Render Rich Progress bars for actively downloading companies."""
    parts: list[Any] = []
    for snap in downloading:
        found = max(snap.reports_found, 1)
        dl = snap.reports_downloaded
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}"),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            expand=True,
        )
        progress.add_task(snap.company.name[:24], total=found, completed=dl)
        parts.append(progress)
        if snap.failed_downloads:
            parts.append(
                Text(
                    f"  Failed: {len(snap.failed_downloads)} file(s)",
                    style="red",
                )
            )
    return parts


def _render_download_summary(snapshots: Sequence[CompanySnapshot]) -> list[Any]:
    """Static download summary when nothing is actively downloading."""
    total_found = sum(s.reports_found for s in snapshots)
    total_dl = sum(s.reports_downloaded for s in snapshots)
    total_pdf = sum(s.pdf_count for s in snapshots)
    total_failed = sum(len(s.failed_downloads) for s in snapshots)

    parts: list[Any] = []

    summary = Table(show_header=False, box=None, padding=(0, 2))
    summary.add_column("Label", style="dim", no_wrap=True)
    summary.add_column("Value", style="white", no_wrap=True)
    summary.add_row("Reports found (meta)", str(total_found))
    summary.add_row("Reports downloaded (meta)", str(total_dl))
    summary.add_row("PDF files on disk", str(total_pdf))
    if total_failed > 0:
        summary.add_row(
            Text("Failed downloads", style="red"),
            Text(str(total_failed), style="bold red"),
        )
    parts.append(summary)
    parts.append(Text(""))

    bar_table = Table(
        show_header=True, header_style="dim", box=None, padding=(0, 1)
    )
    bar_table.add_column("Company", style="white", no_wrap=True, min_width=18)
    bar_table.add_column("Found", justify="right", width=6)
    bar_table.add_column("DL", justify="right", width=5)
    bar_table.add_column("Disk", justify="right", width=6)
    bar_table.add_column("Progress", width=16)

    for snap in snapshots:
        if snap.reports_found == 0 and snap.pdf_count == 0:
            continue
        bar_table.add_row(
            snap.company.name[:18],
            str(snap.reports_found),
            str(snap.reports_downloaded),
            str(snap.pdf_count),
            _mini_bar(snap.pdf_count, max(snap.reports_found, snap.pdf_count)),
        )

    parts.append(bar_table)
    return parts


# ---------------------------------------------------------------------------
# Panel 3 -- AI Parsing Progress
# ---------------------------------------------------------------------------


def _build_parsing_panel(
    snapshots: Sequence[CompanySnapshot],
    state: DashboardState,
) -> Panel:
    """AI parsing progress panel."""
    parsing = [s for s in snapshots if s.pipeline_status == "parsing"]
    if parsing:
        lines = _render_active_parsing(parsing, state)
    else:
        lines = _render_parsing_summary(snapshots, state)

    content = (
        Group(*lines) if lines else Text("No parsing activity detected.", style="dim")
    )
    return Panel(
        content,
        title="[bold magenta]AI Parsing Progress[/bold magenta]",
        border_style="bright_black",
        padding=(1, 2),
    )


def _render_active_parsing(
    parsing: Sequence[CompanySnapshot],
    state: DashboardState,
) -> list[Any]:
    """Rich Progress bars for companies whose parsing set grew since last poll."""
    parts: list[Any] = []
    for snap in parsing:
        parsed = len(snap.processed_files)
        total = snap.pdf_count

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}"),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            expand=True,
        )
        progress.add_task(snap.company.name[:24], total=total, completed=parsed)
        parts.append(progress)

        if snap.unprocessed_files:
            display = snap.unprocessed_files[0]
            if len(display) > 50:
                display = display[:50]
            parts.append(Text(f"  Current: {display}", style="dim italic"))

        # Pipeline sub-step indicator
        steps_text = Text("  Steps: ")
        for idx, step in enumerate(_PARSE_STEPS):
            if idx > 0:
                steps_text.append(" > ", style="dim")
            steps_text.append(
                f" {step} ",
                style="bold magenta reverse" if step == "classify" else "dim",
            )
        parts.append(steps_text)
        parts.append(Text(""))

    _append_classification_stats(parts, state)
    return parts


def _render_parsing_summary(
    snapshots: Sequence[CompanySnapshot],
    state: DashboardState,
) -> list[Any]:
    """Static parsing summary when nothing is actively being parsed."""
    total_pdfs = sum(s.pdf_count for s in snapshots)
    total_parsed = sum(len(s.processed_files) for s in snapshots)
    total_unparsed = sum(len(s.unprocessed_files) for s in snapshots)
    total_fin = sum(s.financials_count for s in snapshots)
    total_kpi = sum(1 for s in snapshots if s.kpi_exists)
    total_memo = sum(1 for s in snapshots if s.memo_exists)

    parts: list[Any] = []

    # Overall parsing progress bar
    progress = Progress(
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.percentage:>5.1f}%"),
        expand=True,
    )
    progress.add_task(
        "Reports parsed",
        total=max(total_pdfs, 1),
        completed=total_parsed,
    )
    parts.append(progress)
    parts.append(Text(""))

    stats = Table(show_header=False, box=None, padding=(0, 2))
    stats.add_column("Label", style="dim", no_wrap=True)
    stats.add_column("Value", style="white", no_wrap=True)
    stats.add_row("Total PDFs", str(total_pdfs))
    stats.add_row("Parsed", Text(str(total_parsed), style="green"))
    stats.add_row(
        "Pending",
        Text(
            str(total_unparsed),
            style="yellow" if total_unparsed > 0 else "dim",
        ),
    )
    stats.add_row(
        "Financial periods extracted", Text(str(total_fin), style="white")
    )
    stats.add_row("KPI dashboards", Text(str(total_kpi), style="white"))
    stats.add_row("Investment memos", Text(str(total_memo), style="white"))
    parts.append(stats)
    parts.append(Text(""))

    # Per-company mini-bars
    bar_table = Table(
        show_header=True, header_style="dim", box=None, padding=(0, 1)
    )
    bar_table.add_column("Company", style="white", no_wrap=True, min_width=18)
    bar_table.add_column("PDFs", justify="right", width=5)
    bar_table.add_column("Parsed", justify="right", width=8)
    bar_table.add_column("Fin", justify="right", width=4)
    bar_table.add_column("Memo", justify="center", width=5)
    bar_table.add_column("Progress", width=16)

    for snap in snapshots:
        if snap.pdf_count == 0:
            continue
        parsed = len(snap.processed_files)
        memo_label = (
            Text("Y", style="green") if snap.memo_exists else Text("-", style="dim")
        )
        bar_table.add_row(
            snap.company.name[:18],
            str(snap.pdf_count),
            f"{parsed}/{snap.pdf_count}",
            str(snap.financials_count),
            memo_label,
            _mini_bar(parsed, snap.pdf_count),
        )

    parts.append(bar_table)
    return parts


def _append_classification_stats(
    parts: list[Any], state: DashboardState
) -> None:
    """Append classification and extraction breakdown."""
    stats = Table(show_header=False, box=None, padding=(0, 2))
    stats.add_column("Label", style="dim", no_wrap=True)
    stats.add_column("Value", style="white", no_wrap=True)
    stats.add_row(
        "Classified (processed)",
        Text(str(state.classification_financial), style="green"),
    )
    stats.add_row(
        "Extraction results",
        Text(f"{state.extraction_success} period(s)", style="white"),
    )
    parts.append(stats)


# ---------------------------------------------------------------------------
# Panel 4 -- Recent Activity Log
# ---------------------------------------------------------------------------


def _build_activity_log(state: DashboardState) -> Panel:
    """Panel showing the last N log lines of pipeline activity."""
    if state.activity_log:
        lines = Text()
        for entry in state.activity_log:
            lines.append_text(Text.from_markup(entry))
            lines.append("\n")
    else:
        lines = Text(
            "Waiting for pipeline activity...\n", style="dim italic"
        )
        lines.append(
            "The dashboard polls the filesystem every refresh interval.\n"
            "Start a pipeline run in another terminal to see activity here.",
            style="dim",
        )

    return Panel(
        lines,
        title="[bold yellow]Recent Activity[/bold yellow]",
        border_style="bright_black",
        padding=(1, 2),
    )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------


def _build_header(state: DashboardState) -> Panel:
    """Top banner with global summary counters."""
    snaps = state.snapshots
    total = len(snaps)
    scraped = sum(
        1 for s in snaps if s.last_scrape_status == "success"
    )
    total_pdfs = sum(s.pdf_count for s in snaps)
    total_parsed = sum(len(s.processed_files) for s in snaps)
    total_fin = sum(s.financials_count for s in snaps)
    total_memos = sum(1 for s in snaps if s.memo_exists)
    now = (
        state.collected_at.strftime("%Y-%m-%d %H:%M:%S")
        if state.collected_at
        else "--"
    )

    dl_active = sum(
        1 for s in snaps if s.pipeline_status == "downloading"
    )
    parse_active = sum(
        1 for s in snaps if s.pipeline_status == "parsing"
    )

    title = Text("Financial Data Pipeline Dashboard", style="bold cyan")

    stats = Text()
    stats.append(f"  {scraped}/{total} scraped", style="white")
    stats.append("  |  ", style="dim")
    stats.append(f"{total_pdfs} PDFs", style="white")
    stats.append(
        f" ({total_parsed} parsed)",
        style="green" if total_parsed > 0 else "dim",
    )
    stats.append("  |  ", style="dim")
    stats.append(f"{total_fin} periods", style="white")
    stats.append("  |  ", style="dim")
    stats.append(f"{total_memos} memos", style="white")

    if dl_active > 0:
        stats.append("  |  ", style="dim")
        stats.append(f"{dl_active} downloading", style="bold cyan")
    if parse_active > 0:
        stats.append("  |  ", style="dim")
        stats.append(f"{parse_active} parsing", style="bold magenta")

    stats.append(f"  |  {now}", style="dim")

    content = Group(Align.center(title), Align.center(stats))
    return Panel(content, border_style="cyan", padding=(0, 2))


# ---------------------------------------------------------------------------
# Full layout assembly
# ---------------------------------------------------------------------------


def _build_layout(state: DashboardState) -> Layout:
    """Assemble the Rich Layout from current ``DashboardState``."""
    layout = Layout()

    log_lines = len(state.activity_log) if state.activity_log else 4
    footer_height = min(log_lines + 5, _LOG_MAX_LINES + 5)

    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="body"),
        Layout(name="footer", size=footer_height),
    )

    layout["body"].split_column(
        Layout(name="company_table", ratio=3),
        Layout(name="panels", ratio=2),
    )

    layout["panels"].split_row(
        Layout(name="download", ratio=1),
        Layout(name="parsing", ratio=1),
    )

    layout["header"].update(_build_header(state))
    layout["company_table"].update(
        Panel(
            _build_company_table(state.snapshots),
            border_style="bright_black",
            padding=(0, 0),
        )
    )
    layout["download"].update(_build_download_panel(state.snapshots))
    layout["parsing"].update(_build_parsing_panel(state.snapshots, state))
    layout["footer"].update(_build_activity_log(state))

    return layout


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def run_dashboard(
    slug: Optional[str] = None,
    priority: Optional[str] = None,
    watch: Optional[int] = None,
) -> None:
    """Main entry point.

    Args:
        slug: Optional company slug to filter to.
        priority: Optional priority tier (``high`` or ``low``).
        watch: If not None, auto-refresh every *watch* seconds.
    """
    registry = CompanyRegistry()

    if slug:
        companies: list[Company] = [registry.get(slug)]
    elif priority:
        companies = registry.list_by_priority(priority)
    else:
        companies = registry.all()

    # Sort: high priority first, then alphabetical by name
    companies.sort(
        key=lambda c: (0 if c.priority == "high" else 1, c.name)
    )

    console = Console()
    state = DashboardState()

    if watch is not None:
        interval = max(1, watch)
        _run_live(console, companies, state, interval)
    else:
        collect_all(companies, state)
        console.print(_build_layout(state))


def _run_live(
    console: Console,
    companies: Sequence[Company],
    state: DashboardState,
    interval: int,
) -> None:
    """Live auto-refreshing dashboard using ``rich.live.Live``."""
    collect_all(companies, state)

    with Live(
        _build_layout(state),
        console=console,
        refresh_per_second=1,
        screen=True,
    ) as live:
        try:
            while True:
                time.sleep(interval)
                collect_all(companies, state)
                live.update(_build_layout(state))
        except KeyboardInterrupt:
            pass

    console.print("\n[dim]Dashboard stopped.[/dim]\n")


# ---------------------------------------------------------------------------
# Standalone: ``python -m cli.dashboard``
# ---------------------------------------------------------------------------


def main() -> None:
    """Argparse entry point for standalone execution."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Rich terminal dashboard for the Financial Data Pipeline"
    )
    parser.add_argument(
        "--company",
        "-c",
        default=None,
        help="Filter to a single company slug",
    )
    parser.add_argument(
        "--tier",
        choices=["high", "low"],
        default=None,
        help="Filter by priority tier",
    )
    parser.add_argument(
        "--watch",
        "-w",
        nargs="?",
        const=5,
        type=int,
        metavar="SECONDS",
        help="Auto-refresh (default: 5s)",
    )
    args = parser.parse_args()

    run_dashboard(slug=args.company, priority=args.tier, watch=args.watch)


if __name__ == "__main__":
    main()
