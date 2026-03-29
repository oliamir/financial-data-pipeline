"""V3 Pipeline orchestrator — runs the full pipeline with step tracking.

Coordinates: scrape → classify → extract → KPI → memo
with PipelineJob tracking, step filtering, and ProgressTracker integration.

Supports:
    - ``--step download,parse,model,memo`` to run specific steps only
    - ``--reprocess`` to re-analyze already-processed files
    - ``--test-mode`` shortcut (1-year download + model + full-research memo)
    - Real-time progress emission via EventBus/ProgressTracker
"""

import asyncio
import os
import threading
from datetime import datetime
from typing import Optional, List, Set

from ..ai.registry import ProviderRegistry
from ..ai.task_router import TaskRouter
from ..config.loader import load_companies, load_providers_config
from ..models.company import Company
from ..models.job import PipelineJob, StepResult, StepName
from ..models.kpi import KPIMetrics
from ..models.memo import InvestmentMemo
from ..sources.coordinator import SourceCoordinator
from ..storage.file_manager import FileManager
from .steps import classify_document, is_financial_document
from .steps.extract import extract_financials
from .steps.memo import generate_memo
from .steps.kpi import calculate_kpis
from .steps.initial_research import run_initial_research
from ..utils.logging import get_logger

logger = get_logger(__name__)


# Valid step names for the --step flag
VALID_STEPS = {
    "download", "parse", "model", "memo",
    "initial_research",
}


class PipelineOrchestrator:
    """V3 pipeline orchestrator with step tracking, filtering, and progress.

    Stages:
        1. initial_research — web-based strategic research (Gemini)
        2. download — discover & fetch reports from sources
        3. parse — classify, extract financials, calculate KPIs (per file)
        4. model — build Excel financial model
        5. memo — generate/update investment memo
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
        self._tracker = None
        self._storage_lock = threading.Lock()

    def _get_tracker(self):
        """Lazy-load ProgressTracker to avoid import cycles."""
        if self._tracker is None:
            try:
                from ..progress import ProgressTracker
                self._tracker = ProgressTracker(self.company.slug)
            except ImportError:
                pass
        return self._tracker

    def _should_run_step(self, step: str, requested_steps: Optional[Set[str]]) -> bool:
        """Check if a step should run based on the filter."""
        if requested_steps is None:
            return True
        return step in requested_steps

    async def run(
        self,
        years_back: int = 5,
        skip_scrape: bool = False,
        skip_analyze: bool = False,
        dry_run: bool = False,
        initial_research: bool = False,
        requested_steps: Optional[List[str]] = None,
        reprocess: bool = False,
    ) -> PipelineJob:
        """Run the pipeline with optional step filtering.

        Args:
            years_back: How many years of history to fetch.
            skip_scrape: Skip document discovery and download.
            skip_analyze: Skip AI analysis (classify, extract, memo).
            dry_run: Log actions without executing.
            initial_research: Force initial research even if already done.
            requested_steps: List of step names to run (None = all).
                Valid steps: download, parse, model, memo, initial_research
            reprocess: Re-analyze already-processed files.

        Returns:
            PipelineJob with step results.
        """
        # Convert step list to set for fast lookup
        step_filter: Optional[Set[str]] = None
        if requested_steps:
            step_filter = set(requested_steps)
            unknown = step_filter - VALID_STEPS
            if unknown:
                raise ValueError(
                    f"Unknown steps: {unknown}. Valid: {sorted(VALID_STEPS)}"
                )
            self.job.requested_steps = [
                StepName(s) for s in requested_steps
                if s in [e.value for e in StepName]
            ]

        logger.info(f"\n{'=' * 60}")
        logger.info(f"PIPELINE: {self.company.name}")
        logger.info(f"Providers: {self.registry.available()}")
        if step_filter:
            logger.info(f"Steps: {sorted(step_filter)}")
        if reprocess:
            logger.info("Mode: REPROCESS (re-analyzing processed files)")
        logger.info(f"{'=' * 60}\n")

        # Start progress tracking
        tracker = self._get_tracker()
        if tracker:
            tracker.start_pipeline(requested_steps)

        try:
            # Stage 0: Initial Research (if requested or first run)
            if self._should_run_step("initial_research", step_filter):
                if initial_research or (not self.storage.load_memo()):
                    await self._run_initial_research(dry_run)
                elif step_filter and "initial_research" in step_filter:
                    # Explicitly requested even if already done
                    await self._run_initial_research(dry_run)
            elif step_filter:
                logger.info("[0/6] Initial research skipped (not in requested steps)")

            # Stage 1-2: Discover & Download
            if self._should_run_step("download", step_filter) and not skip_scrape:
                await self._run_scrape(years_back, dry_run)
            elif not skip_scrape and not step_filter:
                pass  # Normal flow, scrape already handled above
            else:
                logger.info("[1/6] Download skipped")
                self.job.steps.append(StepResult(
                    step=StepName.DOWNLOAD,
                    status="skipped",
                ))
                if tracker:
                    tracker.skip_step("download", "Not in requested steps")

            # Stage 3: Parse (classify + extract + KPI per file)
            if self._should_run_step("parse", step_filter) and not skip_analyze:
                await self._run_analysis(dry_run, reprocess=reprocess)
            elif not skip_analyze and not step_filter:
                pass  # Normal flow
            else:
                logger.info("[2/6] Parse/analysis skipped")
                if tracker:
                    tracker.skip_step("parse", "Not in requested steps")

            # Stage 4: Model (Excel)
            if self._should_run_step("model", step_filter):
                await self._run_model(dry_run)

            # Stage 5: Memo
            if self._should_run_step("memo", step_filter):
                # Memo can run independently with web research only
                if step_filter and "memo" in step_filter and "parse" not in (step_filter or set()):
                    await self._run_memo_standalone(dry_run)

            self.job.status = "complete"

            if tracker:
                tracker.complete_pipeline()

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self.job.status = "failed"
            self.job.error = str(e)

            if tracker:
                tracker.fail_pipeline(str(e))

        self.job.finished_at = datetime.now()
        self._print_summary()

        # Cleanup tracker
        if tracker:
            tracker.cleanup()

        return self.job

    async def _run_scrape(self, years_back: int, dry_run: bool) -> List[str]:
        """Run document discovery and download."""
        logger.info("[1/6] Discovering & downloading reports...")
        tracker = self._get_tracker()
        if tracker:
            tracker.start_step("download", "Discovering documents...")

        coordinator = SourceCoordinator(
            company=self.company,
            years_back=years_back,
            financial_only=True,
        )

        documents = await coordinator.discover_all()

        if tracker:
            tracker.update_step("download", f"Discovered {len(documents)} documents")

        self.job.steps.append(StepResult(
            step=StepName.DOWNLOAD,
            status="success",
            detail=f"Discovered {len(documents)} documents",
        ))

        if dry_run:
            for doc in documents:
                logger.info(f"  [DRY RUN] Would download: {doc.description}")
            if tracker:
                tracker.complete_step("download", f"Dry run: {len(documents)} documents")
            return []

        results = await coordinator.download_all(documents)
        downloaded = list(results.values())
        logger.info(f"  Downloaded {len(downloaded)} reports\n")

        if tracker:
            tracker.complete_step("download", f"Downloaded {len(downloaded)} reports")

        return downloaded

    async def _run_analysis(self, dry_run: bool, reprocess: bool = False) -> None:
        """Run AI analysis on reports.

        Args:
            dry_run: Log without executing.
            reprocess: If True, re-analyze already-processed files too.
        """
        if reprocess:
            # Get ALL report files, not just unprocessed
            reports_dir = self.storage.paths.reports_dir
            if reports_dir.exists():
                all_reports = sorted(reports_dir.glob("*.pdf"))
                unprocessed = all_reports
                logger.info(f"[2/6] REPROCESSING all {len(unprocessed)} reports...")
            else:
                unprocessed = []
        else:
            unprocessed = self.storage.get_unprocessed_reports()

        logger.info(f"[2/6] Analyzing {len(unprocessed)} {'total' if reprocess else 'unprocessed'} reports...")

        tracker = self._get_tracker()
        if tracker:
            tracker.start_step("parse", f"Analyzing {len(unprocessed)} reports")

        concurrency = int(os.environ.get("PARSE_CONCURRENCY", "1"))

        if concurrency > 1:
            logger.info(f"  Parallel mode: {concurrency} concurrent workers")
            semaphore = asyncio.Semaphore(concurrency)
            done_count = 0

            async def _process_with_semaphore(idx, fp):
                nonlocal done_count
                async with semaphore:
                    filename = os.path.basename(str(fp))
                    if dry_run:
                        logger.info(f"  [DRY RUN] Would analyze: {filename}")
                        return
                    try:
                        await asyncio.to_thread(self._process_single_report_sync, str(fp))
                    except Exception as e:
                        logger.error(f"  Failed to process {filename}: {e}")
                    done_count += 1
                    if tracker:
                        tracker.update_step("parse", f"Processed {done_count}/{len(unprocessed)}")

            tasks = [
                _process_with_semaphore(i, fp)
                for i, fp in enumerate(unprocessed, 1)
            ]
            await asyncio.gather(*tasks)
        else:
            for i, file_path in enumerate(unprocessed, 1):
                filename = os.path.basename(str(file_path))

                if tracker:
                    tracker.update_step("parse", f"Processing {i}/{len(unprocessed)}: {filename}")

                if dry_run:
                    logger.info(f"  [DRY RUN] Would analyze: {filename}")
                    continue

                try:
                    await self._process_single_report(str(file_path))
                except Exception as e:
                    logger.error(f"  Failed to process {filename}: {e}")

        if tracker:
            tracker.complete_step("parse", f"Analyzed {len(unprocessed)} reports")

    def _process_single_report_sync(self, file_path: str) -> None:
        """Thread-safe synchronous version for parallel processing."""
        filename = os.path.basename(file_path)
        logger.info(f"\n  Processing: {filename}")

        # Step 1: Classify (thread-safe, no shared state)
        doc_type = classify_document(self.router, file_path)
        with self._storage_lock:
            self.job.steps.append(StepResult(
                step=StepName.CLASSIFY,
                status="success",
                detail=f"{filename}: {doc_type}",
            ))

        if not is_financial_document(doc_type):
            with self._storage_lock:
                self.storage.mark_processed(file_path)
            logger.info(f"  → Skipped (type: {doc_type})")
            return

        # Step 2: Extract financials (thread-safe, no shared state)
        period = extract_financials(self.router, file_path, self.company.slug)
        if not period:
            with self._storage_lock:
                self.job.steps.append(StepResult(
                    step=StepName.EXTRACT,
                    status="failed",
                    detail=f"{filename}: extraction returned None",
                ))
                self.storage.mark_processed(file_path)
            return

        with self._storage_lock:
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

        # Step 5: Generate/update memo (skip if SKIP_PARSE_MEMO is set)
        if not os.environ.get("SKIP_PARSE_MEMO"):
            with self._storage_lock:
                current_memo = self.storage.load_memo()
            memo = generate_memo(self.router, file_path, self.company.slug, current_memo)
            if memo:
                with self._storage_lock:
                    self.storage.save_memo(memo)
                    self.job.steps.append(StepResult(
                        step=StepName.MEMO,
                        status="success",
                        detail=f"Recommendation: {memo.recommendation}",
                    ))
        else:
            logger.debug("Skipping per-report memo (SKIP_PARSE_MEMO set)")

        # Mark complete
        with self._storage_lock:
            self.storage.mark_processed(file_path)
        logger.info(f"  → Done: {filename}")

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

        # Step 5: Generate/update memo (skip if SKIP_PARSE_MEMO is set)
        if not os.environ.get("SKIP_PARSE_MEMO"):
            current_memo = self.storage.load_memo()
            memo = generate_memo(self.router, file_path, self.company.slug, current_memo)
            if memo:
                self.storage.save_memo(memo)
                self.job.steps.append(StepResult(
                    step=StepName.MEMO,
                    status="success",
                    detail=f"Recommendation: {memo.recommendation}",
                ))
        else:
            logger.debug("Skipping per-report memo (SKIP_PARSE_MEMO set)")

        # Mark complete
        self.storage.mark_processed(file_path)
        logger.info(f"  → Done: {filename}")

    async def _run_model(self, dry_run: bool) -> None:
        """Build the Excel financial model."""
        logger.info("[3/6] Building Excel financial model...")

        tracker = self._get_tracker()
        if tracker:
            tracker.start_step("model", "Building Excel model...")

        if dry_run:
            logger.info("  [DRY RUN] Would build Excel model")
            if tracker:
                tracker.complete_step("model", "Dry run")
            return

        try:
            from ..excel import ExcelModelBuilder
            builder = ExcelModelBuilder(self.company.slug)
            path = builder.build()
            self.job.steps.append(StepResult(
                step=StepName.MODEL,
                status="success",
                detail=f"Model saved: {os.path.basename(path)}",
            ))
            logger.info(f"  → Excel model saved: {path}")

            if tracker:
                tracker.complete_step("model", f"Saved: {os.path.basename(path)}")

        except Exception as e:
            logger.error(f"  Excel model build failed: {e}")
            self.job.steps.append(StepResult(
                step=StepName.MODEL,
                status="failed",
                detail=str(e),
            ))
            if tracker:
                tracker.fail_step("model", str(e))

    async def _run_memo_standalone(self, dry_run: bool) -> None:
        """Run memo generation independently (web research only, no files needed)."""
        logger.info("[4/6] Generating investment memo (standalone mode)...")

        tracker = self._get_tracker()
        if tracker:
            tracker.start_step("memo", "Generating memo with web research...")

        if dry_run:
            logger.info("  [DRY RUN] Would generate standalone memo")
            if tracker:
                tracker.complete_step("memo", "Dry run")
            return

        try:
            # Ensure initial research is available
            existing_memo = self.storage.load_memo()
            if not existing_memo or not existing_memo.initial_research.generated_at:
                logger.info("  Running initial research first...")
                await self._run_initial_research(dry_run=False)
                existing_memo = self.storage.load_memo()

            # Find the most recent report file for memo generation
            reports_dir = self.storage.paths.reports_dir
            report_files = sorted(reports_dir.glob("*.pdf")) if reports_dir.exists() else []

            if report_files:
                # Use the most recent file
                file_path = str(report_files[-1])
                memo = generate_memo(
                    self.router, file_path, self.company.slug, existing_memo
                )
                if memo:
                    self.storage.save_memo(memo)
                    self.job.steps.append(StepResult(
                        step=StepName.MEMO,
                        status="success",
                        detail=f"Standalone memo: {memo.recommendation}",
                    ))
                    if tracker:
                        tracker.complete_step("memo", f"Recommendation: {memo.recommendation}")
            else:
                logger.warning("  No report files available for memo generation")
                self.job.steps.append(StepResult(
                    step=StepName.MEMO,
                    status="failed",
                    detail="No report files available",
                ))
                if tracker:
                    tracker.fail_step("memo", "No report files available")

        except Exception as e:
            logger.error(f"  Standalone memo failed: {e}")
            if tracker:
                tracker.fail_step("memo", str(e))

    async def _run_initial_research(self, dry_run: bool) -> None:
        """Run strategic initial research with Gemini deep thinking."""
        # Check if already done
        existing_memo = self.storage.load_memo()
        if existing_memo and existing_memo.initial_research.generated_at:
            logger.info("[0/6] Initial research already completed, skipping")
            self.job.steps.append(StepResult(
                step=StepName.INITIAL_RESEARCH,
                status="skipped",
                detail="Already completed",
            ))
            return

        logger.info(f"[0/6] Running initial strategic research for {self.company.name}...")

        tracker = self._get_tracker()
        if tracker:
            tracker.start_step("initial_research", "Running strategic research...")

        if dry_run:
            logger.info("  [DRY RUN] Would run 5 strategic research prompts")
            if tracker:
                tracker.complete_step("initial_research", "Dry run")
            return

        research = run_initial_research(self.company)
        if research:
            memo = existing_memo or InvestmentMemo(company_slug=self.company.slug)
            memo.initial_research = research
            self.storage.save_memo(memo)
            self.job.steps.append(StepResult(
                step=StepName.INITIAL_RESEARCH,
                status="success",
                detail=f"5 prompts completed via {research.model_used}",
            ))
            logger.info("  → Initial research saved")
            if tracker:
                tracker.complete_step("initial_research", f"Via {research.model_used}")
        else:
            self.job.steps.append(StepResult(
                step=StepName.INITIAL_RESEARCH,
                status="failed",
                detail="No GOOGLE_API_KEY or provider error",
            ))
            if tracker:
                tracker.fail_step("initial_research", "No API key or provider error")

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
    initial_research: bool = False,
    requested_steps: Optional[List[str]] = None,
    reprocess: bool = False,
) -> PipelineJob:
    """Run pipeline for a single company by slug.

    Args:
        slug: Company identifier.
        years_back: Years of history to fetch.
        skip_scrape: Skip document download.
        skip_analyze: Skip AI analysis.
        provider_override: Force a specific AI provider.
        dry_run: Log without executing.
        initial_research: Force initial research.
        requested_steps: List of step names to run (None = all).
        reprocess: Re-analyze already-processed files.

    Returns:
        PipelineJob with results.
    """
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
        initial_research=initial_research,
        requested_steps=requested_steps,
        reprocess=reprocess,
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
