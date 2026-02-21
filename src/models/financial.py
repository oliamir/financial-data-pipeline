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

    eps_basic: Optional[float] = None
    eps_diluted: Optional[float] = None

    weighted_avg_shares_basic: Optional[float] = None
    weighted_avg_shares_diluted: Optional[float] = None

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
