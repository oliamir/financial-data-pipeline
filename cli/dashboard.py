#!/usr/bin/env python3
"""
Terminal dashboard for the Financial Data Pipeline.
Shows real-time status of downloads and parsing for all companies.

Usage:
    python -m cli.dashboard              # All companies
    python -m cli.dashboard --tier high  # High-priority only
    python -m cli.dashboard --watch      # Auto-refresh every 5s
    python -m cli.dashboard --watch 2    # Auto-refresh every 2s
"""
import sys
import os
import time
import json
import shutil
import argparse
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.registry.company import CompanyRegistry
from src.storage import paths

# ── Colors ──────────────────────────────────────────────────────────────────

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"
BG_BLUE = "\033[44m"

# ── Status symbols ──────────────────────────────────────────────────────────

STATUS_OK = f"{GREEN}OK{RESET}"
STATUS_FAIL = f"{RED}FAIL{RESET}"
STATUS_PARTIAL = f"{YELLOW}PARTIAL{RESET}"
STATUS_NONE = f"{DIM}--{RESET}"
STATUS_RUNNING = f"{CYAN}RUNNING{RESET}"

# ── Helpers ─────────────────────────────────────────────────────────────────


def load_meta(slug):
    meta_path = paths.meta_json(slug)
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def count_reports(slug):
    report_dir = paths.reports_dir(slug)
    if not os.path.exists(report_dir):
        return 0, 0, []
    files = [f for f in os.listdir(report_dir) if not f.startswith(".") and os.path.isfile(os.path.join(report_dir, f))]
    pdfs = [f for f in files if f.lower().endswith(".pdf")]
    return len(files), len(pdfs), pdfs


def count_financials(slug):
    csv_path = paths.financials_csv(slug)
    if not os.path.exists(csv_path):
        return 0
    try:
        with open(csv_path, "r") as f:
            return max(0, sum(1 for _ in f) - 1)  # subtract header
    except IOError:
        return 0


def has_memo(slug):
    memo_path = paths.memo_json(slug)
    if not os.path.exists(memo_path):
        return False, None
    try:
        with open(memo_path, "r") as f:
            memo = json.load(f)
        return True, memo.get("recommendation", "N/A")
    except (json.JSONDecodeError, IOError):
        return False, None


def format_time_ago(iso_str):
    if not iso_str:
        return f"{DIM}never{RESET}"
    try:
        dt = datetime.fromisoformat(iso_str)
        delta = datetime.now() - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s ago"
        elif secs < 3600:
            return f"{secs // 60}m ago"
        elif secs < 86400:
            return f"{secs // 3600}h ago"
        else:
            return f"{secs // 86400}d ago"
    except (ValueError, TypeError):
        return f"{DIM}?{RESET}"


def scrape_status_color(status):
    if status == "success":
        return f"{GREEN}{status}{RESET}"
    elif status == "failed":
        return f"{RED}{status}{RESET}"
    elif status == "no_reports":
        return f"{YELLOW}no_reports{RESET}"
    elif status is None:
        return f"{DIM}--{RESET}"
    return f"{YELLOW}{status}{RESET}"


def progress_bar(current, total, width=12):
    if total == 0:
        return f"{DIM}{'.' * width}{RESET}"
    filled = int(width * current / total)
    bar = "█" * filled + "░" * (width - filled)
    pct = current / total * 100
    if pct >= 100:
        return f"{GREEN}{bar}{RESET}"
    elif pct > 0:
        return f"{YELLOW}{bar}{RESET}"
    else:
        return f"{DIM}{bar}{RESET}"


# ── Dashboard rendering ────────────────────────────────────────────────────


def get_company_status(company):
    """Gather all status info for a company."""
    slug = company.slug
    meta = load_meta(slug)
    total_files, pdf_count, pdf_names = count_reports(slug)
    metric_rows = count_financials(slug)
    memo_exists, recommendation = has_memo(slug)

    processed = []
    unprocessed = []
    if meta:
        processed_set = set(meta.get("processed_files", []))
        report_dir = paths.reports_dir(slug)
        for pdf in pdf_names:
            full_path = os.path.join(report_dir, pdf)
            if full_path in processed_set:
                processed.append(pdf)
            else:
                unprocessed.append(pdf)

    return {
        "company": company,
        "meta": meta,
        "total_files": total_files,
        "pdf_count": pdf_count,
        "pdf_names": pdf_names,
        "processed": processed,
        "unprocessed": unprocessed,
        "metric_rows": metric_rows,
        "memo_exists": memo_exists,
        "recommendation": recommendation,
    }


def render_dashboard(companies, show_files=True):
    """Render the full dashboard."""
    term_width = shutil.get_terminal_size((120, 40)).columns
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []

    # Header
    lines.append("")
    lines.append(f"  {BOLD}{CYAN}Financial Data Pipeline Dashboard{RESET}  {DIM}|  {now}{RESET}")
    lines.append(f"  {DIM}{'─' * min(term_width - 4, 100)}{RESET}")
    lines.append("")

    # Summary counters
    statuses = [get_company_status(c) for c in companies]
    total = len(statuses)
    scraped = sum(1 for s in statuses if s["meta"] and s["meta"].get("last_scrape_status") == "success")
    with_data = sum(1 for s in statuses if s["metric_rows"] > 0)
    with_memo = sum(1 for s in statuses if s["memo_exists"])
    total_pdfs = sum(s["pdf_count"] for s in statuses)
    total_processed = sum(len(s["processed"]) for s in statuses)
    total_metrics = sum(s["metric_rows"] for s in statuses)

    lines.append(f"  {BOLD}Summary:{RESET}  "
                 f"{scraped}/{total} scraped  |  "
                 f"{total_pdfs} PDFs ({total_processed} parsed)  |  "
                 f"{total_metrics} metrics  |  "
                 f"{with_memo}/{total} memos")
    lines.append("")

    # Table header
    hdr = (f"  {BOLD}{'COMPANY':<22} {'PRI':>4} {'SCRAPE':>10} {'WHEN':>8} "
           f"{'DL':>4} {'PARSED':>6} {' PROGRESS':<14} {'METRICS':>8} {'MEMO':>6}{RESET}")
    lines.append(hdr)
    lines.append(f"  {'─' * min(term_width - 4, 96)}")

    # Company rows
    for s in statuses:
        c = s["company"]
        meta = s["meta"]

        # Scrape status
        scrape_st = scrape_status_color(meta.get("last_scrape_status") if meta else None)
        last_scrape = format_time_ago(meta.get("last_scrape") if meta else None)

        # Download count
        dl_count = str(s["pdf_count"]) if s["pdf_count"] > 0 else f"{DIM}0{RESET}"

        # Parse progress
        total_parseable = s["pdf_count"]
        parsed_count = len(s["processed"])
        parse_str = f"{parsed_count}/{total_parseable}" if total_parseable > 0 else f"{DIM}0/0{RESET}"
        bar = progress_bar(parsed_count, total_parseable)

        # Metrics
        metric_str = str(s["metric_rows"]) if s["metric_rows"] > 0 else f"{DIM}0{RESET}"

        # Memo
        if s["memo_exists"]:
            memo_str = f"{GREEN}YES{RESET}"
        else:
            memo_str = f"{DIM}NO{RESET}"

        # Priority color
        pri = c.priority.upper()
        if pri == "HIGH":
            pri_str = f"{YELLOW}{pri:>4}{RESET}"
        else:
            pri_str = f"{DIM}{pri:>4}{RESET}"

        name = c.name[:21]
        # Dual-listing indicator
        dual = f" {CYAN}{c.us_ticker}{RESET}" if getattr(c, 'dual_listed', False) and getattr(c, 'us_ticker', None) else ""
        lines.append(
            f"  {name:<22} {pri_str}{dual} {scrape_st:>19} {last_scrape:>17} "
            f"{dl_count:>13} {parse_str:>15} {bar} {metric_str:>17} {memo_str:>15}"
        )

        # Show individual files if requested and they exist
        if show_files and s["pdf_names"]:
            for pdf in sorted(s["pdf_names"]):
                if pdf in s["processed"]:
                    icon = f"  {GREEN}✓{RESET}"
                elif pdf in s["unprocessed"]:
                    icon = f"  {YELLOW}○{RESET}"
                else:
                    icon = f"  {DIM}?{RESET}"
                # Truncate long filenames
                display_name = pdf[:60] if len(pdf) > 60 else pdf
                lines.append(f"  {DIM}{'':>22}{RESET} {icon} {DIM}{display_name}{RESET}")

    lines.append("")

    # Legend
    lines.append(f"  {DIM}Legend:  {GREEN}✓{RESET}{DIM} = parsed   "
                 f"{YELLOW}○{RESET}{DIM} = pending   "
                 f"DL = downloaded PDFs   "
                 f"METRICS = extracted data rows{RESET}")
    lines.append("")

    return "\n".join(lines)


def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="Pipeline Status Dashboard")
    parser.add_argument("--tier", choices=["high", "low"], help="Filter by priority tier")
    parser.add_argument("--company", help="Show single company details")
    parser.add_argument("--watch", nargs="?", const=5, type=int, metavar="SECONDS",
                        help="Auto-refresh (default: 5s)")
    parser.add_argument("--no-files", action="store_true", help="Hide individual file list")
    args = parser.parse_args()

    registry = CompanyRegistry()

    if args.company:
        companies = [registry.get(args.company)]
    elif args.tier:
        companies = registry.list_by_priority(args.tier)
    else:
        companies = registry.all()

    # Sort: high priority first, then alphabetical
    companies.sort(key=lambda c: (0 if c.priority == "high" else 1, c.name))

    show_files = not args.no_files

    if args.watch is not None:
        interval = max(1, args.watch)
        try:
            while True:
                clear_screen()
                output = render_dashboard(companies, show_files=show_files)
                print(output)
                print(f"  {DIM}Refreshing every {interval}s  |  Ctrl+C to exit{RESET}")
                time.sleep(interval)
        except KeyboardInterrupt:
            print(f"\n  {DIM}Dashboard stopped.{RESET}\n")
    else:
        output = render_dashboard(companies, show_files=show_files)
        print(output)


if __name__ == "__main__":
    main()
