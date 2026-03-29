# Phase 1: Foundation -- Implementation Plan

> **Status**: ✅ COMPLETE (verified 2026-02-21)
> **Verification**: 57/57 unit tests pass, CLI `list-companies --help` ✓, CLI `status --help` ✓
> **Files created**: 38 files matching this plan

## Overview

Phase 1 establishes the project skeleton: Poetry packaging, Pydantic v2 data models, config loading, storage layer, utility functions (ported from v1), CLI skeleton with Typer, and test infrastructure. This phase produces 38 files and creates the foundation that all subsequent phases build upon.

---

## Task 1: Poetry Project Setup

### File: `pyproject.toml`

```toml
[tool.poetry]
name = "finance"
version = "0.1.0"
description = "Financial data pipeline -- automated scraping and AI analysis of TASE company reports"
authors = ["Amir Oliker"]
readme = "README.md"
packages = [{include = "src"}, {include = "cli"}]

[tool.poetry.scripts]
finance = "cli.main:app"

[tool.poetry.dependencies]
python = "^3.10"
pydantic = "^2.6"
pydantic-settings = "^2.2"
typer = {extras = ["all"], version = "^0.12"}
rich = "^13.7"
pyyaml = "^6.0"
python-dotenv = "^1.0"
pdfplumber = "^0.11"
pandas = "^2.2"
openpyxl = "^3.1"
playwright = "^1.44"
beautifulsoup4 = "^4.12"
requests = "^2.31"
httpx = "^0.27"
google-generativeai = "^0.8"
ollama = "^0.3"
anthropic = "^0.34"
openai = "^1.40"
flask = "^3.0"
flask-socketio = "^5.3"
google-auth-oauthlib = "^1.2"
google-api-python-client = "^2.142"

[tool.poetry.group.dev.dependencies]
pytest = "^8.2"
pytest-asyncio = "^0.23"
pytest-cov = "^5.0"
ruff = "^0.5"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 120
target-version = "py310"
```

### Key decisions:
- `packages = [{include = "src"}, {include = "cli"}]` -- both packages importable
- `finance` CLI entry point via `cli.main:app` (Typer app)
- All AI providers included as dependencies even if initially disabled
- Dev dependencies include ruff for linting, pytest-asyncio for future async tests

---

## Task 2: Pydantic v2 Data Models

### File: `src/models/__init__.py`

```python
from .company import Company, CompanyType, PriorityTier
from .document import DocumentMetadata, DocumentType
from .financial import FinancialPeriod, IncomeStatement, BalanceSheet, CashFlow, PerShareData
from .kpi import KPIMetrics
from .memo import InvestmentMemo, Scenario, Risk, Catalyst
from .research import MarketResearch, SWOT, CompSet, IndustryTrend
from .job import PipelineJob, StepResult, StepName

__all__ = [
    "Company", "CompanyType", "PriorityTier",
    "DocumentMetadata", "DocumentType",
    "FinancialPeriod", "IncomeStatement", "BalanceSheet", "CashFlow", "PerShareData",
    "KPIMetrics",
    "InvestmentMemo", "Scenario", "Risk", "Catalyst",
    "MarketResearch", "SWOT", "CompSet", "IndustryTrend",
    "PipelineJob", "StepResult", "StepName",
]
```

### File: `src/models/company.py`

```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class CompanyType(str, Enum):
    US_TRADED = "us_traded"
    TASE_TRADED = "tase_traded"
    PRIVATE = "private"

class PriorityTier(str, Enum):
    HIGH = "high"
    LOW = "low"

class Company(BaseModel):
    """Company definition loaded from companies.yaml."""
    slug: str
    name: str
    company_type: CompanyType = CompanyType.TASE_TRADED
    priority: PriorityTier = PriorityTier.LOW
    sector: str = ""

    # TASE identifiers
    tase_id: Optional[str] = None
    tase_company_id: Optional[str] = None

    # US listing
    us_ticker: Optional[str] = None
    us_exchange: Optional[str] = None       # "NASDAQ", "NYSE"

    # IR website
    ir_url: Optional[str] = None
    ir_platform: Optional[str] = None       # "wordpress", "q4", "notified", "generic"

    # Financial
    reporting_currency: str = "ILS"
    dual_listed: bool = False
```

**Porting notes:** The v2 `src/registry/company.py` Company dataclass has 12 fields. The new Pydantic model adds `company_type` (new requirement from master plan) and keeps all existing fields. Validation is automatic via Pydantic.

### File: `src/models/document.py`

```python
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
```

**Porting notes:** Based on v2 `src/models/report.py` ReportMetadata dataclass. Adds `document_type` enum (was just a string), `downloaded_at` timestamp, `file_size_bytes`.

### File: `src/models/financial.py`

```python
from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field

class IncomeStatement(BaseModel):
    """~25 line items for a professional income statement."""
    revenue: Optional[float] = None
    cost_of_revenue: Optional[float] = None
    gross_profit: Optional[float] = None

    rd_expense: Optional[float] = None
    sga_expense: Optional[float] = None
    depreciation_amortization: Optional[float] = None
    other_operating_expense: Optional[float] = None
    total_operating_expense: Optional[float] = None

    operating_income: Optional[float] = None
    interest_income: Optional[float] = None
    interest_expense: Optional[float] = None
    other_income_expense: Optional[float] = None
    pretax_income: Optional[float] = None

    income_tax: Optional[float] = None
    minority_interest: Optional[float] = None
    net_income: Optional[float] = None

    ebitda: Optional[float] = None
    adjusted_ebitda: Optional[float] = None

    # Per-share (convenience, also in PerShareData)
    eps_basic: Optional[float] = None
    eps_diluted: Optional[float] = None

    # Share count
    weighted_avg_shares_basic: Optional[float] = None
    weighted_avg_shares_diluted: Optional[float] = None

    # Stock-based comp (add-back for adjusted metrics)
    stock_based_compensation: Optional[float] = None

class BalanceSheet(BaseModel):
    """~30 line items for a professional balance sheet."""
    # Current Assets
    cash_and_equivalents: Optional[float] = None
    short_term_investments: Optional[float] = None
    accounts_receivable: Optional[float] = None
    inventory: Optional[float] = None
    prepaid_expenses: Optional[float] = None
    other_current_assets: Optional[float] = None
    total_current_assets: Optional[float] = None

    # Non-Current Assets
    ppe_gross: Optional[float] = None
    accumulated_depreciation: Optional[float] = None
    ppe_net: Optional[float] = None
    goodwill: Optional[float] = None
    intangible_assets: Optional[float] = None
    right_of_use_assets: Optional[float] = None
    long_term_investments: Optional[float] = None
    deferred_tax_assets: Optional[float] = None
    other_non_current_assets: Optional[float] = None
    total_non_current_assets: Optional[float] = None

    total_assets: Optional[float] = None

    # Current Liabilities
    accounts_payable: Optional[float] = None
    short_term_debt: Optional[float] = None
    current_portion_long_term_debt: Optional[float] = None
    accrued_liabilities: Optional[float] = None
    deferred_revenue: Optional[float] = None
    other_current_liabilities: Optional[float] = None
    total_current_liabilities: Optional[float] = None

    # Non-Current Liabilities
    long_term_debt: Optional[float] = None
    lease_liabilities: Optional[float] = None
    deferred_tax_liabilities: Optional[float] = None
    other_non_current_liabilities: Optional[float] = None
    total_non_current_liabilities: Optional[float] = None

    total_liabilities: Optional[float] = None

    # Equity
    common_stock: Optional[float] = None
    additional_paid_in_capital: Optional[float] = None
    retained_earnings: Optional[float] = None
    accumulated_other_comprehensive_income: Optional[float] = None
    treasury_stock: Optional[float] = None
    minority_interest: Optional[float] = None
    total_equity: Optional[float] = None

class CashFlow(BaseModel):
    """~25 line items for a professional cash flow statement (indirect method)."""
    # Operating Activities
    net_income: Optional[float] = None
    depreciation_amortization: Optional[float] = None
    stock_based_compensation: Optional[float] = None
    deferred_taxes: Optional[float] = None
    change_in_working_capital: Optional[float] = None
    change_in_accounts_receivable: Optional[float] = None
    change_in_inventory: Optional[float] = None
    change_in_accounts_payable: Optional[float] = None
    other_operating_activities: Optional[float] = None
    cash_from_operations: Optional[float] = None  # CFO

    # Investing Activities
    capex: Optional[float] = None
    acquisitions: Optional[float] = None
    purchases_of_investments: Optional[float] = None
    sales_of_investments: Optional[float] = None
    other_investing_activities: Optional[float] = None
    cash_from_investing: Optional[float] = None   # CFI

    # Financing Activities
    debt_issuance: Optional[float] = None
    debt_repayment: Optional[float] = None
    equity_issuance: Optional[float] = None
    share_repurchases: Optional[float] = None
    dividends_paid: Optional[float] = None
    other_financing_activities: Optional[float] = None
    cash_from_financing: Optional[float] = None    # CFF

    # Summary
    net_change_in_cash: Optional[float] = None
    free_cash_flow: Optional[float] = None         # CFO - CapEx

class PerShareData(BaseModel):
    """Per-share metrics."""
    shares_outstanding_basic: Optional[float] = None
    shares_outstanding_diluted: Optional[float] = None
    eps_basic: Optional[float] = None
    eps_diluted: Optional[float] = None
    dps: Optional[float] = None                    # Dividends per share
    bvps: Optional[float] = None                   # Book value per share
    fcf_per_share: Optional[float] = None
    share_price: Optional[float] = None
    market_cap: Optional[float] = None

class FinancialPeriod(BaseModel):
    """A complete set of financial data for one period."""
    company_slug: str
    fiscal_year: int
    period_type: str                                # "FY", "Q1", "Q2", "Q3", "Q4", "H1", "H2", "TTM"
    period_end_date: Optional[date] = None
    currency: str = "ILS"
    units: str = "thousands"                        # "thousands", "millions", "units"

    income_statement: IncomeStatement = Field(default_factory=IncomeStatement)
    balance_sheet: BalanceSheet = Field(default_factory=BalanceSheet)
    cash_flow: CashFlow = Field(default_factory=CashFlow)
    per_share: PerShareData = Field(default_factory=PerShareData)

    source_file: str = ""
    source_provider: str = ""
    extracted_at: Optional[str] = None
    confidence: Optional[float] = None
```

**Porting notes:** The v2 `src/models/financial.py` used flat FinancialMetric rows and metric name lists. The new design uses structured nested models (IS/BS/CF/PerShare) inside FinancialPeriod. The old metric lists (`INCOME_STATEMENT_METRICS` etc.) informed the field names. Expanded from ~13 IS fields to ~24, ~17 BS fields to ~30, ~9 CF fields to ~25.

### File: `src/models/kpi.py`

```python
from typing import Optional
from pydantic import BaseModel

class KPIMetrics(BaseModel):
    """Calculated KPI metrics derived from FinancialPeriod data."""

    # Margins (as decimals, e.g. 0.25 = 25%)
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    ebitda_margin: Optional[float] = None
    net_margin: Optional[float] = None
    rd_pct_revenue: Optional[float] = None
    sga_pct_revenue: Optional[float] = None

    # Growth rates (YoY, as decimals)
    revenue_growth: Optional[float] = None
    ebitda_growth: Optional[float] = None
    net_income_growth: Optional[float] = None
    eps_growth: Optional[float] = None

    # Profitability
    roe: Optional[float] = None                 # Return on equity
    roa: Optional[float] = None                 # Return on assets
    roic: Optional[float] = None                # Return on invested capital

    # Leverage
    debt_to_equity: Optional[float] = None
    net_debt_to_ebitda: Optional[float] = None
    interest_coverage: Optional[float] = None

    # Liquidity
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None

    # Working Capital Efficiency
    dso: Optional[float] = None                 # Days sales outstanding
    dio: Optional[float] = None                 # Days inventory outstanding
    dpo: Optional[float] = None                 # Days payable outstanding
    cash_conversion_cycle: Optional[float] = None

    # Valuation Multiples (require market data)
    pe_ratio: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    price_to_book: Optional[float] = None
    price_to_sales: Optional[float] = None
    price_to_fcf: Optional[float] = None
    dividend_yield: Optional[float] = None

    @classmethod
    def calculate(
        cls,
        current: "FinancialPeriod",
        prior: "FinancialPeriod | None" = None,
    ) -> "KPIMetrics":
        """Calculate all KPI metrics from financial period data.

        Args:
            current: Current period's financial data.
            prior: Prior period's financial data (for growth rates).
        """
        from .financial import FinancialPeriod

        kpi = cls()
        inc = current.income_statement
        bs = current.balance_sheet
        cf = current.cash_flow
        ps = current.per_share

        # --- Margins ---
        if inc.revenue and inc.revenue != 0:
            if inc.gross_profit is not None:
                kpi.gross_margin = inc.gross_profit / inc.revenue
            if inc.operating_income is not None:
                kpi.operating_margin = inc.operating_income / inc.revenue
            if inc.ebitda is not None:
                kpi.ebitda_margin = inc.ebitda / inc.revenue
            if inc.net_income is not None:
                kpi.net_margin = inc.net_income / inc.revenue
            if inc.rd_expense is not None:
                kpi.rd_pct_revenue = abs(inc.rd_expense) / inc.revenue
            if inc.sga_expense is not None:
                kpi.sga_pct_revenue = abs(inc.sga_expense) / inc.revenue

        # --- Profitability ---
        if inc.net_income is not None:
            if bs.total_equity and bs.total_equity != 0:
                kpi.roe = inc.net_income / bs.total_equity
            if bs.total_assets and bs.total_assets != 0:
                kpi.roa = inc.net_income / bs.total_assets

        if inc.operating_income is not None and inc.income_tax is not None:
            nopat = inc.operating_income * (1 - abs(inc.income_tax) / max(abs(inc.pretax_income or 1), 1))
            invested_capital = (bs.total_equity or 0) + (bs.long_term_debt or 0) - (bs.cash_and_equivalents or 0)
            if invested_capital and invested_capital != 0:
                kpi.roic = nopat / invested_capital

        # --- Leverage ---
        total_debt = (bs.short_term_debt or 0) + (bs.long_term_debt or 0)
        if bs.total_equity and bs.total_equity != 0:
            kpi.debt_to_equity = total_debt / bs.total_equity
        if inc.ebitda and inc.ebitda != 0:
            net_debt = total_debt - (bs.cash_and_equivalents or 0)
            kpi.net_debt_to_ebitda = net_debt / inc.ebitda
        if inc.interest_expense and inc.interest_expense != 0:
            kpi.interest_coverage = (inc.operating_income or 0) / abs(inc.interest_expense)

        # --- Liquidity ---
        if bs.total_current_liabilities and bs.total_current_liabilities != 0:
            if bs.total_current_assets is not None:
                kpi.current_ratio = bs.total_current_assets / bs.total_current_liabilities
            quick_assets = (bs.cash_and_equivalents or 0) + (bs.short_term_investments or 0) + (bs.accounts_receivable or 0)
            kpi.quick_ratio = quick_assets / bs.total_current_liabilities

        # --- Working Capital Efficiency ---
        if inc.revenue and inc.revenue != 0:
            annualized_revenue = inc.revenue  # Caller should annualize if quarterly
            daily_revenue = annualized_revenue / 365
            if bs.accounts_receivable is not None and daily_revenue != 0:
                kpi.dso = bs.accounts_receivable / daily_revenue

        if inc.cost_of_revenue and inc.cost_of_revenue != 0:
            daily_cogs = abs(inc.cost_of_revenue) / 365
            if bs.inventory is not None and daily_cogs != 0:
                kpi.dio = bs.inventory / daily_cogs
            if bs.accounts_payable is not None and daily_cogs != 0:
                kpi.dpo = bs.accounts_payable / daily_cogs

        if kpi.dso is not None and kpi.dio is not None and kpi.dpo is not None:
            kpi.cash_conversion_cycle = kpi.dso + kpi.dio - kpi.dpo

        # --- Growth rates (require prior period) ---
        if prior is not None:
            p_inc = prior.income_statement
            p_ps = prior.per_share

            def _growth(current_val: float | None, prior_val: float | None) -> float | None:
                if current_val is not None and prior_val is not None and prior_val != 0:
                    return (current_val - prior_val) / abs(prior_val)
                return None

            kpi.revenue_growth = _growth(inc.revenue, p_inc.revenue)
            kpi.ebitda_growth = _growth(inc.ebitda, p_inc.ebitda)
            kpi.net_income_growth = _growth(inc.net_income, p_inc.net_income)
            kpi.eps_growth = _growth(ps.eps_diluted or inc.eps_diluted, p_ps.eps_diluted or p_inc.eps_diluted)

        # --- Valuation multiples (require market data) ---
        if ps.share_price is not None and ps.share_price > 0:
            if (ps.eps_diluted or inc.eps_diluted) and (ps.eps_diluted or inc.eps_diluted) != 0:
                kpi.pe_ratio = ps.share_price / (ps.eps_diluted or inc.eps_diluted)
            if ps.bvps and ps.bvps != 0:
                kpi.price_to_book = ps.share_price / ps.bvps
            if ps.fcf_per_share and ps.fcf_per_share != 0:
                kpi.price_to_fcf = ps.share_price / ps.fcf_per_share
            if ps.dps is not None:
                kpi.dividend_yield = ps.dps / ps.share_price

        if ps.market_cap is not None and ps.market_cap > 0:
            if inc.revenue and inc.revenue != 0:
                kpi.price_to_sales = ps.market_cap / inc.revenue
            if inc.ebitda and inc.ebitda != 0:
                total_debt = (bs.short_term_debt or 0) + (bs.long_term_debt or 0)
                ev = ps.market_cap + total_debt - (bs.cash_and_equivalents or 0)
                kpi.ev_to_ebitda = ev / inc.ebitda

        return kpi
```

**Porting notes:** The v1 `code/src/models/financial_parser.py` KPIMetrics only had 6 ratios (net_margin, operating_margin, ebitda_margin, debt_to_equity, debt_to_assets, cash_ratio). The new version expands to 26 metrics across 7 categories: margins (6), growth (4), profitability (3), leverage (3), liquidity (2), working capital (4), valuation (6). The `calculate()` classmethod replaces the standalone `calculate_kpis()` function.

### File: `src/models/memo.py`

```python
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class Scenario(BaseModel):
    """Bull/Base/Bear scenario for price target."""
    name: str                                   # "bull", "base", "bear"
    probability_pct: float                      # 0-100
    target_price: Optional[float] = None
    currency: str = "USD"
    description: str = ""
    key_assumptions: List[str] = Field(default_factory=list)
    catalyst_or_risk: str = ""

class Risk(BaseModel):
    """Categorized risk with severity and mitigation."""
    category: str                               # "operational", "market", "financial", "regulatory"
    severity: str                               # "high", "medium", "low"
    description: str = ""
    mitigation: Optional[str] = None
    monitoring_trigger: Optional[str] = None

class Catalyst(BaseModel):
    """Event that could move the stock."""
    description: str
    timeframe: str = ""                         # "near_term", "medium_term", "long_term"
    expected_date: Optional[str] = None
    impact: str = "positive"                    # "positive", "negative"
    probability: Optional[str] = None           # "high", "medium", "low"

class InvestmentMemo(BaseModel):
    """Professional buy-side investment memo with 13 sections."""
    company_slug: str
    last_updated: Optional[datetime] = None
    recommendation: str = "monitor"             # "buy", "hold", "sell", "monitor"
    conviction: str = "low"                     # "high", "medium", "low"
    thesis_status: str = "new"                  # "new", "intact", "strengthening", "weakening", "broken"

    # 13 Sections
    header: str = ""                            # Sec 1: Company, ticker, price, rec, target, conviction
    executive_summary: str = ""                 # Sec 2: One-line thesis + 2-3 paragraphs
    company_overview: str = ""                  # Sec 3: Business, revenue model, customers, geography
    industry_analysis: str = ""                 # Sec 4: TAM/SAM/SOM, growth drivers, regulatory
    competitive_positioning: str = ""           # Sec 5: Competitor table, SWOT
    management_governance: str = ""             # Sec 6: Key execs, insider ownership, capital allocation
    financial_analysis: str = ""                # Sec 7: Key metrics table, ratio trends, margins
    valuation: str = ""                         # Sec 8: DCF summary, comps, implied range
    scenario_analysis: str = ""                 # Sec 9: Narrative for bull/base/bear
    risks_mitigants: str = ""                   # Sec 10: Narrative for categorized risks
    catalysts_timeline: str = ""                # Sec 11: Near/medium/long-term catalysts
    open_questions: str = ""                    # Sec 12: Unresolved questions
    appendix: str = ""                          # Sec 13: Model outputs, comps table, DCF sensitivity

    # Structured sub-objects
    scenarios: List[Scenario] = Field(default_factory=list)
    risks: List[Risk] = Field(default_factory=list)
    catalysts: List[Catalyst] = Field(default_factory=list)
```

**Porting notes:** The v2 `src/models/memo.py` InvestmentMemo had 7 narrative fields. The new version has 13 sections matching the master plan spec. Adds Catalyst model (new). Renames RiskEntry to Risk, ThesisEvent removed (replaced by catalysts_timeline section).

### File: `src/models/research.py`

```python
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
    direction: str = "tailwind"                 # "tailwind", "headwind", "neutral"
    time_horizon: str = ""                      # "short_term", "medium_term", "long_term"
    impact_description: str = ""
    data_points: List[str] = Field(default_factory=list)

class MarketResearch(BaseModel):
    """Aggregated market research for a company."""
    company_slug: str

    # Market sizing
    tam: Optional[float] = None                 # Total addressable market ($)
    sam: Optional[float] = None                 # Serviceable addressable market
    som: Optional[float] = None                 # Serviceable obtainable market
    market_growth_rate: Optional[float] = None
    market_sizing_methodology: str = ""

    # Analysis objects
    swot: SWOT = Field(default_factory=SWOT)
    comp_set: CompSet = Field(default_factory=CompSet)
    industry_trends: List[IndustryTrend] = Field(default_factory=list)

    # Sources
    sources: List[str] = Field(default_factory=list)
    last_updated: Optional[str] = None
```

**Porting notes:** Entirely new. No v1/v2 equivalent. Supports the market research sub-functions defined in the master plan (TAM/SAM/SOM, SWOT, comps, industry trends).

### File: `src/models/job.py`

```python
from enum import Enum
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class StepName(str, Enum):
    DOWNLOAD = "download"
    PARSE = "parse"
    MODEL = "model"
    MEMO = "memo"
    UPLOAD = "upload"

class StepResult(BaseModel):
    """Result of a single pipeline step execution."""
    step: StepName
    status: str = "pending"                     # "pending", "running", "success", "failed", "skipped"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    artifacts: List[str] = Field(default_factory=list)  # File paths produced
    metadata: dict = Field(default_factory=dict)        # Step-specific info

class PipelineJob(BaseModel):
    """Tracks a full pipeline run for one company."""
    job_id: str
    company_slug: str
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "pending"                     # "pending", "running", "completed", "failed"
    steps: List[StepResult] = Field(default_factory=list)
    requested_steps: List[StepName] = Field(default_factory=list)
    provider_override: Optional[str] = None
    error: Optional[str] = None

    @property
    def current_step(self) -> Optional[StepResult]:
        for s in self.steps:
            if s.status == "running":
                return s
        return None

    @property
    def progress_pct(self) -> float:
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.status in ("success", "skipped"))
        return completed / len(self.steps) * 100
```

**Porting notes:** New model. The v2 pipeline orchestrator tracked status via prints. This model enables the EventBus progress tracking planned for Phase 4.

---

## Task 3: Config Directory + Loader

### File: `config/companies.yaml`

Migrated from existing with `company_type` added. Structure:

```yaml
companies:
  - slug: enlight
    name: Enlight Renewable Energy
    company_type: tase_traded      # NEW FIELD
    tase_id: "720"
    tase_company_id: "720"
    us_ticker: ENLT
    us_exchange: NASDAQ
    ir_url: https://enlightenergy.co.il/investors/financial-reports/
    ir_platform: wordpress
    priority: high
    reporting_currency: ILS
    sector: renewable_energy
    dual_listed: true
  # ... all 18 existing companies with company_type inferred:
  # dual_listed=true + us_ticker -> us_traded  (enlight, ormat, ellomay, sofwave, brainsway)
  # tase_company_id + no us_ticker -> tase_traded  (rest)
```

**Migration rule:** For each existing company:
- If `dual_listed: true` and `us_ticker` is set: `company_type: us_traded`
- If `tase_company_id` is set and not dual-listed: `company_type: tase_traded`
- Otherwise: `company_type: private`

### File: `config/providers.yaml`

Extended from existing with routing table:

```yaml
providers:
  gemini:
    type: google
    model: gemini-2.0-flash
    api_key_env: GOOGLE_API_KEY
    max_retries: 3
    rate_limit_delay: 10
    enabled: true

  ollama:
    type: ollama
    model: qwen2.5:7b
    host_env: OLLAMA_HOST
    host_default: "http://localhost:11434"
    fallback_model: llama3.1
    enabled: true
    auto_detect_models: true         # NEW: discover available models at startup

  anthropic:
    type: anthropic
    model: claude-sonnet-4-20250514
    api_key_env: ANTHROPIC_API_KEY
    enabled: false

  openai:
    type: openai
    model: gpt-4o
    api_key_env: OPENAI_API_KEY
    enabled: false

routing:                               # NEW: task routing table
  classify:
    primary: ollama
    fallback: [gemini]
  extract:
    primary: ollama
    fallback: [gemini]
    validation: gemini
  memo:
    primary: gemini
    fallback: [ollama]
  research:
    primary: gemini
    fallback: []
```

### File: `config/settings.yaml`

```yaml
pipeline:
  data_dir: data/companies
  downloads_dir: downloads
  output_dir: output
  max_concurrent_companies: 3
  default_years_back: 1

scraping:
  tase_timeout_seconds: 120
  tase_max_pages: 8
  page_load_timeout: 30000
  headless: true

web:
  host: 0.0.0.0
  port: 8050
  debug: false

scheduler:
  high_priority_interval_hours: 24
  low_priority_interval_hours: 168
  enabled: false

logging:
  level: INFO
  format: structured
  log_dir: logs
```

### File: `src/config/__init__.py`

```python
from .loader import load_companies, load_providers_config, load_settings
from .settings import Settings, get_settings
```

### File: `src/config/loader.py`

```python
"""YAML configuration loader with Pydantic validation."""

import yaml
from pathlib import Path
from typing import List, Dict, Any

from ..models.company import Company

def _find_project_root() -> Path:
    """Walk up from this file to find project root (contains pyproject.toml or config/)."""
    current = Path(__file__).resolve().parent
    for _ in range(5):
        if (current / "config").is_dir():
            return current
        current = current.parent
    raise FileNotFoundError("Could not find project root")

def _load_yaml(filename: str) -> dict:
    """Load a YAML file from config/ directory."""
    root = _find_project_root()
    path = root / "config" / filename
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r") as f:
        return yaml.safe_load(f)

def load_companies() -> Dict[str, Company]:
    """Load and validate all companies from companies.yaml."""
    data = _load_yaml("companies.yaml")
    companies = {}
    for entry in data.get("companies", []):
        company = Company.model_validate(entry)
        companies[company.slug] = company
    return companies

def load_providers_config() -> Dict[str, Any]:
    """Load raw provider configuration."""
    return _load_yaml("providers.yaml")

def load_settings() -> dict:
    """Load settings.yaml."""
    return _load_yaml("settings.yaml")
```

### File: `src/config/settings.py`

```python
"""Application settings with environment variable support."""

from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings

class PipelineSettings(BaseSettings):
    data_dir: str = "data/companies"
    downloads_dir: str = "downloads"
    output_dir: str = "output"
    max_concurrent_companies: int = 3
    default_years_back: int = 1

class ScrapingSettings(BaseSettings):
    tase_timeout_seconds: int = 120
    tase_max_pages: int = 8
    page_load_timeout: int = 30000
    headless: bool = True

class WebSettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8050
    debug: bool = False

class Settings(BaseSettings):
    """Top-level application settings."""
    model_config = {"env_prefix": "FINANCE_"}

    # API Keys (from .env)
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    ollama_host: str = Field(default="http://localhost:11434", alias="OLLAMA_HOST")

    # Sub-settings
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    scraping: ScrapingSettings = Field(default_factory=ScrapingSettings)
    web: WebSettings = Field(default_factory=WebSettings)

    # Project root (computed)
    project_root: Optional[str] = None

    def resolve_data_dir(self) -> Path:
        root = Path(self.project_root) if self.project_root else Path.cwd()
        return root / self.pipeline.data_dir

_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Get or create singleton settings instance."""
    global _settings
    if _settings is None:
        from dotenv import load_dotenv
        load_dotenv()
        _settings = Settings()
    return _settings
```

---

## Task 4: Storage Layer

### File: `src/storage/__init__.py`

```python
from .paths import CompanyPaths
from .file_manager import FileManager
```

### File: `src/storage/paths.py`

```python
"""Centralized path conventions for data/companies/<slug>/."""

from pathlib import Path
from typing import Optional

class CompanyPaths:
    """All file paths for a single company's data."""

    def __init__(self, slug: str, data_root: Optional[Path] = None):
        if data_root is None:
            # Default: <project_root>/data/companies
            data_root = Path(__file__).resolve().parent.parent.parent / "data" / "companies"
        self.slug = slug
        self.root = data_root / slug
        self.reports_dir = self.root / "reports"

    def ensure_dirs(self) -> None:
        """Create all required directories."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    # --- Artifact paths ---

    @property
    def financials_json(self) -> Path:
        return self.root / "financials.json"

    @property
    def memo_md(self) -> Path:
        return self.root / "Investment_Memo.md"

    @property
    def memo_json(self) -> Path:
        return self.root / "memo.json"

    @property
    def model_xlsx(self) -> Path:
        return self.root / "Financial_Model.xlsx"

    @property
    def meta_json(self) -> Path:
        return self.root / "meta.json"

    @property
    def research_json(self) -> Path:
        return self.root / "research.json"

    @property
    def kpi_json(self) -> Path:
        return self.root / "kpi.json"

    def report_path(self, year: int, period: str, report_id: str, ext: str = "pdf") -> Path:
        """Path for a specific report file."""
        filename = f"{year}_{period}_{report_id}.{ext}"
        return self.reports_dir / filename

    def period_dir(self, year: int, period: str) -> Path:
        """Directory for period-specific downloads (for Drive upload)."""
        d = self.root / f"{year}-{period}"
        d.mkdir(parents=True, exist_ok=True)
        return d
```

**Porting notes:** The v2 `src/storage/paths.py` used module-level functions. The new design uses a `CompanyPaths` class for better encapsulation. Adds `model_xlsx`, `memo_md`, `research_json`, `kpi_json` paths (new artifacts). Changes `financials.csv` to `financials.json` (Pydantic models serialize to JSON natively).

### File: `src/storage/file_manager.py`

```python
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
        # Replace if same period exists, otherwise append
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
```

**Porting notes:** Based on v2 `src/storage/file_manager.py`. Changes: uses Pydantic `model_validate`/`model_dump` instead of manual dict conversion, uses `pathlib.Path` throughout, adds KPI and Research CRUD methods, uses JSON instead of CSV for financials.

---

## Task 5: Utility Modules

### File: `src/utils/__init__.py`

```python
from .pdf import extract_financial_pages, score_page
from .json_fix import fix_json_numbers, extract_json_from_response
from .currency import ils_to_usd, usd_to_ils
from .logging import get_logger
```

### File: `src/utils/pdf.py`

```python
"""PDF text extraction and financial page scoring heuristic.

Ported from: code/src/intelligence/extractor.py -> _extract_financial_pages()
"""

import re
from typing import List, Tuple
from pathlib import Path

# Keywords that indicate financial table pages (Hebrew + English)
FINANCIAL_TABLE_KEYWORDS = [
    # Hebrew keywords for financial statements
    "תוסנכה", "דספה", "חוור", "םיסכנ", "תויובייחתה", "ןוה",
    "םינמוזמ", "יפסכה בצמה", "ימירזת", "ללוכה דספהה",
    # English keywords
    "revenue", "income", "loss", "assets", "liabilities", "equity",
    "cash flow", "consolidated", "balance sheet", "total assets",
    "financial position", "comprehensive loss",
]


def score_page(text: str, page_index: int, total_pages: int) -> int:
    """Score a page for financial content.

    Returns an integer score. Higher = more likely to contain financial tables.
    Threshold for inclusion is typically > 10.

    Args:
        text: Extracted text from the page.
        page_index: 0-based page index.
        total_pages: Total number of pages in the document.
    """
    if len(text.strip()) < 50:
        return 0

    score = 0

    # Count numbers (financial tables have many)
    numbers = re.findall(r"[\d,]{3,}", text)
    score += min(len(numbers), 20)

    # Check for financial keywords
    text_lower = text.lower()
    for kw in FINANCIAL_TABLE_KEYWORDS:
        if kw in text or kw in text_lower:
            score += 5

    # Bonus for pages in the latter half
    if total_pages > 0 and page_index > total_pages * 0.5:
        score += 3

    # Bonus for table-like structure (tab/space separated numbers)
    if len(re.findall(r"\d+\s+\d+", text)) > 3:
        score += 8

    return score


def extract_financial_pages(file_path: str | Path, max_chars: int = 12000) -> str:
    """Extract only the pages containing financial tables from a PDF.

    Strategy: Score each page for financial content, select the best ones
    up to the character budget.

    Args:
        file_path: Path to the PDF file.
        max_chars: Maximum characters to return.

    Returns:
        Concatenated text from financial pages, with page markers.
    """
    import pdfplumber

    with pdfplumber.open(str(file_path)) as pdf:
        total_pages = len(pdf.pages)

        # Score each page
        scored_pages: List[Tuple[int, int, str]] = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            page_score = score_page(text, i, total_pages)
            if page_score > 10:
                scored_pages.append((page_score, i, text))

        # Sort by score descending, take top pages
        scored_pages.sort(key=lambda x: -x[0])

        # Reassemble in page order, limited by char budget
        selected_indices = sorted([p[1] for p in scored_pages[:15]])

        result = ""
        for idx in selected_indices:
            text = pdf.pages[idx].extract_text() or ""
            if len(result) + len(text) > max_chars:
                break
            result += f"\n=== Page {idx + 1} of {total_pages} ===\n{text}\n"

        if not result:
            # Fallback: last 30% of pages
            start_page = int(total_pages * 0.6)
            for i in range(start_page, total_pages):
                text = pdf.pages[i].extract_text() or ""
                if len(result) + len(text) > max_chars:
                    break
                result += f"\n=== Page {i + 1} ===\n{text}\n"

        return result


def extract_all_text(file_path: str | Path) -> str:
    """Extract all text from a PDF."""
    import pdfplumber

    parts = []
    with pdfplumber.open(str(file_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n".join(parts)
```

**Porting notes:** Direct port from `code/src/intelligence/extractor.py` `_extract_financial_pages()` and `FINANCIAL_TABLE_KEYWORDS`. Refactored into standalone functions. Added `score_page()` as a separate public function for testability. Added `extract_all_text()` convenience function.

### File: `src/utils/json_fix.py`

```python
"""Fix common LLM JSON output issues.

Ported from: code/src/intelligence/extractor.py -> _fix_json_numbers(), _parse_response()
"""

import re
import json
from typing import Optional


def fix_json_numbers(json_str: str) -> str:
    """Fix common LLM JSON issues: comma-separated numbers and accounting notation.

    Handles:
    - Accounting notation: (1,234) -> -1234
    - Comma-separated numbers as JSON values: "revenue": 43,536 -> "revenue": 43536
    - Trailing commas before } or ]
    - JavaScript-style comments

    Args:
        json_str: Raw JSON string from LLM output.

    Returns:
        Cleaned JSON string.
    """
    # Fix accounting notation: (1,234) -> -1234
    json_str = re.sub(
        r"\((\d[\d,]*)\)",
        lambda m: "-" + m.group(1).replace(",", ""),
        json_str,
    )

    # Fix comma-separated numbers in JSON values: "key": 43,536 -> "key": 43536
    json_str = re.sub(
        r":\s*(-?\d{1,3}(?:,\d{3})+)(?=[,\s\n\r}])",
        lambda m: ": " + m.group(1).replace(",", ""),
        json_str,
    )

    # Remove JavaScript-style comments
    json_str = re.sub(r"//.*?$", "", json_str, flags=re.MULTILINE)

    # Remove trailing commas before } or ]
    json_str = re.sub(r",\s*([}\]])", r"\1", json_str)

    return json_str


def extract_json_from_response(response_text: str) -> Optional[dict]:
    """Extract and parse JSON from an LLM response that may contain markdown fences.

    Handles:
    - ```json ... ``` code blocks
    - ``` ... ``` code blocks
    - Raw JSON in the response
    - Comma/accounting number fixes

    Args:
        response_text: Raw LLM response text.

    Returns:
        Parsed dict, or None if parsing fails.
    """
    json_str = response_text

    # Handle markdown code blocks
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0]
    elif "```" in json_str:
        parts = json_str.split("```")
        if len(parts) >= 3:
            json_str = parts[1]

    # Find JSON boundaries
    start = json_str.find("{")
    end = json_str.rfind("}") + 1
    if start >= 0 and end > start:
        json_str = json_str[start:end]
    else:
        # Try array
        start = json_str.find("[")
        end = json_str.rfind("]") + 1
        if start >= 0 and end > start:
            json_str = json_str[start:end]
        else:
            return None

    # Apply fixes
    json_str = fix_json_numbers(json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def clean_numeric_value(value) -> Optional[float]:
    """Clean a value that should be numeric.

    Handles string values with commas, %, spaces, accounting notation.

    Args:
        value: Raw value from LLM extraction.

    Returns:
        Float value or None if not parseable.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    cleaned = value.replace(",", "").replace(" ", "").replace("%", "").strip()
    # Handle accounting notation
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None
```

**Porting notes:** Direct port from `code/src/intelligence/extractor.py` `_fix_json_numbers()` and `_parse_response()`. Refactored into three standalone functions. `extract_json_from_response()` combines markdown fence extraction, JSON boundary finding, and number fixing. `clean_numeric_value()` extracted from `_validate_and_clean()`.

### File: `src/utils/currency.py`

```python
"""Currency conversion helpers."""

from typing import Optional

# Approximate exchange rate (updated periodically)
# In production, this could fetch from an API
DEFAULT_ILS_USD_RATE = 3.65


def ils_to_usd(amount: Optional[float], rate: Optional[float] = None) -> Optional[float]:
    """Convert ILS amount to USD."""
    if amount is None:
        return None
    r = rate or DEFAULT_ILS_USD_RATE
    return round(amount / r, 2)


def usd_to_ils(amount: Optional[float], rate: Optional[float] = None) -> Optional[float]:
    """Convert USD amount to ILS."""
    if amount is None:
        return None
    r = rate or DEFAULT_ILS_USD_RATE
    return round(amount * r, 2)
```

### File: `src/utils/logging.py`

```python
"""Structured logging configuration."""

import logging
import sys
from pathlib import Path
from typing import Optional


def get_logger(
    name: str,
    level: int = logging.INFO,
    log_dir: Optional[str | Path] = None,
) -> logging.Logger:
    """Get a configured logger with console and optional file output.

    Args:
        name: Logger name (typically __name__).
        level: Logging level.
        log_dir: Optional directory for log files.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler (optional)
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path / f"{name}.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
```

---

## Task 6: CLI Skeleton (Typer)

### File: `cli/__init__.py`

```python
# CLI package
```

### File: `cli/main.py`

```python
"""Finance CLI -- Typer application entry point.

Usage:
    finance list [--type TYPE] [--priority PRIORITY]
    finance status [SLUG] [--failed]
    finance run <SLUG> [--step STEP] [--provider PROVIDER]
"""

import typer
from typing import Optional

app = typer.Typer(
    name="finance",
    help="Financial data pipeline -- TASE company analysis",
    no_args_is_help=True,
)


@app.command()
def list_companies(
    company_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by type: us_traded, tase_traded, private"),
    priority: Optional[str] = typer.Option(None, "--priority", "-p", help="Filter by priority: high, low"),
) -> None:
    """List all registered companies."""
    from cli.commands.list_cmd import run_list
    run_list(company_type=company_type, priority=priority)


@app.command(name="status")
def show_status(
    slug: Optional[str] = typer.Argument(None, help="Company slug"),
    failed: bool = typer.Option(False, "--failed", help="Show only failed companies"),
) -> None:
    """Show pipeline status for companies."""
    from cli.commands.status import run_status
    run_status(slug=slug, failed_only=failed)


if __name__ == "__main__":
    app()
```

### File: `cli/commands/__init__.py`

```python
# CLI commands package
```

### File: `cli/commands/list_cmd.py`

```python
"""finance list -- List registered companies."""

from typing import Optional
from rich.console import Console
from rich.table import Table

from src.config.loader import load_companies

console = Console()


def run_list(company_type: Optional[str] = None, priority: Optional[str] = None) -> None:
    """Display companies in a Rich table."""
    companies = load_companies()

    # Filter
    filtered = list(companies.values())
    if company_type:
        filtered = [c for c in filtered if c.company_type.value == company_type]
    if priority:
        filtered = [c for c in filtered if c.priority.value == priority]

    # Build table
    table = Table(title="Registered Companies")
    table.add_column("Slug", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Type", style="yellow")
    table.add_column("Priority", style="green")
    table.add_column("Currency")
    table.add_column("Ticker")
    table.add_column("Sector")

    for c in sorted(filtered, key=lambda x: (x.priority.value, x.slug)):
        table.add_row(
            c.slug,
            c.name,
            c.company_type.value,
            c.priority.value,
            c.reporting_currency,
            c.us_ticker or "-",
            c.sector,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(filtered)} companies[/dim]")
```

### File: `cli/commands/status.py`

```python
"""finance status -- Show pipeline status."""

from typing import Optional
from rich.console import Console
from rich.table import Table

from src.config.loader import load_companies
from src.storage.file_manager import FileManager

console = Console()


def run_status(slug: Optional[str] = None, failed_only: bool = False) -> None:
    """Display pipeline status in a Rich table."""
    companies = load_companies()

    if slug:
        if slug not in companies:
            console.print(f"[red]Company '{slug}' not found[/red]")
            return
        targets = {slug: companies[slug]}
    else:
        targets = companies

    table = Table(title="Pipeline Status")
    table.add_column("Company", style="cyan")
    table.add_column("Priority")
    table.add_column("Last Scrape")
    table.add_column("Reports", justify="right")
    table.add_column("Financials", justify="right")
    table.add_column("Memo")
    table.add_column("Status")

    for company_slug, company in sorted(targets.items()):
        fm = FileManager(company_slug)
        meta = fm.load_meta()

        last_scrape = meta.get("last_scrape", "Never")
        if last_scrape and last_scrape != "Never":
            last_scrape = last_scrape[:16]

        reports_count = meta.get("reports_downloaded", 0)
        financials = fm.load_financials()
        memo = fm.load_memo()

        scrape_status = meta.get("last_scrape_status", "-")
        if failed_only and scrape_status != "failed":
            continue

        status_style = "green" if scrape_status == "success" else "red" if scrape_status == "failed" else "dim"

        table.add_row(
            company.name,
            company.priority.value,
            str(last_scrape),
            str(reports_count),
            str(len(financials)),
            "[green]YES[/green]" if memo else "[dim]NO[/dim]",
            f"[{status_style}]{scrape_status}[/{status_style}]",
        )

    console.print(table)
```

---

## Task 7: .env.example and .gitignore

### File: `.env.example`

```bash
# Required: Google Gemini API key (primary AI provider)
GOOGLE_API_KEY=your_google_api_key_here

# Optional: Other AI providers
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Optional: Ollama host (defaults to http://localhost:11434)
OLLAMA_HOST=http://localhost:11434
```

### File: `.gitignore` (update existing)

Add to existing .gitignore:

```gitignore
# Existing entries preserved
__pycache__/
*.pyc
venv/
.env
downloads/
logs/
archive/
*.log
.DS_Store
token.pickle
credentials.json
output/

# New additions for v3
data/
*.egg-info/
dist/
build/
.pytest_cache/
.ruff_cache/
poetry.lock
.mypy_cache/
htmlcov/
.coverage
```

---

## Task 8: Test Infrastructure

### File: `tests/__init__.py`

```python
# Tests package
```

### File: `tests/conftest.py`

```python
"""Shared test fixtures for the finance pipeline test suite."""

import pytest
from pathlib import Path

from src.models.company import Company, CompanyType, PriorityTier
from src.models.financial import (
    FinancialPeriod, IncomeStatement, BalanceSheet, CashFlow, PerShareData,
)


@pytest.fixture
def sample_company() -> Company:
    return Company(
        slug="testco",
        name="Test Company Ltd",
        company_type=CompanyType.TASE_TRADED,
        priority=PriorityTier.HIGH,
        tase_company_id="1234",
        reporting_currency="ILS",
        sector="technology",
    )


@pytest.fixture
def sample_us_company() -> Company:
    return Company(
        slug="usco",
        name="US Company Inc",
        company_type=CompanyType.US_TRADED,
        priority=PriorityTier.HIGH,
        us_ticker="USCO",
        us_exchange="NASDAQ",
        reporting_currency="USD",
        sector="medical_devices",
        dual_listed=True,
    )


@pytest.fixture
def sample_income_statement() -> IncomeStatement:
    return IncomeStatement(
        revenue=100_000,
        cost_of_revenue=60_000,
        gross_profit=40_000,
        rd_expense=10_000,
        sga_expense=8_000,
        operating_income=22_000,
        interest_expense=2_000,
        pretax_income=20_000,
        income_tax=4_000,
        net_income=16_000,
        ebitda=28_000,
        eps_basic=1.60,
        eps_diluted=1.55,
    )


@pytest.fixture
def sample_balance_sheet() -> BalanceSheet:
    return BalanceSheet(
        cash_and_equivalents=25_000,
        short_term_investments=5_000,
        accounts_receivable=15_000,
        inventory=10_000,
        total_current_assets=60_000,
        ppe_net=50_000,
        goodwill=20_000,
        total_assets=150_000,
        accounts_payable=12_000,
        short_term_debt=5_000,
        total_current_liabilities=25_000,
        long_term_debt=30_000,
        total_liabilities=65_000,
        total_equity=85_000,
    )


@pytest.fixture
def sample_cash_flow() -> CashFlow:
    return CashFlow(
        net_income=16_000,
        depreciation_amortization=6_000,
        cash_from_operations=24_000,
        capex=-8_000,
        cash_from_investing=-12_000,
        cash_from_financing=-5_000,
        net_change_in_cash=7_000,
        free_cash_flow=16_000,
    )


@pytest.fixture
def sample_financial_period(
    sample_income_statement,
    sample_balance_sheet,
    sample_cash_flow,
) -> FinancialPeriod:
    return FinancialPeriod(
        company_slug="testco",
        fiscal_year=2025,
        period_type="FY",
        currency="ILS",
        units="thousands",
        income_statement=sample_income_statement,
        balance_sheet=sample_balance_sheet,
        cash_flow=sample_cash_flow,
        per_share=PerShareData(
            shares_outstanding_basic=10_000,
            shares_outstanding_diluted=10_300,
            eps_basic=1.60,
            eps_diluted=1.55,
            share_price=25.00,
            market_cap=250_000,
        ),
    )


@pytest.fixture
def prior_financial_period() -> FinancialPeriod:
    return FinancialPeriod(
        company_slug="testco",
        fiscal_year=2024,
        period_type="FY",
        currency="ILS",
        units="thousands",
        income_statement=IncomeStatement(
            revenue=85_000,
            ebitda=22_000,
            net_income=12_000,
            eps_diluted=1.20,
        ),
    )


@pytest.fixture
def tmp_data_dir(tmp_path) -> Path:
    """Create a temporary data directory for file manager tests."""
    data_dir = tmp_path / "data" / "companies"
    data_dir.mkdir(parents=True)
    return data_dir
```

### File: `tests/unit/__init__.py`

```python
# Unit tests package
```

### File: `tests/unit/test_models.py`

```python
"""Unit tests for Pydantic data models."""

import pytest
from datetime import datetime

from src.models.company import Company, CompanyType, PriorityTier
from src.models.document import DocumentMetadata, DocumentType
from src.models.financial import FinancialPeriod, IncomeStatement, BalanceSheet, CashFlow
from src.models.memo import InvestmentMemo, Scenario, Risk, Catalyst
from src.models.research import MarketResearch, SWOT, SWOTItem
from src.models.job import PipelineJob, StepResult, StepName


class TestCompanyModel:
    def test_basic_creation(self, sample_company):
        assert sample_company.slug == "testco"
        assert sample_company.company_type == CompanyType.TASE_TRADED
        assert sample_company.priority == PriorityTier.HIGH

    def test_us_traded_company(self, sample_us_company):
        assert sample_us_company.company_type == CompanyType.US_TRADED
        assert sample_us_company.us_ticker == "USCO"
        assert sample_us_company.dual_listed is True

    def test_defaults(self):
        c = Company(slug="min", name="Minimal Co")
        assert c.company_type == CompanyType.TASE_TRADED
        assert c.priority == PriorityTier.LOW
        assert c.reporting_currency == "ILS"
        assert c.dual_listed is False

    def test_serialization_roundtrip(self, sample_company):
        data = sample_company.model_dump()
        restored = Company.model_validate(data)
        assert restored == sample_company


class TestDocumentModel:
    def test_basic_creation(self):
        doc = DocumentMetadata(
            company_slug="enlight",
            year=2025,
            period="Q1",
            url="https://example.com/report.pdf",
            source="tase_maya",
        )
        assert doc.document_type == DocumentType.UNKNOWN
        assert doc.file_type == "pdf"

    def test_financial_document(self):
        doc = DocumentMetadata(
            company_slug="enlight",
            document_type=DocumentType.QUARTERLY_REPORT,
            year=2025,
            period="Q3",
            url="https://example.com/q3.pdf",
            source="ir_website",
            is_financial=True,
        )
        assert doc.is_financial is True
        assert doc.document_type == DocumentType.QUARTERLY_REPORT


class TestFinancialPeriod:
    def test_nested_models(self, sample_financial_period):
        fp = sample_financial_period
        assert fp.income_statement.revenue == 100_000
        assert fp.balance_sheet.total_assets == 150_000
        assert fp.cash_flow.free_cash_flow == 16_000
        assert fp.per_share.share_price == 25.00

    def test_all_optional_fields(self):
        fp = FinancialPeriod(
            company_slug="empty",
            fiscal_year=2025,
            period_type="Q1",
        )
        assert fp.income_statement.revenue is None
        assert fp.balance_sheet.total_assets is None

    def test_serialization(self, sample_financial_period):
        data = sample_financial_period.model_dump(mode="json")
        assert isinstance(data, dict)
        assert data["income_statement"]["revenue"] == 100_000
        restored = FinancialPeriod.model_validate(data)
        assert restored.income_statement.revenue == 100_000


class TestInvestmentMemo:
    def test_basic_creation(self):
        memo = InvestmentMemo(company_slug="testco")
        assert memo.recommendation == "monitor"
        assert memo.scenarios == []
        assert memo.risks == []

    def test_with_scenarios(self):
        memo = InvestmentMemo(
            company_slug="testco",
            scenarios=[
                Scenario(name="bull", probability_pct=25, target_price=40.0),
                Scenario(name="base", probability_pct=50, target_price=28.0),
                Scenario(name="bear", probability_pct=25, target_price=15.0),
            ],
        )
        assert len(memo.scenarios) == 3
        assert sum(s.probability_pct for s in memo.scenarios) == 100

    def test_with_risks(self):
        memo = InvestmentMemo(
            company_slug="testco",
            risks=[
                Risk(category="market", severity="high", description="Macro downturn"),
            ],
        )
        assert memo.risks[0].severity == "high"


class TestPipelineJob:
    def test_progress(self):
        job = PipelineJob(
            job_id="test-001",
            company_slug="testco",
            steps=[
                StepResult(step=StepName.DOWNLOAD, status="success"),
                StepResult(step=StepName.PARSE, status="running"),
                StepResult(step=StepName.MODEL, status="pending"),
            ],
        )
        assert job.progress_pct == pytest.approx(33.33, rel=0.1)
        assert job.current_step.step == StepName.PARSE


class TestResearchModels:
    def test_swot(self):
        swot = SWOT(
            strengths=[SWOTItem(point="Market leader", measurable_outcome="40% share")],
        )
        assert len(swot.strengths) == 1

    def test_market_research(self):
        mr = MarketResearch(
            company_slug="testco",
            tam=1_000_000_000,
            sam=200_000_000,
            som=50_000_000,
        )
        assert mr.som < mr.sam < mr.tam
```

### File: `tests/unit/test_kpi_calculations.py`

```python
"""Unit tests for KPI calculations.

These tests verify the KPIMetrics.calculate() classmethod produces correct
financial ratios from FinancialPeriod data.
"""

import pytest

from src.models.kpi import KPIMetrics
from src.models.financial import FinancialPeriod, IncomeStatement


class TestMarginCalculations:
    def test_gross_margin(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        assert kpi.gross_margin == pytest.approx(0.40, rel=1e-3)

    def test_operating_margin(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        assert kpi.operating_margin == pytest.approx(0.22, rel=1e-3)

    def test_ebitda_margin(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        assert kpi.ebitda_margin == pytest.approx(0.28, rel=1e-3)

    def test_net_margin(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        assert kpi.net_margin == pytest.approx(0.16, rel=1e-3)

    def test_rd_pct(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        assert kpi.rd_pct_revenue == pytest.approx(0.10, rel=1e-3)

    def test_sga_pct(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        assert kpi.sga_pct_revenue == pytest.approx(0.08, rel=1e-3)


class TestProfitabilityRatios:
    def test_roe(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        # ROE = 16,000 / 85,000 = 0.1882
        assert kpi.roe == pytest.approx(0.1882, rel=1e-2)

    def test_roa(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        # ROA = 16,000 / 150,000 = 0.1067
        assert kpi.roa == pytest.approx(0.1067, rel=1e-2)


class TestLeverageRatios:
    def test_debt_to_equity(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        # D/E = (5,000 + 30,000) / 85,000 = 0.4118
        assert kpi.debt_to_equity == pytest.approx(0.4118, rel=1e-2)

    def test_net_debt_to_ebitda(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        # Net debt = 35,000 - 25,000 = 10,000; Net Debt/EBITDA = 10,000 / 28,000 = 0.357
        assert kpi.net_debt_to_ebitda == pytest.approx(0.357, rel=1e-2)

    def test_interest_coverage(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        # Interest coverage = 22,000 / 2,000 = 11.0
        assert kpi.interest_coverage == pytest.approx(11.0, rel=1e-2)


class TestLiquidityRatios:
    def test_current_ratio(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        # Current ratio = 60,000 / 25,000 = 2.4
        assert kpi.current_ratio == pytest.approx(2.4, rel=1e-2)

    def test_quick_ratio(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        # Quick = (25,000 + 5,000 + 15,000) / 25,000 = 1.8
        assert kpi.quick_ratio == pytest.approx(1.8, rel=1e-2)


class TestGrowthRates:
    def test_revenue_growth(self, sample_financial_period, prior_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period, prior_financial_period)
        # Growth = (100,000 - 85,000) / 85,000 = 0.1765
        assert kpi.revenue_growth == pytest.approx(0.1765, rel=1e-2)

    def test_ebitda_growth(self, sample_financial_period, prior_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period, prior_financial_period)
        # Growth = (28,000 - 22,000) / 22,000 = 0.2727
        assert kpi.ebitda_growth == pytest.approx(0.2727, rel=1e-2)

    def test_no_growth_without_prior(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        assert kpi.revenue_growth is None


class TestValuationMultiples:
    def test_pe_ratio(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        # P/E = 25.00 / 1.55 = 16.13
        assert kpi.pe_ratio == pytest.approx(16.13, rel=1e-2)

    def test_ev_ebitda(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        # EV = 250,000 + 35,000 - 25,000 = 260,000
        # EV/EBITDA = 260,000 / 28,000 = 9.29
        assert kpi.ev_to_ebitda == pytest.approx(9.29, rel=1e-2)

    def test_price_to_sales(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        # P/S = 250,000 / 100,000 = 2.5
        assert kpi.price_to_sales == pytest.approx(2.5, rel=1e-2)


class TestEdgeCases:
    def test_zero_revenue(self):
        fp = FinancialPeriod(
            company_slug="zeroco",
            fiscal_year=2025,
            period_type="FY",
            income_statement=IncomeStatement(revenue=0, net_income=-1000),
        )
        kpi = KPIMetrics.calculate(fp)
        assert kpi.gross_margin is None
        assert kpi.net_margin is None

    def test_all_nulls(self):
        fp = FinancialPeriod(
            company_slug="nullco",
            fiscal_year=2025,
            period_type="FY",
        )
        kpi = KPIMetrics.calculate(fp)
        assert kpi.gross_margin is None
        assert kpi.roe is None
        assert kpi.current_ratio is None
```

### File: `tests/unit/test_json_fix.py`

```python
"""Unit tests for JSON fix utilities.

Tests the LLM output cleaning functions ported from v1.
"""

import pytest

from src.utils.json_fix import fix_json_numbers, extract_json_from_response, clean_numeric_value


class TestFixJsonNumbers:
    def test_accounting_notation(self):
        result = fix_json_numbers('{"loss": (1,234)}')
        assert "-1234" in result

    def test_comma_separated_numbers(self):
        result = fix_json_numbers('{"revenue": 43,536}')
        assert "43536" in result

    def test_large_comma_number(self):
        result = fix_json_numbers('{"assets": 1,234,567,890}')
        assert "1234567890" in result

    def test_negative_comma_number(self):
        result = fix_json_numbers('{"loss": -43,536}')
        assert "-43536" in result

    def test_no_change_for_valid_json(self):
        result = fix_json_numbers('{"revenue": 43536}')
        assert result == '{"revenue": 43536}'

    def test_javascript_comment_removal(self):
        result = fix_json_numbers('{"revenue": 100 // in thousands}')
        assert "//" not in result

    def test_trailing_comma(self):
        result = fix_json_numbers('{"a": 1, "b": 2,}')
        assert result == '{"a": 1, "b": 2}'


class TestExtractJsonFromResponse:
    def test_clean_json(self):
        result = extract_json_from_response('{"revenue": 100}')
        assert result == {"revenue": 100}

    def test_markdown_json_fence(self):
        response = '```json\n{"revenue": 100}\n```'
        result = extract_json_from_response(response)
        assert result == {"revenue": 100}

    def test_markdown_fence(self):
        response = 'Here is the data:\n```\n{"revenue": 100}\n```\nDone.'
        result = extract_json_from_response(response)
        assert result == {"revenue": 100}

    def test_surrounding_text(self):
        response = 'I found the following:\n{"revenue": 43,536}\nLet me know if you need more.'
        result = extract_json_from_response(response)
        assert result == {"revenue": 43536}

    def test_accounting_notation_in_response(self):
        response = '{"loss": (5,000), "revenue": 10,000}'
        result = extract_json_from_response(response)
        assert result["loss"] == -5000
        assert result["revenue"] == 10000

    def test_invalid_json_returns_none(self):
        result = extract_json_from_response("This is not JSON at all")
        assert result is None


class TestCleanNumericValue:
    def test_int(self):
        assert clean_numeric_value(42) == 42.0

    def test_float(self):
        assert clean_numeric_value(3.14) == 3.14

    def test_string_with_commas(self):
        assert clean_numeric_value("1,234,567") == 1234567.0

    def test_string_with_spaces(self):
        assert clean_numeric_value("  100  ") == 100.0

    def test_percentage(self):
        assert clean_numeric_value("25.5%") == 25.5

    def test_accounting_notation(self):
        assert clean_numeric_value("(1,234)") == -1234.0

    def test_none(self):
        assert clean_numeric_value(None) is None

    def test_non_numeric_string(self):
        assert clean_numeric_value("N/A") is None
```

---

## Task 9: Entry Points

### File: `src/__init__.py`

```python
"""Finance v3 -- Financial data pipeline for TASE company analysis."""

__version__ = "0.1.0"
```

### File: `src/__main__.py`

```python
"""Allow running as: python -m src"""

from cli.main import app

if __name__ == "__main__":
    app()
```

---

## File Inventory (35 files)

| # | File | Type | Lines (est.) |
|---|------|------|-------------|
| 1 | `pyproject.toml` | Config | 50 |
| 2 | `.env.example` | Config | 10 |
| 3 | `.gitignore` (update) | Config | 20 |
| 4 | `config/companies.yaml` (update) | Config | 215 |
| 5 | `config/providers.yaml` (update) | Config | 35 |
| 6 | `config/settings.yaml` | Config | 30 |
| 7 | `src/__init__.py` | Module | 3 |
| 8 | `src/__main__.py` | Module | 5 |
| 9 | `src/models/__init__.py` | Module | 15 |
| 10 | `src/models/company.py` | Model | 30 |
| 11 | `src/models/document.py` | Model | 40 |
| 12 | `src/models/financial.py` | Model | 180 |
| 13 | `src/models/kpi.py` | Model | 160 |
| 14 | `src/models/memo.py` | Model | 65 |
| 15 | `src/models/research.py` | Model | 70 |
| 16 | `src/models/job.py` | Model | 55 |
| 17 | `src/config/__init__.py` | Module | 3 |
| 18 | `src/config/loader.py` | Loader | 45 |
| 19 | `src/config/settings.py` | Settings | 60 |
| 20 | `src/storage/__init__.py` | Module | 3 |
| 21 | `src/storage/paths.py` | Storage | 55 |
| 22 | `src/storage/file_manager.py` | Storage | 145 |
| 23 | `src/utils/__init__.py` | Module | 5 |
| 24 | `src/utils/pdf.py` | Utility | 100 |
| 25 | `src/utils/json_fix.py` | Utility | 110 |
| 26 | `src/utils/currency.py` | Utility | 25 |
| 27 | `src/utils/logging.py` | Utility | 45 |
| 28 | `cli/__init__.py` | Module | 1 |
| 29 | `cli/main.py` | CLI | 40 |
| 30 | `cli/commands/__init__.py` | Module | 1 |
| 31 | `cli/commands/list_cmd.py` | CLI | 40 |
| 32 | `cli/commands/status.py` | CLI | 50 |
| 33 | `tests/__init__.py` | Test | 1 |
| 34 | `tests/conftest.py` | Test | 120 |
| 35 | `tests/unit/__init__.py` | Test | 1 |
| 36 | `tests/unit/test_models.py` | Test | 140 |
| 37 | `tests/unit/test_kpi_calculations.py` | Test | 130 |
| 38 | `tests/unit/test_json_fix.py` | Test | 90 |

**Total: 38 files, ~2,200 estimated lines.**

---

## Key Architectural Decisions

1. **Pydantic v2 over dataclasses.** All models use `BaseModel` with `model_validate`/`model_dump` for automatic validation, serialization, and schema generation. The v2 codebase used plain dataclasses with manual `to_dict()` methods -- Pydantic eliminates this boilerplate.

2. **Nested financial models over flat metrics.** Instead of the v2 flat `FinancialMetric` rows, financial data is structured as `FinancialPeriod` containing `IncomeStatement`, `BalanceSheet`, `CashFlow`, `PerShareData` sub-models. This enables type-safe access (`period.income_statement.revenue`) and maps directly to Excel sheet structure in Phase 5.

3. **JSON storage over CSV.** `financials.json` replaces `financials.csv` because Pydantic models serialize naturally to JSON, nested structures are preserved, and the data volumes per company are small (< 50 periods).

4. **CompanyPaths class over module-level functions.** The v2 `paths.py` used module-level functions with `os.path`. The new `CompanyPaths` class uses `pathlib.Path`, is instantiable with custom data roots (for testing), and groups all path logic for one company.

5. **company_type enum replaces implicit inference.** The v2 inferred US vs. TASE from `dual_listed` + `us_ticker`. The new `CompanyType` enum is explicit in YAML config, enabling future support for `private` companies with no exchange listing.

6. **Typer replaces argparse.** The v2 CLI used raw argparse. Typer provides type hints, auto-generated help, Rich integration, and the `finance` entry point via `pyproject.toml`.

7. **KPIMetrics.calculate() as classmethod.** The v1 `calculate_kpis()` was a standalone function taking a `FinancialData` argument. The new design is a classmethod on `KPIMetrics` itself, taking `FinancialPeriod` (current) and optional prior period for growth rates. Expanded from 6 ratios to 26.

8. **pydantic-settings for environment variables.** The `Settings` class uses `pydantic-settings` to load API keys from `.env` with type validation, replacing the ad-hoc `os.getenv()` calls scattered throughout v1 and v2.

9. **Poetry packaging.** The `pyproject.toml` defines `finance` as the CLI entry point, enabling `poetry install` followed by `finance list` from anywhere.

10. **Test fixtures in conftest.py.** Shared fixtures (`sample_company`, `sample_financial_period`, `prior_financial_period`) ensure consistent test data across all unit test modules. The `tmp_data_dir` fixture enables isolated file manager tests.

---

## Dependencies on Legacy Code

| Legacy Source | What to Port | Target |
|---------------|-------------|--------|
| `code/src/intelligence/extractor.py` lines 14-23 | `FINANCIAL_TABLE_KEYWORDS` | `src/utils/pdf.py` |
| `code/src/intelligence/extractor.py` lines 28-96 | `_extract_financial_pages()` | `src/utils/pdf.py::extract_financial_pages()` |
| `code/src/intelligence/extractor.py` lines 194-204 | `_fix_json_numbers()` | `src/utils/json_fix.py::fix_json_numbers()` |
| `code/src/intelligence/extractor.py` lines 206-237 | `_parse_response()` | `src/utils/json_fix.py::extract_json_from_response()` |
| `code/src/models/financial_parser.py` lines 41-70 | `KPIMetrics` dataclass (6 ratios) | `src/models/kpi.py` (expanded to 26 ratios) |
| `code/src/models/financial_parser.py` lines 200-231 | `calculate_kpis()` function | `src/models/kpi.py::KPIMetrics.calculate()` |
| `src/models/financial.py` lines 1-78 | Metric name lists | `src/models/financial.py` field names |
| `src/models/memo.py` lines 1-114 | InvestmentMemo, Scenario, RiskEntry | `src/models/memo.py` (expanded) |
| `src/models/report.py` lines 1-25 | ReportMetadata | `src/models/document.py` |
| `src/registry/company.py` lines 1-74 | Company, CompanyRegistry | `src/models/company.py`, `src/config/loader.py` |
| `src/storage/paths.py` lines 1-39 | Path functions | `src/storage/paths.py::CompanyPaths` |
| `src/storage/file_manager.py` lines 1-144 | FileManager class | `src/storage/file_manager.py` (rewritten) |
| `config/companies.yaml` | 18 company definitions | `config/companies.yaml` (+ company_type) |
| `config/providers.yaml` | Provider definitions | `config/providers.yaml` (+ routing table) |
