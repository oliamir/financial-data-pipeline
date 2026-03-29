from enum import Enum
from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, Field

class DocumentType(str, Enum):
    ANNUAL_REPORT = "annual_report"
    QUARTERLY_REPORT = "quarterly_report"
    BOARD_REPORT = "board_report"
    PROSPECTUS = "prospectus"
    PROXY = "proxy"
    PRESENTATION = "presentation"
    PRESS_RELEASE = "press_release"
    OTHER = "other"
    UNKNOWN = "unknown"

class DocumentMetadata(BaseModel):
    """Metadata for a discovered/downloaded financial document."""
    company_slug: str
    company_name: str = ""
    document_type: DocumentType = DocumentType.UNKNOWN
    year: int
    period: str                             # "Q1", "Q2", "Q3", "Q4", "Annual", "H1", "H2"
    url: str
    source: str                             # "tase_maya", "ir_website", "manual"
    file_type: str = "pdf"
    description: str = ""
    report_id: Optional[str] = None
    is_financial: bool = False
    extra_headers: Optional[Dict[str, str]] = None
    local_path: Optional[str] = None
    local_paths: List[str] = Field(default_factory=list)
    drive_id: Optional[str] = None
    downloaded_at: Optional[datetime] = None
    file_size_bytes: Optional[int] = None
