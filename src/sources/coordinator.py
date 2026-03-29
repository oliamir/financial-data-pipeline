"""Source coordinator — orchestrates document discovery and download across sources.

Runs multiple document sources with retries, deduplication, and health checks.
"""

import asyncio
from datetime import date
from typing import List, Optional, Dict

from .base import BaseSource
from .tase import TASESource
from .ir_website import IRWebsiteSource
from .ir_discovery import IRDiscoverySource
from .manual import ManualSource
from ..models.document import DocumentMetadata
from ..models.company import Company, CompanyType
from ..storage.paths import CompanyPaths
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SourceCoordinator:
    """Orchestrates document discovery and download across all sources.

    For each company, determines which sources to use based on company type,
    runs discovery, deduplicates results, and manages downloads.
    """

    def __init__(
        self,
        company: Company,
        years_back: int = 5,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        financial_only: bool = True,
        import_dir: Optional[str] = None,
    ):
        self.company = company
        self.years_back = years_back
        self.from_date = from_date
        self.to_date = to_date
        self.financial_only = financial_only
        self.paths = CompanyPaths(company.slug)
        self.sources = self._build_sources(import_dir)

    def _build_sources(self, import_dir: Optional[str] = None) -> List[BaseSource]:
        """Determine which sources to use based on company type."""
        sources = []

        if self.company.company_type in (CompanyType.TASE_TRADED,) and self.company.tase_company_id:
            sources.append(TASESource(self.company))

        if self.company.ir_url:
            sources.append(IRWebsiteSource(self.company))
        elif self.company.company_type == CompanyType.US_TRADED:
            sources.append(IRDiscoverySource(self.company))

        if self.company.company_type == CompanyType.PRIVATE or import_dir:
            sources.append(ManualSource(self.company, import_dir=import_dir))

        if not sources:
            logger.warning(f"No sources available for {self.company.slug}")

        return sources

    async def discover_all(self) -> List[DocumentMetadata]:
        """Run discovery across all sources, deduplicate, and return results."""
        all_documents = []

        for source in self.sources:
            try:
                docs = await source.discover(
                    years_back=self.years_back,
                    from_date=self.from_date,
                    to_date=self.to_date,
                )
                all_documents.extend(docs)
            except Exception as e:
                logger.error(f"Discovery failed for source '{source.name}': {e}")

        # Deduplicate
        deduped = self._deduplicate(all_documents)

        # Filter to financial only if configured
        if self.financial_only:
            deduped = [d for d in deduped if d.is_financial]

        logger.info(
            f"Discovered {len(deduped)} documents for {self.company.slug} "
            f"({len(all_documents)} total, {len(all_documents) - len(deduped)} duplicates/filtered)"
        )
        return deduped

    async def download_all(
        self,
        documents: Optional[List[DocumentMetadata]] = None,
        max_concurrent: int = 3,
    ) -> Dict[str, str]:
        """Download all discovered documents.

        Args:
            documents: List of documents to download. If None, runs discover_all first.
            max_concurrent: Maximum concurrent downloads.

        Returns:
            Dict mapping document URL to local file path for successful downloads.
        """
        if documents is None:
            documents = await self.discover_all()

        output_dir = str(self.paths.reports_dir)
        results: Dict[str, str] = {}
        failed = []

        sem = asyncio.Semaphore(max_concurrent)

        async def _download_one(doc: DocumentMetadata):
            async with sem:
                source = self._source_for_document(doc)
                if source:
                    try:
                        path = await source.download(doc, output_dir)
                        if path:
                            results[doc.url] = path
                        else:
                            failed.append(doc.url)
                    except Exception as e:
                        logger.error(f"Download error for {doc.url}: {e}")
                        failed.append(doc.url)

        await asyncio.gather(*[_download_one(doc) for doc in documents])

        logger.info(
            f"Downloaded {len(results)}/{len(documents)} documents for {self.company.slug} "
            f"({len(failed)} failed)"
        )
        return results

    def _source_for_document(self, doc: DocumentMetadata) -> Optional[BaseSource]:
        """Find the right source instance for downloading a document."""
        for source in self.sources:
            if source.name == doc.source:
                return source
        # Fallback to first source
        return self.sources[0] if self.sources else None

    def _deduplicate(self, documents: List[DocumentMetadata]) -> List[DocumentMetadata]:
        """Remove duplicate documents by URL."""
        seen_urls = set()
        unique = []
        for doc in documents:
            if doc.url not in seen_urls:
                seen_urls.add(doc.url)
                unique.append(doc)
        return unique
