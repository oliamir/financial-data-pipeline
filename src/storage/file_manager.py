"""CRUD operations for company artifacts."""

import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from ..models.financial import FinancialPeriod
from ..models.memo import InvestmentMemo
from ..models.kpi import KPIMetrics
from ..models.research import MarketResearch
from .paths import CompanyPaths

class FileManager:
    """Manages reading/writing company artifacts to disk."""

    def __init__(self, slug: str, data_root: Optional[Path] = None):
        self.slug = slug
        self.paths = CompanyPaths(slug, data_root)
        self.paths.ensure_dirs()

    # --- Financial Periods ---

    def load_financials(self) -> List[FinancialPeriod]:
        path = self.paths.financials_json
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        return [FinancialPeriod.model_validate(item) for item in data]

    def save_financials(self, periods: List[FinancialPeriod]) -> None:
        data = [p.model_dump(mode="json") for p in periods]
        self.paths.financials_json.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str)
        )

    def append_financial(self, period: FinancialPeriod) -> None:
        existing = self.load_financials()
        replaced = False
        for i, p in enumerate(existing):
            if p.fiscal_year == period.fiscal_year and p.period_type == period.period_type:
                existing[i] = period
                replaced = True
                break
        if not replaced:
            existing.append(period)
        self.save_financials(existing)

    # --- Investment Memo ---

    def load_memo(self) -> Optional[InvestmentMemo]:
        path = self.paths.memo_json
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return InvestmentMemo.model_validate(data)

    def save_memo(self, memo: InvestmentMemo) -> None:
        self.paths.memo_json.write_text(
            json.dumps(memo.model_dump(mode="json"), indent=2, ensure_ascii=False, default=str)
        )
        # Auto-render professional markdown
        from ..memo.renderer import MemoRenderer
        md = MemoRenderer.render(memo)
        self.save_memo_markdown(md)

    def save_memo_markdown(self, markdown: str) -> None:
        self.paths.memo_md.write_text(markdown)

    # --- KPI Metrics ---

    def load_kpis(self) -> Optional[KPIMetrics]:
        path = self.paths.kpi_json
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return KPIMetrics.model_validate(data)

    def save_kpis(self, kpi: KPIMetrics) -> None:
        self.paths.kpi_json.write_text(
            json.dumps(kpi.model_dump(mode="json"), indent=2, ensure_ascii=False)
        )

    # --- Market Research ---

    def load_research(self) -> Optional[MarketResearch]:
        path = self.paths.research_json
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return MarketResearch.model_validate(data)

    def save_research(self, research: MarketResearch) -> None:
        self.paths.research_json.write_text(
            json.dumps(research.model_dump(mode="json"), indent=2, ensure_ascii=False)
        )

    # --- Meta JSON (scraping inventory) ---

    def load_meta(self) -> dict:
        path = self.paths.meta_json
        if not path.exists():
            return {
                "last_scrape": None,
                "last_scrape_status": None,
                "reports_found": 0,
                "reports_downloaded": 0,
                "failed_downloads": [],
                "known_reports": {},
                "processed_files": [],
            }
        return json.loads(path.read_text())

    def save_meta(self, meta: dict) -> None:
        self.paths.meta_json.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False, default=str)
        )

    def update_scrape_status(
        self, reports_found: int, reports_downloaded: int,
        failed: List[str], status: str = "success"
    ) -> None:
        meta = self.load_meta()
        meta["last_scrape"] = datetime.now().isoformat()
        meta["last_scrape_status"] = status
        meta["reports_found"] = reports_found
        meta["reports_downloaded"] = reports_downloaded
        meta["failed_downloads"] = failed
        self.save_meta(meta)

    def mark_processed(self, file_path: str) -> None:
        meta = self.load_meta()
        processed = meta.setdefault("processed_files", [])
        if file_path not in processed:
            processed.append(file_path)
            self.save_meta(meta)

    def is_processed(self, file_path: str) -> bool:
        meta = self.load_meta()
        return file_path in meta.get("processed_files", [])

    def get_unprocessed_reports(self) -> List[Path]:
        if not self.paths.reports_dir.exists():
            return []
        meta = self.load_meta()
        processed = set(meta.get("processed_files", []))
        return sorted([
            f for f in self.paths.reports_dir.iterdir()
            if f.is_file() and not f.name.startswith(".") and str(f) not in processed
        ])
