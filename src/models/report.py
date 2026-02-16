from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class ReportMetadata:
    """Metadata for a single financial report (PDF or other document)."""
    company_slug: str
    company_name: str
    year: int
    period: str                         # "Q1", "Q2", "Q3", "Q4", "Annual", "H1", "H2", "Other"
    url: str
    source: str                         # "TASE_Maya", "IR_Website"
    file_type: str = "pdf"
    description: str = ""
    report_id: Optional[str] = None
    is_financial: bool = False
    extra_headers: Optional[Dict] = None
    attachments: Optional[List] = None
    local_path: Optional[str] = None
    local_paths: List[str] = field(default_factory=list)
    drive_id: Optional[str] = None

    def __repr__(self):
        return f"<Report {self.company_slug} {self.year} {self.period} ({self.source})>"
