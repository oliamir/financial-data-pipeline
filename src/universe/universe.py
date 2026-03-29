"""TASE company universe: CSV parsing, searching, and priority list management."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_UNIVERSE_JSON = _DATA_DIR / "universe.json"
_PRIORITY_JSON = _DATA_DIR / "priority_list.json"

# ---------------------------------------------------------------------------
# Sector normalisation
# ---------------------------------------------------------------------------
# The CSV uses hierarchical sectors like "High-Tech-Technology-Renewable Energy".
# We extract the most meaningful leaf label.

_SECTOR_MAP: Dict[str, str] = {
    "Software And Internet": "Software & Internet",
    "IT Services": "IT Services",
    "Renewable Energy": "Renewable Energy",
    "Defence": "Defence",
    "Semiconductors": "Semiconductors",
    "Communications Equipment": "Communications Equipment",
    "Electronics And Optics": "Electronics & Optics",
    "Cleantech": "Cleantech",
    "Robotics & 3d": "Robotics & 3D",
    "Robotics & 3D": "Robotics & 3D",
    "Investments In High-Tech": "High-Tech Investments",
    "High-Tech Funds": "High-Tech Funds",
    "Foodtech": "FoodTech",
    "Medical Devices": "Medical Devices",
    "Biotechnology": "Biotechnology",
    "Pharma": "Pharma",
    "Cannabis": "Cannabis",
    "Investments In Life Science": "Life Science Investments",
    "Construction": "Construction",
    "Investment-Proerties In Israel": "Real Estate (Israel)",
    "Investment-Proerties Abroad": "Real Estate (Abroad)",
    "Investment & Holdings": "Investment & Holdings",
    "Inactive & Shell Companies": "Shell Companies",
    "Financial Services": "Financial Services",
    "Non Banking Credit": "Non-Banking Credit",
    "Insurance": "Insurance",
    "Banks": "Banks",
    "Oil & Gas Exploration": "Oil & Gas",
    "Energy": "Energy",
    "Food": "Food",
    "Fashion & Clothing": "Fashion & Clothing",
    "Wood & Paper": "Wood & Paper",
    "Metal & Building Products": "Metal & Building Products",
    "Chemical, Rubber & Plastic": "Chemicals & Plastics",
    "Electrical": "Electrical",
    "Commerce": "Commerce",
    "Retail": "Retail",
    "Services": "Services",
    "Hotels & Tourism": "Hotels & Tourism",
    "Communications & Media": "Communications & Media",
    "Structured Bonds": "Structured Bonds",
}


def _normalise_sector(raw: str) -> str:
    """Extract a clean sector label from TASE's hierarchical sector string."""
    if not raw:
        return "Other"
    # Try matching from the end (most specific part)
    parts = [p.strip() for p in raw.split("-") if p.strip()]
    for i in range(len(parts) - 1, -1, -1):
        segment = parts[i]
        if segment in _SECTOR_MAP:
            return _SECTOR_MAP[segment]
    # Fallback: last two segments
    if len(parts) >= 2:
        return f"{parts[-2]} - {parts[-1]}"
    return raw


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class TASECompany(BaseModel):
    """A single TASE-listed company."""

    name: str
    full_name: str = ""
    sector_raw: str = ""
    sector: str = ""
    issuer_no: str = ""
    corporate_no: str = ""
    country: str = ""
    website: str = ""
    market_cap_k_ils: int = 0
    email: str = ""
    phone: str = ""


# ---------------------------------------------------------------------------
# CSV Parsing
# ---------------------------------------------------------------------------

def parse_csv(csv_path: str | Path) -> List[TASECompany]:
    """Parse the TASE companies CSV into a list of TASECompany models.

    The CSV has:
      Row 1: "List of TASE Companies,,,,,,,,,,,"
      Row 2: "As of 20/02/2026"
      Row 3: Header row
      Rows 4+: Data
    """
    csv_path = Path(csv_path)
    companies: List[TASECompany] = []

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        # Skip first two informational rows
        next(f)
        next(f)
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Name") or "").strip()
            if not name:
                continue

            # Parse market cap — may be empty or "0"
            mc_raw = (row.get("Market Cap (K ILS)") or "0").strip().replace(",", "")
            try:
                mc = int(mc_raw)
            except ValueError:
                mc = 0

            sector_raw = (row.get("TASE Sector") or "").strip()

            companies.append(TASECompany(
                name=name,
                full_name=(row.get("Full Name") or "").strip(),
                sector_raw=sector_raw,
                sector=_normalise_sector(sector_raw),
                issuer_no=(row.get("Issuer No.") or "").strip(),
                corporate_no=(row.get("Corporate No.") or "").strip(),
                country=(row.get("Incorporation") or "").strip(),
                website=(row.get("Website") or "").strip(),
                market_cap_k_ils=mc,
                email=(row.get("E-Mail") or "").strip(),
                phone=(row.get("Phone") or "").strip(),
            ))

    return companies


def save_universe(companies: List[TASECompany], path: Path | None = None) -> Path:
    """Save parsed companies to JSON."""
    out = path or _UNIVERSE_JSON
    out.parent.mkdir(parents=True, exist_ok=True)
    data = [c.model_dump() for c in companies]
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def load_universe(path: Path | None = None) -> List[TASECompany]:
    """Load the company universe from JSON."""
    src = path or _UNIVERSE_JSON
    if not src.exists():
        return []
    data = json.loads(src.read_text(encoding="utf-8"))
    return [TASECompany(**d) for d in data]


def get_sectors(companies: List[TASECompany]) -> List[str]:
    """Return sorted list of unique sectors."""
    return sorted({c.sector for c in companies if c.sector})


def search_companies(
    companies: List[TASECompany],
    query: str = "",
    sector: str = "",
) -> List[TASECompany]:
    """Filter companies by search query and/or sector."""
    results = companies
    if sector:
        results = [c for c in results if c.sector == sector]
    # Remove companies without market cap
    results = [c for c in results if c.market_cap_k_ils > 0]
    if query:
        q = query.lower()
        results = [
            c for c in results
            if q in c.name.lower() 
            or q in c.full_name.lower()
            or getattr(c, "ticker", "").lower() == q
            or str(c.issuer_no) == q
            or str(c.corporate_no) == q
        ]
    return results


# ---------------------------------------------------------------------------
# Priority List
# ---------------------------------------------------------------------------

class PriorityList:
    """Manages the high-priority company watchlist."""

    def __init__(self, path: Path | None = None):
        self._path = path or _PRIORITY_JSON
        self._companies: Set[str] = set()
        self._sectors: Set[str] = set()
        self._load()

    def _load(self):
        if self._path.exists():
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._companies = set(data.get("companies", []))
            self._sectors = set(data.get("sectors", []))

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "companies": sorted(self._companies),
            "sectors": sorted(self._sectors),
        }
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @property
    def companies(self) -> List[str]:
        return sorted(self._companies)

    @property
    def sectors(self) -> List[str]:
        return sorted(self._sectors)

    def has_company(self, name: str) -> bool:
        return name in self._companies

    def has_sector(self, sector: str) -> bool:
        return sector in self._sectors

    def add_company(self, name: str) -> bool:
        """Add a company. Returns True if newly added."""
        if name in self._companies:
            return False
        self._companies.add(name)
        self._save()
        return True

    def remove_company(self, name: str) -> bool:
        """Remove a company. Returns True if was present."""
        if name not in self._companies:
            return False
        self._companies.discard(name)
        self._save()
        return True

    def add_sector(self, sector: str, universe: List[TASECompany]) -> int:
        """Add all companies in a sector. Returns count added."""
        self._sectors.add(sector)
        count = 0
        for c in universe:
            if c.sector == sector and c.name not in self._companies:
                self._companies.add(c.name)
                count += 1
        self._save()
        return count

    def remove_sector(self, sector: str, universe: List[TASECompany]) -> int:
        """Remove a sector and its companies (unless manually added). Returns count removed."""
        self._sectors.discard(sector)
        count = 0
        for c in universe:
            if c.sector == sector and c.name in self._companies:
                self._companies.discard(c.name)
                count += 1
        self._save()
        return count

    def get_priority_companies(self, universe: List[TASECompany]) -> List[TASECompany]:
        """Return full TASECompany objects for all priority companies."""
        name_set = self._companies
        return [c for c in universe if c.name in name_set]

    def count(self) -> int:
        return len(self._companies)

    def to_dict(self) -> dict:
        return {
            "companies": self.companies,
            "sectors": self.sectors,
            "count": self.count(),
        }
