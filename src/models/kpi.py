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
    roe: Optional[float] = None
    roa: Optional[float] = None
    roic: Optional[float] = None

    # Leverage
    debt_to_equity: Optional[float] = None
    net_debt_to_ebitda: Optional[float] = None
    interest_coverage: Optional[float] = None

    # Liquidity
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None

    # Working Capital Efficiency
    dso: Optional[float] = None
    dio: Optional[float] = None
    dpo: Optional[float] = None
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
            annualized_revenue = inc.revenue
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
