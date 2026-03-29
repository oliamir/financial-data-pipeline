"""IR auto-discovery source.

Uses web search to find IR URLs for companies that don't have
a pre-configured IR website URL. Primarily for US-traded companies.
"""

from datetime import date
from typing import List, Optional

from .base import BaseSource
from .ir_website import IRWebsiteSource
from ..models.document import DocumentMetadata
from ..models.company import Company
from ..utils.logging import get_logger

logger = get_logger(__name__)


class IRDiscoverySource(BaseSource):
    """Auto-discovers IR website URLs and delegates to IRWebsiteSource."""

    name = "ir_discovery"

    async def discover(
        self,
        years_back: int = 5,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[DocumentMetadata]:
        """Search for IR website and discover documents."""
        if self.company.ir_url:
            # Already has IR URL, use IRWebsiteSource directly
            ir_source = IRWebsiteSource(self.company)
            return await ir_source.discover(years_back, from_date, to_date)

        # Try to find IR URL via web search
        ir_url = await self._search_for_ir_url()
        if not ir_url:
            logger.info(f"Could not find IR URL for {self.company.name}")
            return []

        # Create a modified company with the discovered URL
        modified = self.company.model_copy(update={"ir_url": ir_url})
        ir_source = IRWebsiteSource(modified)
        return await ir_source.discover(years_back, from_date, to_date)

    async def download(
        self,
        document: DocumentMetadata,
        output_dir: str,
    ) -> Optional[str]:
        """Download via IRWebsiteSource."""
        ir_source = IRWebsiteSource(self.company)
        return await ir_source.download(document, output_dir)

    async def _search_for_ir_url(self) -> Optional[str]:
        """Search the web for the company's IR page URL."""
        search_queries = [
            f"{self.company.name} investor relations financial reports",
            f"{self.company.us_ticker} SEC filings annual report" if self.company.us_ticker else None,
        ]

        try:
            import httpx

            for query in filter(None, search_queries):
                try:
                    async with httpx.AsyncClient(timeout=15) as client:
                        # Simple search via DuckDuckGo HTML
                        response = await client.get(
                            "https://html.duckduckgo.com/html/",
                            params={"q": query},
                        )
                        if response.status_code == 200:
                            url = self._extract_ir_url_from_search(response.text)
                            if url:
                                logger.info(f"Discovered IR URL for {self.company.name}: {url}")
                                return url
                except Exception as e:
                    logger.debug(f"Search query failed: {e}")

        except ImportError:
            logger.warning("httpx not available for IR discovery")

        return None

    def _extract_ir_url_from_search(self, html: str) -> Optional[str]:
        """Extract likely IR URL from search results HTML."""
        import re

        # Look for URLs containing investor-relations patterns
        urls = re.findall(r'href="(https?://[^"]+)"', html)
        ir_patterns = ["investor", "ir.", "/ir/", "financial-reports", "sec-filings"]

        for url in urls:
            url_lower = url.lower()
            if any(p in url_lower for p in ir_patterns):
                # Skip search engine URLs
                if "duckduckgo" not in url_lower and "google" not in url_lower:
                    return url

        return None
