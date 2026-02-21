"""TASE Maya document source.

Discovers and downloads financial reports from the Tel Aviv Stock Exchange
Maya system. Ported from src/scrapers/tase.py with date range filtering.
"""

import os
import asyncio
from datetime import date, datetime
from typing import List, Optional

from .base import BaseSource
from ..models.document import DocumentMetadata, DocumentType
from ..models.company import Company
from ..utils.logging import get_logger

logger = get_logger(__name__)

# TASE Maya API base URL
TASE_API_BASE = "https://maya.tase.co.il/api/company"


class TASESource(BaseSource):
    """TASE Maya document source for Israeli-listed companies."""

    name = "tase_maya"

    def __init__(self, company: Company):
        super().__init__(company)
        self.tase_company_id = company.tase_company_id
        self.tase_id = company.tase_id

    async def discover(
        self,
        years_back: int = 5,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[DocumentMetadata]:
        """Discover reports from TASE Maya API."""
        if not self.tase_company_id:
            logger.warning(f"No TASE company ID for {self.company.slug}, skipping TASE source")
            return []

        documents = []
        current_year = datetime.now().year
        start_year = from_date.year if from_date else current_year - years_back
        end_year = to_date.year if to_date else current_year

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                for page_num in range(1, 9):  # Max 8 pages
                    url = (
                        f"{TASE_API_BASE}/{self.tase_company_id}/reports"
                        f"?page={page_num}&pageSize=20"
                    )
                    try:
                        await page.goto(url, timeout=30000)
                        content = await page.content()

                        # Parse the API response for report entries
                        import json
                        import re

                        # Extract JSON from page content
                        json_match = re.search(r'\{.*\}', content, re.DOTALL)
                        if not json_match:
                            break

                        data = json.loads(json_match.group())
                        reports = data.get("Reports", data.get("reports", []))

                        if not reports:
                            break

                        for report in reports:
                            year = self._extract_year_from_report(report)
                            if not self._within_date_range(year, from_date, to_date):
                                continue

                            doc = self._report_to_document(report, year)
                            if doc:
                                documents.append(doc)

                    except Exception as e:
                        logger.warning(f"TASE page {page_num} failed: {e}")
                        break

                await browser.close()

        except Exception as e:
            logger.error(f"TASE discovery failed for {self.company.slug}: {e}")

        logger.info(f"TASE: Discovered {len(documents)} documents for {self.company.slug}")
        return documents

    async def download(
        self,
        document: DocumentMetadata,
        output_dir: str,
    ) -> Optional[str]:
        """Download a report from TASE."""
        os.makedirs(output_dir, exist_ok=True)

        filename = f"{document.year}_{document.period}_{document.report_id or 'report'}.pdf"
        output_path = os.path.join(output_dir, filename)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            logger.debug(f"Already downloaded: {filename}")
            return output_path

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                response = await page.goto(document.url, timeout=30000)
                if response and response.ok:
                    content = await response.body()
                    with open(output_path, "wb") as f:
                        f.write(content)

                    if self.validate_pdf(output_path):
                        logger.info(f"Downloaded: {filename}")
                        return output_path

                await browser.close()

        except Exception as e:
            logger.error(f"Download failed for {document.url}: {e}")

        return None

    def _extract_year_from_report(self, report: dict) -> int:
        """Extract year from TASE report data."""
        for field in ["PeriodYear", "periodYear", "Year", "year"]:
            if field in report:
                try:
                    return int(report[field])
                except (ValueError, TypeError):
                    pass
        desc = report.get("Description", report.get("description", ""))
        return self.extract_year(desc)

    def _report_to_document(self, report: dict, year: int) -> Optional[DocumentMetadata]:
        """Convert TASE API report to DocumentMetadata."""
        desc = report.get("Description", report.get("description", ""))
        report_id = str(report.get("Id", report.get("id", "")))
        url = report.get("Url", report.get("url", ""))

        if not url:
            return None

        period = self.extract_period(desc)
        is_financial = any(kw in desc.lower() for kw in [
            "financial", "דוח כספי", "תקופתי", "כספיים",
            "quarterly", "annual", "רבעוני", "שנתי",
        ])

        return DocumentMetadata(
            company_slug=self.company.slug,
            company_name=self.company.name,
            document_type=self._classify_report(desc),
            year=year,
            period=period,
            url=url,
            source=self.name,
            description=desc,
            report_id=report_id,
            is_financial=is_financial,
        )

    def _classify_report(self, description: str) -> DocumentType:
        """Classify document type from description."""
        desc_lower = description.lower()
        if any(kw in desc_lower for kw in ["annual", "שנתי", "yearly"]):
            return DocumentType.ANNUAL_REPORT
        elif any(kw in desc_lower for kw in ["quarterly", "רבעון", "q1", "q2", "q3", "q4"]):
            return DocumentType.QUARTERLY_REPORT
        elif any(kw in desc_lower for kw in ["board", "דירקטוריון"]):
            return DocumentType.BOARD_REPORT
        return DocumentType.OTHER
