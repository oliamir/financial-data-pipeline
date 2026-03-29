"""TASE Maya document source.

Delegates to the proven TaseMayaDownloader for document discovery and download.
The downloader navigates the Maya website with Playwright, scraping event pages
and downloading PDF/text artifacts directly into data/companies/<slug>/reports/.
"""

import shutil
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from .base import BaseSource
from ..models.document import DocumentMetadata, DocumentType
from ..models.company import Company
from ..storage.paths import CompanyPaths
from ..utils.logging import get_logger

logger = get_logger(__name__)


class TASESource(BaseSource):
    """TASE Maya document source using the headless TaseMayaDownloader.

    Instead of hitting the TASE API (which returns 403), this delegates to
    the proven TaseMayaDownloader which navigates the Maya website with
    Playwright and downloads PDF artifacts directly.
    """

    name = "tase_maya"

    def __init__(self, company: Company):
        super().__init__(company)
        self.tase_company_id = company.tase_company_id

    async def discover(
        self,
        years_back: int = 5,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[DocumentMetadata]:
        """Run the TaseMayaDownloader to discover and download reports.

        This method both discovers AND downloads in one pass (that's how
        the Maya scraper works — it navigates event pages and downloads PDFs
        on the spot). Downloaded files are placed in a temp directory, then
        moved into data/companies/<slug>/reports/.

        Returns DocumentMetadata entries for each downloaded PDF so the
        coordinator can track them.
        """
        if not self.tase_company_id:
            logger.warning(f"No TASE company ID for {self.company.slug}, skipping TASE source")
            return []

        try:
            from ..tase_maya import TaseMayaDownloader
        except ImportError as e:
            logger.error(f"TaseMayaDownloader not available: {e}")
            return []

        paths = CompanyPaths(self.company.slug)
        paths.ensure_dirs()

        # Run the downloader — it saves PDFs into <output_root>/<slug>/<quarter>/
        downloader = TaseMayaDownloader(
            output_root=str(paths.root / "_tase_scratch"),
            headless=True,
            max_pages=8,
        )

        try:
            summaries = await downloader.run(
                companies=[self.company],
                years=years_back,
                from_date=from_date,
                to_date=to_date,
                incremental=True,
            )
        except Exception as e:
            logger.error(f"TASE Maya scraper failed for {self.company.slug}: {e}")
            return []

        # Move downloaded PDFs from scratch dir into reports/
        documents = []
        scratch_root = paths.root / "_tase_scratch"
        scratch_dir = scratch_root / self.company.slug

        if scratch_dir.exists():
            for pdf_file in sorted(scratch_dir.rglob("*.pdf")):
                dest = paths.reports_dir / pdf_file.name
                if not dest.exists():
                    shutil.move(str(pdf_file), str(dest))
                    logger.info(f"  Moved to reports: {pdf_file.name}")

                    # Create a DocumentMetadata entry
                    doc = DocumentMetadata(
                        company_slug=self.company.slug,
                        company_name=self.company.name,
                        document_type=DocumentType.OTHER,
                        year=self._extract_year_from_filename(pdf_file.name),
                        period="Unknown",
                        url=f"file://{dest}",
                        source=self.name,
                        description=pdf_file.stem,
                        report_id=pdf_file.stem,
                        is_financial=True,  # Assume financial — classify step will verify
                    )
                    documents.append(doc)

        # Always clean up scratch directory (even if no PDFs found)
        if scratch_root.exists():
            try:
                shutil.rmtree(str(scratch_root), ignore_errors=True)
            except Exception:
                pass

        # Log summary
        total_pdfs = 0
        for summary in summaries:
            total_pdfs += summary.pdf_files_downloaded

        logger.info(
            f"TASE: Discovered {len(documents)} new documents for {self.company.slug} "
            f"({total_pdfs} PDFs downloaded from {sum(s.events_found for s in summaries)} events)"
        )
        return documents

    async def download(
        self,
        document: DocumentMetadata,
        output_dir: str,
    ) -> Optional[str]:
        """No-op — downloads already happened during discover().

        The TaseMayaDownloader downloads PDFs as it discovers them.
        Files are already in data/companies/<slug>/reports/.
        """
        # Files were already downloaded and moved during discover()
        dest = Path(output_dir) / Path(document.url.replace("file://", "")).name
        if dest.exists():
            return str(dest)
        return None

    def _extract_year_from_filename(self, filename: str) -> int:
        """Try to extract a year from the filename."""
        import re
        match = re.search(r"(\d{4})", filename)
        if match:
            year = int(match.group(1))
            if 2015 <= year <= 2030:
                return year
        return datetime.now().year
