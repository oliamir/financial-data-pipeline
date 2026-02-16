import asyncio
from typing import List

from .tase import TaseScraper
from .ir_generic import GenericIRScraper
from .base import BaseScraper
from ..models.report import ReportMetadata
from ..registry.company import Company
from ..storage.file_manager import FileManager
from ..storage import paths


class ScrapingCoordinator:
    """Runs scrapers with retries, deduplication, and health checks.

    Sources are tried in order:
      1. TASE Maya (primary for all TASE-listed companies)
      2. Company IR website (fallback / supplemental, if ir_url is set)

    Results from all sources are merged and deduplicated before download.
    """

    def __init__(self, company: Company):
        self.company = company
        self.file_manager = FileManager(company.slug)

    async def scrape_and_download(
        self,
        years_back: int = 5,
        financial_only: bool = True,
    ) -> List[ReportMetadata]:
        """Full scrape + download flow with retries."""

        # 1. Scrape report metadata from all sources
        all_reports = await self._scrape_all_sources(years_back)

        if not all_reports:
            print(f"  [Coordinator] No reports found for {self.company.name}", flush=True)
            self.file_manager.update_scrape_status(0, 0, [], "no_reports")
            return []

        # 2. Filter to financial reports only
        if financial_only:
            before = len(all_reports)
            all_reports = [r for r in all_reports if r.is_financial or "FINANCIAL" in r.period]
            print(f"  [Coordinator] Filtered to {len(all_reports)}/{before} financial reports", flush=True)

        # 3. Deduplicate
        all_reports = self._deduplicate(all_reports)

        # 4. Download
        downloaded = []
        failed = []
        output_dir = paths.reports_dir(self.company.slug)

        for report in all_reports:
            path = await self._download_with_retry(report, output_dir)
            if path:
                downloaded.append(report)
            else:
                failed.append(report.report_id or "unknown")

        print(f"  [Coordinator] Downloaded {len(downloaded)}/{len(all_reports)} reports", flush=True)

        # 5. Update meta
        self.file_manager.update_scrape_status(
            reports_found=len(all_reports),
            reports_downloaded=len(downloaded),
            failed=failed,
            status="success" if downloaded else "failed",
        )

        return downloaded

    async def _scrape_all_sources(self, years_back: int) -> List[ReportMetadata]:
        """Scrape TASE first, then IR website as fallback/supplement. Merge results."""
        all_reports: List[ReportMetadata] = []

        # Source 1: TASE Maya
        tase_reports = await self._scrape_tase_with_retry(years_back)
        if tase_reports:
            all_reports.extend(tase_reports)
            print(
                f"  [Coordinator] TASE returned {len(tase_reports)} reports",
                flush=True,
            )

        # Source 2: IR Website (if company has an ir_url configured)
        if self.company.ir_url:
            ir_reports = await self._scrape_ir_with_retry(years_back)
            if ir_reports:
                # Merge, avoiding URL-level duplicates across sources
                before = len(all_reports)
                all_reports = self._merge_cross_source(all_reports, ir_reports)
                added = len(all_reports) - before
                print(
                    f"  [Coordinator] IR website returned {len(ir_reports)} reports "
                    f"({added} new after cross-source dedup)",
                    flush=True,
                )
        else:
            print(
                f"  [Coordinator] No ir_url configured for {self.company.name}, "
                f"skipping IR scrape",
                flush=True,
            )

        return all_reports

    # ------------------------------------------------------------------
    # TASE scraping
    # ------------------------------------------------------------------

    async def _scrape_tase_with_retry(self, years_back: int, max_retries: int = 3) -> List[ReportMetadata]:
        """Scrape TASE Maya with exponential backoff retries."""
        # Health check first
        if not await self._check_tase_health():
            print(f"  [Coordinator] TASE Maya unreachable, skipping TASE scrape", flush=True)
            return []

        for attempt in range(max_retries):
            try:
                scraper = TaseScraper(
                    self.company.slug,
                    self.company.name,
                    self.company.tase_id,
                )
                reports = await scraper.fetch_reports(
                    years_back=years_back,
                    company_id=self.company.tase_company_id,
                )
                return reports
            except Exception as e:
                wait = 2**attempt * 5
                print(
                    f"  [Coordinator] TASE scrape attempt {attempt + 1} failed: {e}. "
                    f"Retry in {wait}s...",
                    flush=True,
                )
                await asyncio.sleep(wait)

        print(f"  [Coordinator] All TASE scrape attempts failed for {self.company.name}", flush=True)
        return []

    # ------------------------------------------------------------------
    # IR website scraping
    # ------------------------------------------------------------------

    async def _scrape_ir_with_retry(self, years_back: int, max_retries: int = 2) -> List[ReportMetadata]:
        """Scrape the company's IR website with retries."""
        for attempt in range(max_retries):
            try:
                scraper = GenericIRScraper(
                    company_slug=self.company.slug,
                    company_name=self.company.name,
                    ir_url=self.company.ir_url,
                    ir_profile=self.company.ir_platform or "generic",
                )
                reports = await scraper.fetch_reports(years_back=years_back)
                return reports
            except Exception as e:
                wait = 2**attempt * 5
                print(
                    f"  [Coordinator] IR scrape attempt {attempt + 1} failed: {e}. "
                    f"Retry in {wait}s...",
                    flush=True,
                )
                await asyncio.sleep(wait)

        print(f"  [Coordinator] All IR scrape attempts failed for {self.company.name}", flush=True)
        return []

    # ------------------------------------------------------------------
    # Downloads
    # ------------------------------------------------------------------

    async def _download_with_retry(self, report: ReportMetadata, output_dir: str, max_retries: int = 2) -> str:
        """Download a single report with retries.

        Picks the right scraper based on the report's source.
        """
        for attempt in range(max_retries):
            try:
                scraper = self._scraper_for_report(report)
                path = await scraper.download_report(report, output_dir)
                if path:
                    return path
            except Exception as e:
                wait = 2**attempt * 3
                print(
                    f"  [Coordinator] Download attempt {attempt + 1} failed: {e}. "
                    f"Retry in {wait}s...",
                    flush=True,
                )
                await asyncio.sleep(wait)

        return ""

    def _scraper_for_report(self, report: ReportMetadata) -> BaseScraper:
        """Return the appropriate scraper instance for downloading a report."""
        if report.source == "IR_Website":
            return GenericIRScraper(
                company_slug=self.company.slug,
                company_name=self.company.name,
                ir_url=self.company.ir_url or "",
                ir_profile=self.company.ir_platform or "generic",
            )
        # Default to TASE
        return TaseScraper(
            self.company.slug,
            self.company.name,
            self.company.tase_id,
        )

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    async def _check_tase_health(self) -> bool:
        """Verify TASE Maya is reachable."""
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                response = await page.goto("https://maya.tase.co.il", timeout=15000)
                await browser.close()
                ok = response and response.status == 200
                if ok:
                    print(f"  [Coordinator] TASE Maya health check: OK", flush=True)
                else:
                    print(
                        f"  [Coordinator] TASE Maya health check: FAILED "
                        f"(status={response.status if response else 'None'})",
                        flush=True,
                    )
                return ok
        except Exception as e:
            print(f"  [Coordinator] TASE Maya health check failed: {e}", flush=True)
            return False

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _deduplicate(self, reports: List[ReportMetadata]) -> List[ReportMetadata]:
        """Remove duplicate reports by (year, period, report_id)."""
        seen = {}
        for r in reports:
            key = (r.year, r.period, r.report_id)
            if key not in seen:
                seen[key] = r
        deduped = list(seen.values())
        if len(deduped) < len(reports):
            print(f"  [Coordinator] Deduplicated {len(reports)} -> {len(deduped)} reports", flush=True)
        return deduped

    @staticmethod
    def _merge_cross_source(
        existing: List[ReportMetadata],
        new_reports: List[ReportMetadata],
    ) -> List[ReportMetadata]:
        """Merge reports from different sources, deduplicating by URL.

        When the same URL appears from both TASE and IR, the TASE version is
        preferred (it typically has richer metadata).
        """
        seen_urls = set()
        for r in existing:
            normalized = r.url.split("#")[0].split("?")[0].rstrip("/").lower()
            seen_urls.add(normalized)

        merged = list(existing)
        for r in new_reports:
            normalized = r.url.split("#")[0].split("?")[0].rstrip("/").lower()
            if normalized not in seen_urls:
                seen_urls.add(normalized)
                merged.append(r)

        return merged
