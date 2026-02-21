"""Base document source interface.

All document sources (TASE, IR website, manual) implement this interface,
enabling pluggable document discovery and download with date range filtering.
"""

import os
import re
from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional

from ..models.document import DocumentMetadata
from ..models.company import Company
from ..utils.logging import get_logger

logger = get_logger(__name__)


class BaseSource(ABC):
    """Abstract base class for document sources."""

    name: str = "base"

    def __init__(self, company: Company):
        self.company = company

    @abstractmethod
    async def discover(
        self,
        years_back: int = 5,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[DocumentMetadata]:
        """Discover available documents from this source.

        Args:
            years_back: How many years of history to search.
            from_date: Optional start date filter.
            to_date: Optional end date filter.

        Returns:
            List of document metadata for available documents.
        """
        pass

    @abstractmethod
    async def download(
        self,
        document: DocumentMetadata,
        output_dir: str,
    ) -> Optional[str]:
        """Download a document to the output directory.

        Args:
            document: Metadata for the document to download.
            output_dir: Directory to save the file.

        Returns:
            Local file path if successful, None otherwise.
        """
        pass

    def _within_date_range(
        self,
        year: int,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> bool:
        """Check whether a year falls within the configured date range."""
        if from_date and year < from_date.year:
            return False
        if to_date and year > to_date.year:
            return False
        return True

    def extract_period(self, text: str) -> str:
        """Extract period from text (Hebrew + English)."""
        text_lower = text.lower()
        if any(q in text_lower for q in ["q1", "רבעון ראשון", "רבעון 1", "first quarter"]):
            return "Q1"
        elif any(q in text_lower for q in ["q2", "רבעון שני", "רבעון 2", "second quarter"]):
            return "Q2"
        elif any(q in text_lower for q in ["q3", "רבעון שלישי", "רבעון 3", "third quarter"]):
            return "Q3"
        elif any(q in text_lower for q in ["q4", "רבעון רביעי", "רבעון 4", "fourth quarter"]):
            return "Q4"
        elif any(a in text_lower for a in ["annual", "שנתי", "yearly", "תקופתי"]):
            return "Annual"
        elif any(h in text_lower for h in ["half", "חציון", "חצי שנתי"]):
            return "H1"
        return "Other"

    def extract_year(self, text: str, url: str = "") -> int:
        """Extract year from text or URL."""
        combined = text + " " + url
        match = re.search(r"20(2[0-9]|1[0-9])", combined)
        if match:
            return int(match.group(0))
        return 2024

    def validate_pdf(self, path: str) -> bool:
        """Check that a downloaded file is a valid PDF."""
        if not os.path.exists(path):
            return False
        try:
            with open(path, "rb") as f:
                header = f.read(5)
            if header != b"%PDF-":
                logger.warning(f"Invalid PDF (bad header): {path}")
                os.remove(path)
                return False
            if os.path.getsize(path) < 1000:
                logger.warning(f"Suspiciously small file ({os.path.getsize(path)} bytes): {path}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error checking PDF: {e}")
            return False
