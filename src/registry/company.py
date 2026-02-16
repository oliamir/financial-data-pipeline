import yaml
import os
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class Company:
    slug: str
    name: str
    tase_id: str
    tase_company_id: Optional[str]
    ir_url: Optional[str]
    ir_platform: Optional[str]
    priority: str                       # "high" or "low"
    reporting_currency: str
    sector: str
    dual_listed: bool


class CompanyRegistry:
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Find config relative to project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(project_root, "config", "companies.yaml")
        self.config_path = config_path
        self.companies: dict[str, Company] = {}
        self._load()

    def _load(self):
        with open(self.config_path, "r") as f:
            data = yaml.safe_load(f)

        for entry in data.get("companies", []):
            company = Company(
                slug=entry["slug"],
                name=entry["name"],
                tase_id=entry["tase_id"],
                tase_company_id=entry.get("tase_company_id"),
                ir_url=entry.get("ir_url"),
                ir_platform=entry.get("ir_platform"),
                priority=entry.get("priority", "low"),
                reporting_currency=entry.get("reporting_currency", "ILS"),
                sector=entry.get("sector", ""),
                dual_listed=entry.get("dual_listed", False),
            )
            self.companies[company.slug] = company

    def get(self, slug: str) -> Company:
        slug_lower = slug.lower()
        if slug_lower in self.companies:
            return self.companies[slug_lower]
        # Try matching by name
        for company in self.companies.values():
            if slug_lower in company.name.lower() or slug_lower == company.slug:
                return company
        raise KeyError(f"Company '{slug}' not found in registry")

    def list_by_priority(self, priority: str) -> List[Company]:
        return [c for c in self.companies.values() if c.priority == priority]

    def all(self) -> List[Company]:
        return list(self.companies.values())

    def slugs(self) -> List[str]:
        return list(self.companies.keys())
