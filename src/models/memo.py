from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Scenario:
    name: str                           # "bull", "base", "bear"
    probability_pct: float
    target_price: Optional[float] = None
    currency: str = "USD"
    description: str = ""
    key_assumptions: List[str] = field(default_factory=list)
    catalyst_or_risk: str = ""


@dataclass
class RiskEntry:
    category: str                       # "operational", "market", "financial", "regulatory"
    severity: str                       # "high", "medium", "low"
    description: str = ""
    mitigation: Optional[str] = None
    monitoring_trigger: Optional[str] = None


@dataclass
class ThesisEvent:
    date: str                           # ISO 8601
    event: str
    source_file: str = ""
    impact: str = "neutral"             # "positive", "negative", "neutral"


@dataclass
class OpenQuestion:
    question: str
    raised_date: str
    status: str = "open"                # "open", "resolved"
    resolution: Optional[str] = None


@dataclass
class InvestmentMemo:
    company_slug: str
    last_updated: str = ""
    recommendation: str = "monitor"     # "buy", "hold", "sell", "monitor"
    conviction: str = "low"             # "high", "medium", "low"
    thesis_status: str = "new"          # "new", "intact", "strengthening", "weakening", "broken"
    executive_summary: str = ""
    one_line_thesis: str = ""
    company_overview: str = ""
    financial_summary: str = ""
    competitive_positioning: str = ""
    management_notes: str = ""
    scenarios: List[Scenario] = field(default_factory=list)
    risks: List[RiskEntry] = field(default_factory=list)
    thesis_timeline: List[ThesisEvent] = field(default_factory=list)
    open_questions: List[OpenQuestion] = field(default_factory=list)
    raw_narrative: str = ""

    def to_dict(self) -> dict:
        return {
            "company_slug": self.company_slug,
            "last_updated": self.last_updated,
            "recommendation": self.recommendation,
            "conviction": self.conviction,
            "thesis_status": self.thesis_status,
            "executive_summary": self.executive_summary,
            "one_line_thesis": self.one_line_thesis,
            "company_overview": self.company_overview,
            "financial_summary": self.financial_summary,
            "competitive_positioning": self.competitive_positioning,
            "management_notes": self.management_notes,
            "scenarios": [
                {
                    "name": s.name,
                    "probability_pct": s.probability_pct,
                    "target_price": s.target_price,
                    "currency": s.currency,
                    "description": s.description,
                    "key_assumptions": s.key_assumptions,
                    "catalyst_or_risk": s.catalyst_or_risk,
                }
                for s in self.scenarios
            ],
            "risks": [
                {
                    "category": r.category,
                    "severity": r.severity,
                    "description": r.description,
                    "mitigation": r.mitigation,
                    "monitoring_trigger": r.monitoring_trigger,
                }
                for r in self.risks
            ],
            "thesis_timeline": [
                {
                    "date": t.date,
                    "event": t.event,
                    "source_file": t.source_file,
                    "impact": t.impact,
                }
                for t in self.thesis_timeline
            ],
            "open_questions": [
                {
                    "question": q.question,
                    "raised_date": q.raised_date,
                    "status": q.status,
                    "resolution": q.resolution,
                }
                for q in self.open_questions
            ],
            "raw_narrative": self.raw_narrative,
        }
