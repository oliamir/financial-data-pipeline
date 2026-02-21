from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class Scenario(BaseModel):
    """Bull/Base/Bear scenario for price target."""
    name: str
    probability_pct: float
    target_price: Optional[float] = None
    currency: str = "USD"
    description: str = ""
    key_assumptions: List[str] = Field(default_factory=list)
    catalyst_or_risk: str = ""

class Risk(BaseModel):
    """Categorized risk with severity and mitigation."""
    category: str
    severity: str
    description: str = ""
    mitigation: Optional[str] = None
    monitoring_trigger: Optional[str] = None

class Catalyst(BaseModel):
    """Event that could move the stock."""
    description: str
    timeframe: str = ""
    expected_date: Optional[str] = None
    impact: str = "positive"
    probability: Optional[str] = None

class InvestmentMemo(BaseModel):
    """Professional buy-side investment memo with 13 sections."""
    company_slug: str
    last_updated: Optional[datetime] = None
    recommendation: str = "monitor"
    conviction: str = "low"
    thesis_status: str = "new"

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

    # Structured sub-objects
    scenarios: List[Scenario] = Field(default_factory=list)
    risks: List[Risk] = Field(default_factory=list)
    catalysts: List[Catalyst] = Field(default_factory=list)
