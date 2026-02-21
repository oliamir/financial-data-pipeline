"""Manual document source.

Allows importing local files (PDFs) for private companies or
when automated scraping isn't available.
"""

import os
import shutil
from datetime import date
from pathlib import Path
from typing import List, Optional

from .base import BaseSource
from ..models.document import DocumentMetadata, DocumentType
from ..models.company import Company
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ManualSource(BaseSource):
    """Manual file import source for private companies."""

    name = "manual"

    def __init__(self, company: Company, import_dir: Optional[str] = None):
        super().__init__(company)
        self.import_dir = import_dir

    async def discover(
        self,
        years_back: int = 5,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[DocumentMetadata]:
        """Discover local PDF files in the import directory."""
        if not self.import_dir or not os.path.isdir(self.import_dir):
            return []

        documents = []
        for filename in sorted(os.listdir(self.import_dir)):
            if not filename.lower().endswith(".pdf"):
                continue

            filepath = os.path.join(self.import_dir, filename)
            year = self.extract_year(filename)

            if not self._within_date_range(year, from_date, to_date):
                continue

            period = self.extract_period(filename)

            doc = DocumentMetadata(
                company_slug=self.company.slug,
                company_name=self.company.name,
                document_type=DocumentType.OTHER,
                year=year,
                period=period,
                url=f"file://{filepath}",
                source=self.name,
                description=filename,
                is_financial=True,
                local_path=filepath,
            )
            documents.append(doc)

        logger.info(f"Manual: Found {len(documents)} files for {self.company.slug}")
        return documents

    async def download(
        self,
        document: DocumentMetadata,
        output_dir: str,
    ) -> Optional[str]:
        """Copy a local file to the output directory."""
        if not document.local_path or not os.path.exists(document.local_path):
            logger.warning(f"Source file not found: {document.local_path}")
            return None

        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.basename(document.local_path)
        output_path = os.path.join(output_dir, filename)

        if not os.path.exists(output_path):
            shutil.copy2(document.local_path, output_path)
            logger.info(f"Copied: {filename}")

        return output_path
