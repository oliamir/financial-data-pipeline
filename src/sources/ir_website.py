"""IR website document source.

Discovers and downloads financial reports from company investor relations
websites. Supports WordPress, Q4, Notified, and generic IR platforms.
Ported from src/scrapers/ir_generic.py and src/scrapers/ir_profiles.py.
"""

import os
from datetime import date
from typing import List, Optional

from .base import BaseSource
from ..models.document import DocumentMetadata, DocumentType
from ..models.company import Company
from ..utils.logging import get_logger

logger = get_logger(__name__)


class IRWebsiteSource(BaseSource):
    """IR website document source for companies with public IR pages."""

    name = "ir_website"

    def __init__(self, company: Company):
        super().__init__(company)
        self.ir_url = company.ir_url
        self.ir_platform = company.ir_platform

    async def discover(
        self,
        years_back: int = 5,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[DocumentMetadata]:
        """Discover reports from the company's IR website."""
        if not self.ir_url:
            logger.debug(f"No IR URL for {self.company.slug}, skipping IR source")
            return []

        documents = []

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                await page.goto(self.ir_url, timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=15000)

                # Find all PDF links on the page
                links = await page.query_selector_all('a[href$=".pdf"], a[href*="/pdf/"]')

                for link in links:
                    try:
                        href = await link.get_attribute("href")
                        text = await link.inner_text()

                        if not href:
                            continue

                        # Make absolute URL
                        if href.startswith("/"):
                            from urllib.parse import urlparse
                            parsed = urlparse(self.ir_url)
                            href = f"{parsed.scheme}://{parsed.netloc}{href}"

                        year = self.extract_year(text, href)
                        if not self._within_date_range(year, from_date, to_date):
                            continue

                        period = self.extract_period(text)

                        doc = DocumentMetadata(
                            company_slug=self.company.slug,
                            company_name=self.company.name,
                            document_type=self._classify_from_text(text),
                            year=year,
                            period=period,
                            url=href,
                            source=self.name,
                            description=text.strip()[:200],
                            is_financial=self._is_financial(text),
                        )
                        documents.append(doc)

                    except Exception as e:
                        logger.debug(f"Skipping link: {e}")

                await browser.close()

        except Exception as e:
            logger.error(f"IR discovery failed for {self.company.slug}: {e}")

        logger.info(f"IR: Discovered {len(documents)} documents for {self.company.slug}")
        return documents

    async def download(
        self,
        document: DocumentMetadata,
        output_dir: str,
    ) -> Optional[str]:
        """Download a report from the IR website."""
        os.makedirs(output_dir, exist_ok=True)

        filename = f"{document.year}_{document.period}_ir_{hash(document.url) % 10000}.pdf"
        output_path = os.path.join(output_dir, filename)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return output_path

        try:
            import httpx

            headers = document.extra_headers or {}
            async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
                response = await client.get(document.url, headers=headers)
                if response.status_code == 200:
                    with open(output_path, "wb") as f:
                        f.write(response.content)

                    if self.validate_pdf(output_path):
                        logger.info(f"Downloaded: {filename}")
                        return output_path

        except Exception as e:
            logger.error(f"Download failed for {document.url}: {e}")

        return None

    def _classify_from_text(self, text: str) -> DocumentType:
        """Classify document type from link text."""
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["annual", "שנתי"]):
            return DocumentType.ANNUAL_REPORT
        elif any(kw in text_lower for kw in ["quarterly", "q1", "q2", "q3", "q4", "רבעון"]):
            return DocumentType.QUARTERLY_REPORT
        elif any(kw in text_lower for kw in ["presentation", "מצגת"]):
            return DocumentType.PRESENTATION
        elif any(kw in text_lower for kw in ["press", "הודעה"]):
            return DocumentType.PRESS_RELEASE
        return DocumentType.OTHER

    def _is_financial(self, text: str) -> bool:
        """Check if document is likely a financial report."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in [
            "financial", "כספי", "quarterly", "annual",
            "רבעוני", "שנתי", "תקופתי",
        ])
