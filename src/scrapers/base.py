import os
import re
from abc import ABC, abstractmethod
from typing import List

from ..models.report import ReportMetadata


class BaseScraper(ABC):
    def __init__(self, company_slug: str, company_name: str):
        self.company_slug = company_slug
        self.company_name = company_name

    @abstractmethod
    async def fetch_reports(self, years_back: int = 5, **kwargs) -> List[ReportMetadata]:
        """Fetch report metadata from the source."""
        pass

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
        """Check that a downloaded file is actually a valid PDF."""
        if not os.path.exists(path):
            return False
        try:
            with open(path, "rb") as f:
                header = f.read(5)
            if header != b"%PDF-":
                print(f"  [Validate] Invalid PDF (bad header): {path}")
                os.remove(path)
                return False
            # Also check file isn't tiny (likely error page)
            if os.path.getsize(path) < 1000:
                print(f"  [Validate] Suspiciously small file ({os.path.getsize(path)} bytes): {path}")
                return False
            return True
        except Exception as e:
            print(f"  [Validate] Error checking PDF: {e}")
            return False
