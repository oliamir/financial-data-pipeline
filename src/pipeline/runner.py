"""V3 Pipeline orchestrator — runs the full pipeline with step tracking.

Coordinates: scrape → classify → extract → KPI → memo → drive upload
with PipelineJob tracking for progress visibility.
"""

import asyncio
import os
from datetime import datetime
from typing import Optional, List

from ..ai.registry import ProviderRegistry
from ..ai.task_router import TaskRouter
from ..config.loader import load_companies, load_providers_config
from ..models.company import Company
from ..models.job import PipelineJob, StepResult, StepName
from ..models.kpi import KPIMetrics
from ..sources.coordinator import SourceCoordinator
from ..storage.file_manager import FileManager
from .steps import classify_document, is_financial_document
from .steps.extract import extract_financials
from .steps.memo import generate_memo
from .steps.kpi import calculate_kpis
from ..utils.logging import get_logger

logger = get_logger(__name__)


class PipelineOrchestrator:
    """V3 pipeline orchestrator with step tracking and PipelineJob progress.

    Stages:
        1. Discover — find documents from all sources
        2. Download — fetch reports to local storage
        3. Classify — AI document classification
        4. Extract — AI financial data extraction
        5. KPI — ratio calculations
        6. Memo — AI investment memo generation
        7. Upload — Google Drive upload (optional)
    """

    def __init__(
        self,
        company: Company,
        registry: Optional[ProviderRegistry] = None,
        override_provider: Optional[str] = None,
    ):
        self.company = company
        self.registry = registry or ProviderRegistry()
        self.router = TaskRouter(
            self.registry,
            override_provider=override_provider,
        )
        self.storage = FileManager(company.slug)
        self.job = PipelineJob(
            company_slug=company.slug,
            started_at=datetime.now(),
        )

    async def run(
        self,
        years_back: int = 5,
        skip_scrape: bool = False,
        skip_analyze: bool = False,
        skip_upload: bool = True,
        dry_run: bool = False,
    ) -> PipelineJob:
        """Run the full pipeline.

        Args:
            years_back: How many years of history to fetch.
            skip_scrape: Skip document discovery and download.
            skip_analyze: Skip AI analysis (classify, extract, memo).
            skip_upload: Skip Google Drive upload.
            dry_run: Log actions without executing.

        Returns:
            PipelineJob with step results.
        """
        logger.info(f"\n{'=' * 60}")
        logger.info(f"PIPELINE: {self.company.name}")
        logger.info(f"Providers: {self.registry.available()}")
        logger.info(f"{'=' * 60}\n")

        try:
            # Stage 1-2: Discover & Download
            downloaded_files = []
            if not skip_scrape:
                downloaded_files = await self._run_scrape(years_back, dry_run)
            else:
                logger.info("[1/6] Scrape skipped")
                self.job.steps.append(StepResult(
                    step=StepName.DOWNLOAD,
                    status="skipped",
                ))

            # Stage 3-6: Analyze
            if not skip_analyze:
                await self._run_analysis(dry_run)
            else:
                logger.info("[2/6] Analysis skipped")

            self.job.status = "complete"

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self.job.status = "failed"
            self.job.error = str(e)

        self.job.finished_at = datetime.now()
        self._print_summary()
        return self.job

    async def _run_scrape(self, years_back: int, dry_run: bool) -> List[str]:
        """Run document discovery and download."""
        logger.info("[1/6] Discovering & downloading reports...")

        coordinator = SourceCoordinator(
            company=self.company,
            years_back=years_back,
            financial_only=True,
        )

        documents = await coordinator.discover_all()
        self.job.steps.append(StepResult(
            step=StepName.DOWNLOAD,
            status="success",
            detail=f"Discovered {len(documents)} documents",
        ))

        if dry_run:
            for doc in documents:
                logger.info(f"  [DRY RUN] Would download: {doc.description}")
            return []

        results = await coordinator.download_all(documents)
        downloaded = list(results.values())
        logger.info(f"  Downloaded {len(downloaded)} reports\n")
        return downloaded

    async def _run_analysis(self, dry_run: bool) -> None:
        """Run AI analysis on unprocessed reports."""
        unprocessed = self.storage.get_unprocessed_reports()
        logger.info(f"[2/6] Analyzing {len(unprocessed)} unprocessed reports...")

        for file_path in unprocessed:
            filename = os.path.basename(str(file_path))

            if dry_run:
                logger.info(f"  [DRY RUN] Would analyze: {filename}")
                continue

            try:
                await self._process_single_report(str(file_path))
            except Exception as e:
                logger.error(f"  Failed to process {filename}: {e}")

    async def _process_single_report(self, file_path: str) -> None:
        """Process a single report through classify → extract → KPI → memo."""
        filename = os.path.basename(file_path)
        logger.info(f"\n  Processing: {filename}")

        # Step 1: Classify
        doc_type = classify_document(self.router, file_path)
        self.job.steps.append(StepResult(
            step=StepName.CLASSIFY,
            status="success",
            detail=f"{filename}: {doc_type}",
        ))

        if not is_financial_document(doc_type):
            self.storage.mark_processed(file_path)
            logger.info(f"  → Skipped (type: {doc_type})")
            return

        # Step 2: Extract financials
        period = extract_financials(self.router, file_path, self.company.slug)
        if not period:
            self.job.steps.append(StepResult(
                step=StepName.EXTRACT,
                status="failed",
                detail=f"{filename}: extraction returned None",
            ))
            self.storage.mark_processed(file_path)
            return

        self.job.steps.append(StepResult(
            step=StepName.EXTRACT,
            status="success",
            detail=f"{filename}: {period.period_type} {period.fiscal_year}",
        ))

        # Step 3: Save financials
        self.storage.append_financial(period)

        # Step 4: Calculate KPIs
        financials = self.storage.load_financials()
        prior = self._find_prior_period(financials, period)
        kpi = calculate_kpis(period, prior)
        self.storage.save_kpis(kpi)
        self.job.steps.append(StepResult(
            step=StepName.KPI,
            status="success",
        ))

        # Step 5: Generate/update memo
        current_memo = self.storage.load_memo()
        memo = generate_memo(self.router, file_path, self.company.slug, current_memo)
        if memo:
            self.storage.save_memo(memo)
            self.job.steps.append(StepResult(
                step=StepName.MEMO,
                status="success",
                detail=f"Recommendation: {memo.recommendation}",
            ))

        # Mark complete
        self.storage.mark_processed(file_path)
        logger.info(f"  → Done: {filename}")

    def _find_prior_period(self, financials, current):
        """Find the prior period for growth calculations."""
        for p in financials:
            if (p.fiscal_year == current.fiscal_year - 1
                    and p.period_type == current.period_type):
                return p
        return None

    def _print_summary(self):
        """Print pipeline summary."""
        logger.info(f"\n{'=' * 60}")
        logger.info(f"SUMMARY: {self.company.name}")
        logger.info(f"  Status: {self.job.status}")
        logger.info(f"  Steps: {len(self.job.steps)}")
        for step in self.job.steps:
            status_icon = "✓" if step.status == "success" else "✗" if step.status == "failed" else "○"
            logger.info(f"    {status_icon} {step.step}: {step.detail or ''}")
        if self.job.finished_at and self.job.started_at:
            elapsed = (self.job.finished_at - self.job.started_at).total_seconds()
            logger.info(f"  Duration: {elapsed:.1f}s")
        logger.info(f"{'=' * 60}\n")


# --- Convenience entry points ---

async def run_company(
    slug: str,
    years_back: int = 5,
    skip_scrape: bool = False,
    skip_analyze: bool = False,
    provider_override: Optional[str] = None,
    dry_run: bool = False,
) -> PipelineJob:
    """Run pipeline for a single company by slug."""
    companies = load_companies()
    if slug not in companies:
        raise KeyError(f"Company '{slug}' not found. Available: {list(companies.keys())}")

    company = companies[slug]
    orchestrator = PipelineOrchestrator(
        company,
        override_provider=provider_override,
    )
    return await orchestrator.run(
        years_back=years_back,
        skip_scrape=skip_scrape,
        skip_analyze=skip_analyze,
        dry_run=dry_run,
    )


async def run_all(
    priority: Optional[str] = None,
    years_back: int = 5,
    max_concurrent: int = 3,
) -> List[PipelineJob]:
    """Run pipeline for multiple companies."""
    companies = load_companies()

    if priority:
        companies = {k: v for k, v in companies.items() if v.priority.value == priority}

    logger.info(f"Running pipeline for {len(companies)} companies")

    jobs = []
    for slug, company in companies.items():
        orchestrator = PipelineOrchestrator(company)
        job = await orchestrator.run(years_back=years_back)
        jobs.append(job)

    return jobs
