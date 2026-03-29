from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, model_validator

class Scenario(BaseModel):
    """Bull/Base/Bear scenario for price target."""
    name: str = ""
    probability_pct: float = 0.0
    target_price: Optional[float] = None
    currency: str = "USD"
    description: str = ""
    key_assumptions: List[str] = Field(default_factory=list)
    catalyst_or_risk: str = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_probability(cls, data):
        """Accept 'probability' as alias for 'probability_pct'."""
        if isinstance(data, dict):
            if "probability" in data and "probability_pct" not in data:
                val = data.pop("probability")
                # Convert decimal (0.25) to percentage (25) if needed
                if isinstance(val, (int, float)) and val <= 1.0:
                    data["probability_pct"] = val * 100
                else:
                    data["probability_pct"] = val
        return data

class Risk(BaseModel):
    """Categorized risk with severity and mitigation."""
    category: str = ""
    severity: str = "medium"
    description: str = ""
    mitigation: Optional[str] = None
    monitoring_trigger: Optional[str] = None

class Catalyst(BaseModel):
    """Event that could move the stock."""
    description: str = ""
    timeframe: str = ""
    timeline: str = ""
    expected_date: Optional[str] = None
    impact: str = "positive"
    probability: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_timeline(cls, data):
        """Accept 'timeline' as alias for 'timeframe'."""
        if isinstance(data, dict):
            if "timeline" in data and not data.get("timeframe"):
                data["timeframe"] = data.get("timeline", "")
        return data

class MemoRevision(BaseModel):
    """Tracks a single memo update event."""
    version: int
    date: str
    source_file: str = ""
    changes_summary: str = ""
    fields_updated: List[str] = Field(default_factory=list)
    thesis_impact: str = "neutral"  # positive / negative / neutral


class InitialResearch(BaseModel):
    """Results from strategic deep-thinking prompts.

    Core research prompts (populated from memo framework):
      - Competitor discovery
      - TAM / SAM / SOM market sizing
      - Competitive analysis
      - Market intelligence
      - SWOT analysis
      - Seven Powers analysis (Hamilton Helmer)
      - Ownership structure & shareholder dynamics
      - Israel-specific risk factors
    """
    competitors: str = ""
    tam_sam_som: str = ""
    competitive_analysis: str = ""
    market_intelligence: str = ""
    swot_analysis: str = ""
    seven_powers: str = ""
    ownership_structure: str = ""
    israel_risk: str = ""
    generated_at: Optional[str] = None
    model_used: str = ""


class InvestmentMemo(BaseModel):
    """Professional buy-side investment memo with versioning and strategic research."""
    company_slug: str = ""
    last_updated: Optional[datetime] = None
    recommendation: str = "monitor"
    conviction: str = "low"
    thesis_status: str = "new"

    # Versioning
    version: int = 1
    revisions: List[MemoRevision] = Field(default_factory=list)

    # Summary field (LLM may use 'summary' instead of 'executive_summary')
    summary: str = ""

    # 13 Sections
    header: str = ""
    executive_summary: str = ""
    company_overview: str = ""
    industry_analysis: str = ""
    competitive_positioning: str = ""
    management_governance: str = ""
    financial_analysis: str = ""
    valuation: str = ""
    scenario_analysis: str = ""
    risks_mitigants: str = ""
    catalysts_timeline: str = ""
    open_questions: str = ""
    appendix: str = ""

    # New framework sections (from investment_memo_framework_v3)
    market_size: str = ""
    seven_powers: str = ""
    ownership_structure: str = ""
    israel_risk_factors: str = ""
    investment_conclusion: str = ""
    swot_analysis: str = ""

    # LLM may return these alternative field names
    revenue_analysis: str = ""
    profitability_analysis: str = ""
    balance_sheet_review: str = ""
    cash_flow_analysis: str = ""
    esg_notes: str = ""
    action_items: List[str] = Field(default_factory=list)

    # Structured sub-objects
    scenarios: List[Scenario] = Field(default_factory=list)
    risks: List[Risk] = Field(default_factory=list)
    catalysts: List[Catalyst] = Field(default_factory=list)

    # Strategic research (populated by Initial Run phase)
    initial_research: InitialResearch = Field(default_factory=InitialResearch)

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data):
        """Map LLM-returned field names to our model fields."""
        if isinstance(data, dict):
            # Map summary -> executive_summary if missing
            if data.get("summary") and not data.get("executive_summary"):
                data["executive_summary"] = data["summary"]

            # Convert dict/list values to JSON strings for text fields
            text_fields = [
                "header", "executive_summary", "company_overview", "industry_analysis",
                "competitive_positioning", "management_governance", "financial_analysis",
                "valuation", "scenario_analysis", "risks_mitigants", "catalysts_timeline",
                "open_questions", "appendix", "summary", "revenue_analysis",
                "profitability_analysis", "balance_sheet_review", "cash_flow_analysis",
                "esg_notes", "market_size", "seven_powers", "ownership_structure",
                "israel_risk_factors", "investment_conclusion", "swot_analysis",
            ]
            for field in text_fields:
                val = data.get(field)
                if isinstance(val, dict):
                    # Convert dict to readable string
                    parts = []
                    for k, v in val.items():
                        parts.append(f"{k}: {v}")
                    data[field] = "\n".join(parts)
                elif isinstance(val, list):
                    data[field] = "\n".join(str(item) for item in val)

            # Handle action_items that might be a string
            if isinstance(data.get("action_items"), str):
                data["action_items"] = [data["action_items"]]
        return data
