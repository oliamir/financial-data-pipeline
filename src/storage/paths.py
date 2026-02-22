"""Centralized path conventions for data/companies/<slug>/."""

from pathlib import Path
from typing import Optional

class CompanyPaths:
    """All file paths for a single company's data."""

    def __init__(self, slug: str, data_root: Optional[Path] = None):
        if data_root is None:
            data_root = Path(__file__).resolve().parent.parent.parent / "data" / "companies"
        self.slug = slug
        self.root = data_root / slug
        self.reports_dir = self.root / "reports"

    def ensure_dirs(self) -> None:
        """Create all required directories."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    @property
    def financials_json(self) -> Path:
        return self.root / "financials.json"

    @property
    def memo_md(self) -> Path:
        return self.root / "Investment_Memo.md"

    @property
    def memo_json(self) -> Path:
        return self.root / "memo.json"

    @property
    def model_xlsx(self) -> Path:
        return self.root / "Financial_Model.xlsx"

    @property
    def meta_json(self) -> Path:
        return self.root / "meta.json"

    @property
    def research_json(self) -> Path:
        return self.root / "research.json"

    @property
    def kpi_json(self) -> Path:
        return self.root / "kpi.json"

    def report_path(self, year: int, period: str, report_id: str, ext: str = "pdf") -> Path:
        """Path for a specific report file."""
        filename = f"{year}_{period}_{report_id}.{ext}"
        return self.reports_dir / filename



# ---------------------------------------------------------------------------
# Module-level convenience functions (used by dashboard, etc.)
# ---------------------------------------------------------------------------
_DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "companies"


def company_dir(slug: str) -> str:
    """Return the company data directory path as a string."""
    return str(_DATA_ROOT / slug)


def reports_dir(slug: str) -> str:
    """Return the reports directory path as a string."""
    return str(_DATA_ROOT / slug / "reports")


def meta_json(slug: str) -> str:
    """Return the meta.json path as a string."""
    return str(_DATA_ROOT / slug / "meta.json")


def financials_json(slug: str) -> str:
    """Return the financials.json path as a string."""
    return str(_DATA_ROOT / slug / "financials.json")


def memo_json(slug: str) -> str:
    """Return the memo.json path as a string."""
    return str(_DATA_ROOT / slug / "memo.json")


def kpi_json(slug: str) -> str:
    """Return the kpi.json path as a string."""
    return str(_DATA_ROOT / slug / "kpi.json")


def financials_csv(slug: str) -> str:
    """Return the financials CSV path (legacy compat) as a string."""
    return str(_DATA_ROOT / slug / "Financial_Model.csv")
