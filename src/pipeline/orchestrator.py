import asyncio
import os
from datetime import datetime
from typing import Optional

from ..registry.company import Company, CompanyRegistry
from ..registry.priority import get_policy
from ..ai.providers import ProviderRegistry
from ..ai.router import TaskRouter
from ..scrapers.coordinator import ScrapingCoordinator
from ..storage.file_manager import FileManager
from ..storage import paths
from ..models.revision import RevisionEntry


class PipelineOrchestrator:
    """Main pipeline: scrape -> download -> analyze -> output."""

    def __init__(self, company: Company, providers: Optional[ProviderRegistry] = None):
        self.company = company
        self.policy = get_policy(company.priority)
        self.providers = providers or ProviderRegistry()
        self.router = TaskRouter(self.providers, self.policy)
        self.storage = FileManager(company.slug)
        self.coordinator = ScrapingCoordinator(company)

    async def run(
        self,
        years_back: int = 5,
        skip_scrape: bool = False,
        skip_analyze: bool = False,
        dry_run: bool = False,
    ):
        print(f"\n{'=' * 60}")
        print(f"PIPELINE: {self.company.name}")
        print(f"Priority: {self.company.priority} | Providers: {self.providers.available()}")
        print(f"{'=' * 60}\n")

        # Phase 1: Scrape & Download
        if not skip_scrape:
            print(f"[1/3] Scraping & Downloading...")
            downloaded = await self.coordinator.scrape_and_download(
                years_back=years_back,
                financial_only=True,
            )
            print(f"  Downloaded {len(downloaded)} reports\n")
        else:
            print(f"[1/3] Scraping skipped\n")

        # Phase 2: Analyze
        if not skip_analyze:
            print(f"[2/3] Analyzing reports...")
            unprocessed = self.storage.get_unprocessed_reports()
            print(f"  Found {len(unprocessed)} unprocessed files")

            for file_path in unprocessed:
                if dry_run:
                    print(f"  [DRY RUN] Would process: {os.path.basename(file_path)}")
                    continue
                await self._process_report(file_path)

            print()
        else:
            print(f"[2/3] Analysis skipped\n")

        # Phase 3: Summary
        print(f"[3/3] Pipeline complete")
        self._print_summary()

    async def _process_report(self, file_path: str):
        filename = os.path.basename(file_path)
        print(f"\n  Processing: {filename}")

        try:
            # 1. Classify
            print(f"  -> Classifying...")
            doc_type = self.router.classify(file_path)
            print(f"     Type: {doc_type}")

            if doc_type != "financial_report":
                self.storage.mark_processed(file_path)
                print(f"  -> Skipped (not a financial report)")
                return

            # 2. Extract financials
            print(f"  -> Extracting financials...")
            metrics, provider_name = self.router.extract(file_path, self.company.slug)
            print(f"     Extracted {len(metrics)} metrics via {provider_name}")

            if metrics:
                # 3. Check for revisions
                existing = self.storage.load_financials()
                revisions = self._detect_revisions(existing, metrics, filename)

                # 4. Save financials
                self.storage.append_financials(metrics)
                if revisions:
                    self.storage.append_revisions(revisions)
                    print(f"     Logged {len(revisions)} revisions")

            # 5. Update memo
            print(f"  -> Updating investment memo...")
            current_memo = self.storage.load_memo()
            memo = self.router.write_memo(file_path, self.company.slug, current_memo)
            self.storage.save_memo(memo)
            print(f"     Memo updated (status: {memo.thesis_status})")

            # 6. Mark processed
            self.storage.mark_processed(file_path)
            print(f"  -> Done")

        except Exception as e:
            print(f"  -> ERROR: {e}")
            import traceback
            traceback.print_exc()

    def _detect_revisions(self, existing: list, new_metrics: list, source_file: str) -> list:
        """Compare new extraction against existing data to detect changes."""
        revisions = []
        now = datetime.now().isoformat()

        # Build lookup of existing values
        existing_lookup = {}
        for row in existing:
            key = (row.get("metric_name"), row.get("period_type"), str(row.get("fiscal_year")))
            existing_lookup[key] = row.get("value")

        for metric in new_metrics:
            key = (metric.metric_name, metric.period_type, str(metric.fiscal_year))
            if key in existing_lookup:
                old_val = existing_lookup[key]
                new_val = metric.value
                if old_val is not None and new_val is not None:
                    try:
                        if abs(float(old_val) - float(new_val)) > 0.01:
                            revisions.append(RevisionEntry(
                                timestamp=now,
                                company_slug=self.company.slug,
                                metric_name=metric.metric_name,
                                period=f"{metric.period_type}_{metric.fiscal_year}",
                                old_value=float(old_val),
                                new_value=float(new_val),
                                reason=f"New extraction from {source_file}",
                                source_file=source_file,
                                provider=metric.source_provider,
                            ))
                    except (ValueError, TypeError):
                        pass

        return revisions

    def _print_summary(self):
        """Print pipeline summary."""
        meta = self.storage.load_meta()
        financials = self.storage.load_financials()
        memo = self.storage.load_memo()

        print(f"\n{'=' * 60}")
        print(f"SUMMARY: {self.company.name}")
        print(f"  Last scrape: {meta.get('last_scrape', 'Never')}")
        print(f"  Reports downloaded: {meta.get('reports_downloaded', 0)}")
        print(f"  Financial metrics: {len(financials)} rows")
        print(f"  Memo: {'EXISTS' if memo else 'MISSING'}")
        if memo:
            print(f"    Recommendation: {memo.get('recommendation', 'N/A')}")
            print(f"    Thesis status: {memo.get('thesis_status', 'N/A')}")
        print(f"{'=' * 60}\n")


async def run_pipeline(
    company_slug: str,
    years_back: int = 5,
    skip_scrape: bool = False,
    skip_analyze: bool = False,
    dry_run: bool = False,
    provider_override: str = None,
):
    """Convenience function to run the pipeline for a single company."""
    registry = CompanyRegistry()
    company = registry.get(company_slug)

    providers = ProviderRegistry()
    orchestrator = PipelineOrchestrator(company, providers)

    await orchestrator.run(
        years_back=years_back,
        skip_scrape=skip_scrape,
        skip_analyze=skip_analyze,
        dry_run=dry_run,
    )


async def run_tier(
    priority: str,
    years_back: int = 5,
    skip_scrape: bool = False,
    skip_analyze: bool = False,
):
    """Run the pipeline for all companies in a priority tier."""
    registry = CompanyRegistry()
    companies = registry.list_by_priority(priority)
    providers = ProviderRegistry()

    print(f"\nRunning pipeline for {len(companies)} {priority}-priority companies\n")

    for i, company in enumerate(companies):
        print(f"\n[{i + 1}/{len(companies)}] {company.name}")
        orchestrator = PipelineOrchestrator(company, providers)
        await orchestrator.run(
            years_back=years_back,
            skip_scrape=skip_scrape,
            skip_analyze=skip_analyze,
        )
