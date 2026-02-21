"""Unit tests for KPI calculations."""

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
        assert kpi.roe == pytest.approx(0.1882, rel=1e-2)

    def test_roa(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        assert kpi.roa == pytest.approx(0.1067, rel=1e-2)


class TestLeverageRatios:
    def test_debt_to_equity(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        assert kpi.debt_to_equity == pytest.approx(0.4118, rel=1e-2)

    def test_net_debt_to_ebitda(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        assert kpi.net_debt_to_ebitda == pytest.approx(0.357, rel=1e-2)

    def test_interest_coverage(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        assert kpi.interest_coverage == pytest.approx(11.0, rel=1e-2)


class TestLiquidityRatios:
    def test_current_ratio(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        assert kpi.current_ratio == pytest.approx(2.4, rel=1e-2)

    def test_quick_ratio(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        assert kpi.quick_ratio == pytest.approx(1.8, rel=1e-2)


class TestGrowthRates:
    def test_revenue_growth(self, sample_financial_period, prior_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period, prior_financial_period)
        assert kpi.revenue_growth == pytest.approx(0.1765, rel=1e-2)

    def test_ebitda_growth(self, sample_financial_period, prior_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period, prior_financial_period)
        assert kpi.ebitda_growth == pytest.approx(0.2727, rel=1e-2)

    def test_no_growth_without_prior(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        assert kpi.revenue_growth is None


class TestValuationMultiples:
    def test_pe_ratio(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        assert kpi.pe_ratio == pytest.approx(16.13, rel=1e-2)

    def test_ev_ebitda(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
        assert kpi.ev_to_ebitda == pytest.approx(9.29, rel=1e-2)

    def test_price_to_sales(self, sample_financial_period):
        kpi = KPIMetrics.calculate(sample_financial_period)
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
