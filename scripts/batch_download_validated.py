#!/usr/bin/env python3
"""Validated batch downloader — runs downloads for all high-priority companies,
validates results after each, and logs diagnostics for failures.

Usage:
    python -m scripts.batch_download_validated [--companies slug1,slug2] [--years 5]
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.config.loader import load_companies
from src.storage.paths import CompanyPaths
from src.pipeline.runner import run_company


def count_pdfs(reports_dir: Path) -> int:
    """Count PDF files in a directory."""
    if not reports_dir.exists():
        return 0
    return len(list(reports_dir.glob("*.pdf")))


def diagnose_failure(company, reports_dir: Path) -> str:
    """Diagnose why 0 files were downloaded for a company."""
    issues = []

    # Check TASE company ID
    if not company.tase_company_id:
        issues.append("NO_TASE_ID: Company has no tase_company_id configured")

    # Check if reports directory exists
    if not reports_dir.exists():
        issues.append("NO_REPORTS_DIR: Reports directory doesn't exist")

    # Check company type
    company_type = getattr(company, 'company_type', None)
    if company_type:
        issues.append(f"COMPANY_TYPE: {company_type}")

    # Check IR URL
    ir_url = getattr(company, 'ir_url', None)
    if not ir_url:
        issues.append("NO_IR_URL: No IR website URL configured")
    else:
        issues.append(f"IR_URL: {ir_url}")

    # Check for scratch directory leftovers (indicates downloader ran but no PDFs found)
    scratch_dir = reports_dir.parent / "_tase_scratch"
    if scratch_dir.exists():
        issues.append("SCRATCH_EXISTS: Scratch dir still exists (cleanup failed?)")

    if not issues:
        issues.append("UNKNOWN: No obvious configuration issue found")

    return " | ".join(issues)


async def run_download_validated(
    slugs: list[str] | None = None,
    years_back: int = 5,
):
    """Run downloads for each company with validation."""
    companies = load_companies()

    if slugs:
        targets = {s: companies[s] for s in slugs if s in companies}
    else:
        # High priority only
        targets = {s: c for s, c in companies.items() if c.priority.value == "high"}

    print(f"\n{'=' * 70}")
    print(f"VALIDATED BATCH DOWNLOAD — {len(targets)} companies")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Years back: {years_back}")
    print(f"{'=' * 70}\n")

    results = {}

    for i, (slug, company) in enumerate(targets.items(), 1):
        paths = CompanyPaths(slug)
        paths.ensure_dirs()
        reports_dir = paths.reports_dir

        # Count PDFs before download
        before_count = count_pdfs(reports_dir)

        print(f"[{i}/{len(targets)}] {slug} (TASE ID: {company.tase_company_id or 'N/A'})")
        print(f"  Before: {before_count} PDFs")

        start_time = time.time()

        try:
            job = await run_company(
                slug=slug,
                years_back=years_back,
                requested_steps=["download"],
            )
            status = job.status
        except Exception as e:
            status = f"error: {e}"
            print(f"  ERROR: {e}")

        elapsed = time.time() - start_time

        # Count PDFs after download
        after_count = count_pdfs(reports_dir)
        new_pdfs = after_count - before_count

        results[slug] = {
            "before": before_count,
            "after": after_count,
            "new": new_pdfs,
            "elapsed": elapsed,
            "status": status,
        }

        if new_pdfs > 0:
            print(f"  ✓ After: {after_count} PDFs (+{new_pdfs} new) [{elapsed:.0f}s]")
        elif before_count > 0:
            print(f"  ○ After: {after_count} PDFs (no new, {before_count} existing) [{elapsed:.0f}s]")
        else:
            # 0 files downloaded — diagnose
            diagnosis = diagnose_failure(company, reports_dir)
            print(f"  ✗ FAILED: 0 PDFs downloaded [{elapsed:.0f}s]")
            print(f"  DIAGNOSIS: {diagnosis}")
            results[slug]["diagnosis"] = diagnosis

        print()

    # Retry failed companies after cooldown (rate limiting protection)
    retry_slugs = [
        slug for slug, r in results.items()
        if r["new"] == 0 and r["before"] == 0
    ]

    if retry_slugs:
        cooldown_sec = 120
        print(f"\n{'=' * 70}")
        print(f"RETRYING {len(retry_slugs)} failed companies after {cooldown_sec}s cooldown...")
        print(f"Companies: {', '.join(retry_slugs)}")
        print(f"{'=' * 70}\n")

        # Clean up scratch dirs before retry
        for slug in retry_slugs:
            scratch = CompanyPaths(slug).root / "_tase_scratch"
            if scratch.exists():
                import shutil
                shutil.rmtree(str(scratch), ignore_errors=True)

        await asyncio.sleep(cooldown_sec)

        for i, slug in enumerate(retry_slugs, 1):
            company = targets[slug]
            paths = CompanyPaths(slug)
            reports_dir = paths.reports_dir
            before_count = count_pdfs(reports_dir)

            print(f"[RETRY {i}/{len(retry_slugs)}] {slug}")
            start_time = time.time()

            try:
                job = await run_company(
                    slug=slug,
                    years_back=years_back,
                    requested_steps=["download"],
                )
            except Exception as e:
                print(f"  RETRY ERROR: {e}")

            elapsed = time.time() - start_time
            after_count = count_pdfs(reports_dir)
            new_pdfs = after_count - before_count

            results[slug] = {
                "before": before_count,
                "after": after_count,
                "new": new_pdfs,
                "elapsed": elapsed,
                "status": "retry_success" if new_pdfs > 0 else "retry_failed",
            }

            if new_pdfs > 0:
                print(f"  ✓ RETRY SUCCESS: {after_count} PDFs (+{new_pdfs} new) [{elapsed:.0f}s]")
            else:
                diagnosis = diagnose_failure(company, reports_dir)
                print(f"  ✗ RETRY FAILED: still 0 PDFs [{elapsed:.0f}s]")
                print(f"  DIAGNOSIS: {diagnosis}")
                results[slug]["diagnosis"] = diagnosis

            print()

    # Final summary
    print(f"\n{'=' * 70}")
    print("DOWNLOAD SUMMARY")
    print(f"{'=' * 70}")

    total_new = 0
    failed = []
    for slug, r in results.items():
        icon = "✓" if r["new"] > 0 else ("○" if r["before"] > 0 else "✗")
        print(f"  {icon} {slug}: {r['after']} total PDFs (+{r['new']} new) [{r['elapsed']:.0f}s]")
        total_new += r["new"]
        if r["new"] == 0 and r["after"] == 0:
            failed.append(slug)

    print(f"\nTotal new PDFs: {total_new}")
    if failed:
        print(f"STILL FAILED companies (0 PDFs): {', '.join(failed)}")
    else:
        print("All companies have PDFs!")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 70}\n")

    return results, failed


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--companies", type=str, help="Comma-separated slugs")
    parser.add_argument("--years", type=int, default=5)
    args = parser.parse_args()

    slugs = args.companies.split(",") if args.companies else None
    asyncio.run(run_download_validated(slugs, args.years))
