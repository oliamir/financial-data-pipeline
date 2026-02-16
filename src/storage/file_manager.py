import os
import json
import csv
from typing import List, Optional
from datetime import datetime

from ..models.financial import FinancialMetric
from ..models.memo import InvestmentMemo
from ..models.revision import RevisionEntry
from . import paths


FINANCIALS_COLUMNS = [
    "company_slug", "metric_name", "category", "period_type",
    "period_end_date", "fiscal_year", "value", "unit",
    "value_ils", "value_usd", "source_file", "source_provider",
    "extracted_at", "confidence",
]


class FileManager:
    def __init__(self, slug: str):
        self.slug = slug
        # Ensure directories exist
        paths.company_dir(slug)
        paths.reports_dir(slug)

    # --- Financials CSV ---

    def load_financials(self) -> List[dict]:
        csv_path = paths.financials_csv(self.slug)
        if not os.path.exists(csv_path):
            return []
        rows = []
        with open(csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert numeric fields
                for field in ["value", "value_ils", "value_usd", "confidence", "fiscal_year"]:
                    if row.get(field):
                        try:
                            row[field] = float(row[field])
                        except (ValueError, TypeError):
                            pass
                rows.append(row)
        return rows

    def append_financials(self, metrics: List[FinancialMetric]):
        csv_path = paths.financials_csv(self.slug)
        file_exists = os.path.exists(csv_path)

        with open(csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FINANCIALS_COLUMNS)
            if not file_exists:
                writer.writeheader()
            for metric in metrics:
                writer.writerow(metric.to_dict())

    # --- Investment Memo JSON ---

    def load_memo(self) -> Optional[dict]:
        memo_path = paths.memo_json(self.slug)
        if not os.path.exists(memo_path):
            return None
        with open(memo_path, "r") as f:
            return json.load(f)

    def save_memo(self, memo: InvestmentMemo):
        memo_path = paths.memo_json(self.slug)
        with open(memo_path, "w") as f:
            json.dump(memo.to_dict(), f, indent=2, ensure_ascii=False)

    # --- Revisions JSONL ---

    def append_revision(self, entry: RevisionEntry):
        jsonl_path = paths.revisions_jsonl(self.slug)
        with open(jsonl_path, "a") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def append_revisions(self, entries: List[RevisionEntry]):
        for entry in entries:
            self.append_revision(entry)

    # --- Meta JSON (scraping inventory) ---

    def load_meta(self) -> dict:
        meta_path = paths.meta_json(self.slug)
        if not os.path.exists(meta_path):
            return {
                "last_scrape": None,
                "last_scrape_status": None,
                "reports_found": 0,
                "reports_downloaded": 0,
                "failed_downloads": [],
                "known_reports": {},
                "processed_files": [],
            }
        with open(meta_path, "r") as f:
            return json.load(f)

    def save_meta(self, meta: dict):
        meta_path = paths.meta_json(self.slug)
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

    def update_scrape_status(self, reports_found: int, reports_downloaded: int,
                              failed: List[str], status: str = "success"):
        meta = self.load_meta()
        meta["last_scrape"] = datetime.now().isoformat()
        meta["last_scrape_status"] = status
        meta["reports_found"] = reports_found
        meta["reports_downloaded"] = reports_downloaded
        meta["failed_downloads"] = failed
        self.save_meta(meta)

    def mark_processed(self, file_path: str):
        meta = self.load_meta()
        if file_path not in meta.get("processed_files", []):
            meta.setdefault("processed_files", []).append(file_path)
            self.save_meta(meta)

    def is_processed(self, file_path: str) -> bool:
        meta = self.load_meta()
        return file_path in meta.get("processed_files", [])

    def get_unprocessed_reports(self) -> List[str]:
        """Return list of report file paths that haven't been processed yet."""
        report_dir = paths.reports_dir(self.slug)
        if not os.path.exists(report_dir):
            return []

        meta = self.load_meta()
        processed = set(meta.get("processed_files", []))
        unprocessed = []

        for filename in sorted(os.listdir(report_dir)):
            if filename.startswith("."):
                continue
            full_path = os.path.join(report_dir, filename)
            if os.path.isfile(full_path) and full_path not in processed:
                unprocessed.append(full_path)

        return unprocessed
