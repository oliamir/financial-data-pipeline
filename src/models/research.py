from typing import Optional, List
from pydantic import BaseModel, Field

class SWOTItem(BaseModel):
    """Single SWOT point tied to a measurable business outcome."""
    point: str
    measurable_outcome: str = ""
    data_source: str = ""

class SWOT(BaseModel):
    """SWOT analysis with actionable, data-backed items."""
    strengths: List[SWOTItem] = Field(default_factory=list)
    weaknesses: List[SWOTItem] = Field(default_factory=list)
    opportunities: List[SWOTItem] = Field(default_factory=list)
    threats: List[SWOTItem] = Field(default_factory=list)

class CompSetEntry(BaseModel):
    """Single comparable company."""
    company_name: str
    ticker: Optional[str] = None
    market_cap: Optional[float] = None
    revenue: Optional[float] = None
    ebitda_margin: Optional[float] = None
    pe_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None
    revenue_growth: Optional[float] = None
    notes: str = ""

class CompSet(BaseModel):
    """Comparable company analysis."""
    comps: List[CompSetEntry] = Field(default_factory=list)
    median_pe: Optional[float] = None
    median_ev_ebitda: Optional[float] = None
    implied_value_range: str = ""

class IndustryTrend(BaseModel):
    """A single industry trend (tailwind or headwind)."""
    trend: str
    direction: str = "tailwind"
    time_horizon: str = ""
    impact_description: str = ""
    data_points: List[str] = Field(default_factory=list)

class MarketResearch(BaseModel):
    """Aggregated market research for a company."""
    company_slug: str

    # Market sizing
    tam: Optional[float] = None
    sam: Optional[float] = None
    som: Optional[float] = None
    market_growth_rate: Optional[float] = None
    market_sizing_methodology: str = ""

    # Analysis objects
    swot: SWOT = Field(default_factory=SWOT)
    comp_set: CompSet = Field(default_factory=CompSet)
    industry_trends: List[IndustryTrend] = Field(default_factory=list)

    # Sources
    sources: List[str] = Field(default_factory=list)
    last_updated: Optional[str] = None
