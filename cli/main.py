#!/usr/bin/env python3
"""
Financial Data Pipeline CLI.
Usage: python -m cli.main <command> [options]
"""
import sys
import os
import asyncio
import argparse

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def cmd_run(args):
    """Run the pipeline for a company or tier."""
    from src.pipeline.orchestrator import run_pipeline, run_tier

    if args.tier:
        asyncio.run(run_tier(
            priority=args.tier,
            years_back=args.years,
            skip_scrape=args.skip_scrape,
            skip_analyze=args.skip_analyze,
        ))
    elif args.company:
        asyncio.run(run_pipeline(
            company_slug=args.company,
            years_back=args.years,
            skip_scrape=args.skip_scrape,
            skip_analyze=args.skip_analyze,
            dry_run=args.dry_run,
        ))
    else:
        print("Error: specify --company <slug> or --tier <high|low>")
        sys.exit(1)


def cmd_status(args):
    """Show pipeline status."""
    from src.registry.company import CompanyRegistry
    from src.storage.file_manager import FileManager

    registry = CompanyRegistry()
    companies = registry.all()

    if args.company:
        companies = [registry.get(args.company)]

    print(f"\n{'COMPANY':<30} | {'PRIORITY':<8} | {'LAST SCRAPE':<20} | {'REPORTS':<8} | {'METRICS':<8} | {'MEMO':<6}")
    print("-" * 95)

    for c in companies:
        fm = FileManager(c.slug)
        meta = fm.load_meta()
        financials = fm.load_financials()
        memo = fm.load_memo()

        last_scrape = meta.get("last_scrape", "Never")
        if last_scrape and last_scrape != "Never":
            last_scrape = last_scrape[:16]

        reports = meta.get("reports_downloaded", 0)
        has_memo = "YES" if memo else "NO"

        if args.failed and meta.get("last_scrape_status") != "failed":
            continue

        print(f"{c.name:<30} | {c.priority:<8} | {last_scrape:<20} | {reports:<8} | {len(financials):<8} | {has_memo:<6}")

    print()


def cmd_list(args):
    """List all companies."""
    from src.registry.company import CompanyRegistry

    registry = CompanyRegistry()
    companies = registry.all()

    if args.tier:
        companies = registry.list_by_priority(args.tier)

    print(f"\n{'SLUG':<15} | {'NAME':<35} | {'PRIORITY':<8} | {'TASE ID':<10} | {'CURRENCY':<8}")
    print("-" * 90)

    for c in companies:
        print(f"{c.slug:<15} | {c.name:<35} | {c.priority:<8} | {(c.tase_id or '-'):<10} | {c.reporting_currency:<8}")

    print(f"\nTotal: {len(companies)} companies\n")


def cmd_validate(args):
    """Validate pipeline outputs."""
    from src.registry.company import CompanyRegistry
    from src.storage.file_manager import FileManager
    from src.storage import paths
    import json

    registry = CompanyRegistry()

    if args.company:
        companies = [registry.get(args.company)]
    else:
        companies = registry.all()

    print(f"\n{'COMPANY':<30} | {'FINANCIALS':<12} | {'MEMO':<12} | {'STATUS'}")
    print("-" * 80)

    for c in companies:
        fm = FileManager(c.slug)

        # Check financials
        csv_path = paths.financials_csv(c.slug)
        if os.path.exists(csv_path) and os.path.getsize(csv_path) > 50:
            fin_status = "OK"
        elif os.path.exists(csv_path):
            fin_status = "EMPTY"
        else:
            fin_status = "MISSING"

        # Check memo
        memo_path = paths.memo_json(c.slug)
        if os.path.exists(memo_path):
            try:
                with open(memo_path) as f:
                    memo = json.load(f)
                memo_status = "OK" if memo.get("executive_summary") else "INCOMPLETE"
            except:
                memo_status = "INVALID"
        else:
            memo_status = "MISSING"

        overall = "PASS" if fin_status == "OK" and memo_status == "OK" else "FAIL"

        print(f"{c.name:<30} | {fin_status:<12} | {memo_status:<12} | {overall}")

    print()


def main():
    parser = argparse.ArgumentParser(description="Financial Data Pipeline CLI")
    subparsers = parser.add_subparsers(dest="command")

    # run
    run_parser = subparsers.add_parser("run", help="Run the pipeline")
    run_parser.add_argument("company", nargs="?", help="Company slug")
    run_parser.add_argument("--tier", choices=["high", "low"], help="Run all companies in tier")
    run_parser.add_argument("--years", type=int, default=1, help="Years to look back")
    run_parser.add_argument("--skip-scrape", action="store_true", help="Skip scraping step")
    run_parser.add_argument("--skip-analyze", action="store_true", help="Skip analysis step")
    run_parser.add_argument("--dry-run", action="store_true", help="Preview without changes")

    # status
    status_parser = subparsers.add_parser("status", help="Show pipeline status")
    status_parser.add_argument("company", nargs="?", help="Company slug")
    status_parser.add_argument("--failed", action="store_true", help="Show only failures")

    # list
    list_parser = subparsers.add_parser("list", help="List companies")
    list_parser.add_argument("--tier", choices=["high", "low"], help="Filter by tier")

    # validate
    validate_parser = subparsers.add_parser("validate", help="Validate outputs")
    validate_parser.add_argument("company", nargs="?", help="Company slug")
    validate_parser.add_argument("--all", action="store_true", dest="validate_all")

    # dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Live status dashboard")
    dash_parser.add_argument("--tier", choices=["high", "low"], help="Filter by tier")
    dash_parser.add_argument("--company", help="Single company")
    dash_parser.add_argument("--watch", nargs="?", const=5, type=int, metavar="SEC",
                             help="Auto-refresh (default: 5s)")
    dash_parser.add_argument("--no-files", action="store_true", help="Hide file list")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "dashboard":
        from cli.dashboard import main as dashboard_main
        sys.argv = ["dashboard"] + sys.argv[2:]  # pass remaining args
        dashboard_main()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
