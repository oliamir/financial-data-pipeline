from dataclasses import dataclass
from typing import Optional


@dataclass
class RevisionEntry:
    """Single row in the append-only revision log (JSONL)."""
    timestamp: str                      # ISO 8601
    company_slug: str
    metric_name: str
    period: str                         # "FY2024", "Q3_2024"
    old_value: Optional[float]
    new_value: Optional[float]
    reason: str                         # "New Q3 report processed", "Gemini correction"
    source_file: str = ""
    provider: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "company_slug": self.company_slug,
            "metric_name": self.metric_name,
            "period": self.period,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "source_file": self.source_file,
            "provider": self.provider,
        }
