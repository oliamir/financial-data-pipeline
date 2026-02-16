from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class FinancialMetric:
    """Single row in the long-format financial model CSV."""
    company_slug: str
    metric_name: str                    # e.g., "revenue", "net_income", "gross_margin_pct"
    category: str                       # "income_statement", "balance_sheet", "cash_flow",
                                        # "per_share", "margins", "growth_rates"
    period_type: str                    # "FY", "Q1", "Q2", "Q3", "Q4", "H1", "H2", "TTM"
    period_end_date: str                # ISO 8601: "2024-12-31"
    fiscal_year: int
    value: Optional[float]
    unit: str                           # "thousands", "units", "percentage"
    value_ils: Optional[float] = None
    value_usd: Optional[float] = None
    source_file: str = ""
    source_provider: str = ""           # "ollama", "gemini", "gemini_corrected"
    extracted_at: str = ""              # ISO 8601 timestamp
    confidence: Optional[float] = None  # 0.0-1.0

    def to_dict(self) -> dict:
        return {
            "company_slug": self.company_slug,
            "metric_name": self.metric_name,
            "category": self.category,
            "period_type": self.period_type,
            "period_end_date": self.period_end_date,
            "fiscal_year": self.fiscal_year,
            "value": self.value,
            "unit": self.unit,
            "value_ils": self.value_ils,
            "value_usd": self.value_usd,
            "source_file": self.source_file,
            "source_provider": self.source_provider,
            "extracted_at": self.extracted_at,
            "confidence": self.confidence,
        }


# Standard metrics to extract from financial reports
INCOME_STATEMENT_METRICS = [
    "revenue", "cost_of_revenue", "gross_profit",
    "rd_expense", "sga_expense", "operating_expense",
    "operating_income", "interest_expense", "pretax_income",
    "income_tax", "net_income", "ebitda", "adjusted_ebitda",
]

BALANCE_SHEET_METRICS = [
    "cash_and_equivalents", "short_term_investments",
    "accounts_receivable", "inventory",
    "total_current_assets", "ppe_net",
    "goodwill", "intangible_assets", "total_assets",
    "accounts_payable", "short_term_debt",
    "total_current_liabilities", "long_term_debt",
    "total_liabilities", "total_equity", "minority_interest",
]

CASH_FLOW_METRICS = [
    "cfo", "depreciation_amortization", "capex",
    "fcf", "dividends_paid", "share_repurchases",
    "acquisitions", "debt_issuance_net", "equity_issuance_net",
]

PER_SHARE_METRICS = [
    "shares_outstanding_basic", "shares_outstanding_diluted",
    "eps_basic", "eps_diluted", "dps", "bvps", "fcf_per_share",
]

ALL_METRICS = (
    INCOME_STATEMENT_METRICS
    + BALANCE_SHEET_METRICS
    + CASH_FLOW_METRICS
    + PER_SHARE_METRICS
)
