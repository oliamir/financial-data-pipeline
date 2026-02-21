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
