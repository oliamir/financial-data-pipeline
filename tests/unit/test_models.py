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
