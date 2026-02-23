"""Unit tests for MemoRenderer, MemoRevision, InitialResearch, and versioning."""

import pytest
from datetime import datetime

from src.models.memo import (
    InvestmentMemo, Scenario, Risk, Catalyst,
    MemoRevision, InitialResearch,
)
from src.memo.renderer import MemoRenderer


# ---------------------------------------------------------------------------
# MemoRevision model tests
# ---------------------------------------------------------------------------

class TestMemoRevision:
    def test_basic_creation(self):
        rev = MemoRevision(version=2, date="2026-02-21", source_file="Q3_report.pdf")
        assert rev.version == 2
        assert rev.thesis_impact == "neutral"

    def test_serialization_roundtrip(self):
        rev = MemoRevision(
            version=3,
            date="2026-02-21",
            source_file="annual.pdf",
            changes_summary="Revenue revised up 12%",
            fields_updated=["revenue_analysis", "valuation"],
            thesis_impact="positive",
        )
        data = rev.model_dump(mode="json")
        restored = MemoRevision.model_validate(data)
        assert restored == rev
        assert restored.fields_updated == ["revenue_analysis", "valuation"]


# ---------------------------------------------------------------------------
# InitialResearch model tests
# ---------------------------------------------------------------------------

class TestInitialResearch:
    def test_defaults(self):
        ir = InitialResearch()
        assert ir.competitors == ""
        assert ir.tam_sam_som == ""
        assert ir.generated_at is None
        assert ir.model_used == ""

    def test_populated(self):
        ir = InitialResearch(
            competitors="1. Company A\n2. Company B",
            tam_sam_som="TAM: $10B",
            competitive_analysis="2x2 matrix analysis...",
            market_intelligence="Trends report...",
            swot_analysis="SWOT results...",
            generated_at="2026-02-21T12:00:00",
            model_used="gemini-3.1-pro-preview",
        )
        assert ir.model_used == "gemini-3.1-pro-preview"
        assert "Company A" in ir.competitors


# ---------------------------------------------------------------------------
# InvestmentMemo versioning tests
# ---------------------------------------------------------------------------

class TestMemoVersioning:
    def test_default_version(self):
        memo = InvestmentMemo(company_slug="testco")
        assert memo.version == 1
        assert memo.revisions == []
        assert memo.initial_research.competitors == ""

    def test_with_revisions(self):
        memo = InvestmentMemo(
            company_slug="testco",
            version=3,
            revisions=[
                MemoRevision(version=2, date="2026-01-15", changes_summary="Q3 update"),
                MemoRevision(version=3, date="2026-02-21", changes_summary="Q4 update"),
            ],
        )
        assert len(memo.revisions) == 2
        assert memo.revisions[-1].version == 3

    def test_backward_compatibility_no_new_fields(self):
        """Old memo JSON without version/revisions/initial_research should still load."""
        old_data = {
            "company_slug": "testco",
            "recommendation": "buy",
            "executive_summary": "Great company.",
        }
        memo = InvestmentMemo.model_validate(old_data)
        assert memo.version == 1
        assert memo.revisions == []
        assert memo.initial_research.competitors == ""

    def test_with_initial_research(self):
        memo = InvestmentMemo(
            company_slug="testco",
            initial_research=InitialResearch(
                competitors="Top 7: A, B, C, D, E, F, G",
                tam_sam_som="TAM: $50B",
                model_used="gemini-3.1-pro-preview",
                generated_at="2026-02-21T10:00:00",
            ),
        )
        assert "Top 7" in memo.initial_research.competitors
        assert memo.initial_research.model_used == "gemini-3.1-pro-preview"

    def test_full_serialization_roundtrip(self):
        memo = InvestmentMemo(
            company_slug="testco",
            recommendation="buy",
            version=2,
            revisions=[MemoRevision(version=2, date="2026-02-21")],
            initial_research=InitialResearch(competitors="A, B, C"),
            scenarios=[Scenario(name="bull", probability_pct=30)],
        )
        data = memo.model_dump(mode="json")
        restored = InvestmentMemo.model_validate(data)
        assert restored.version == 2
        assert len(restored.revisions) == 1
        assert restored.initial_research.competitors == "A, B, C"


# ---------------------------------------------------------------------------
# MemoRenderer tests
# ---------------------------------------------------------------------------

class TestMemoRenderer:
    def test_minimal_memo(self):
        """Render a memo with minimal data — should produce header only."""
        memo = InvestmentMemo(company_slug="testco")
        md = MemoRenderer.render(memo)
        assert "# Investment Memo" in md
        assert "⚪ MONITOR" in md
        assert "v1" in md

    def test_header_badges(self):
        memo = InvestmentMemo(
            company_slug="apollo_power",
            recommendation="buy",
            conviction="high",
            thesis_status="strengthening",
            version=3,
        )
        md = MemoRenderer.render(memo)
        assert "🟢 BUY" in md
        assert "🔥 High" in md
        assert "📈 Strengthening" in md
        assert "v3" in md

    def test_scenarios_table(self):
        memo = InvestmentMemo(
            company_slug="testco",
            scenarios=[
                Scenario(name="bull", probability_pct=25, target_price=40.0, description="Best case"),
                Scenario(name="base", probability_pct=50, target_price=28.0, description="Most likely"),
                Scenario(name="bear", probability_pct=25, target_price=15.0, description="Worst case"),
            ],
        )
        md = MemoRenderer.render(memo)
        assert "Scenario Analysis" in md
        assert "| **Bull**" in md
        assert "| **Base**" in md
        assert "| **Bear**" in md
        assert "25%" in md
        assert "50%" in md

    def test_risks_table(self):
        memo = InvestmentMemo(
            company_slug="testco",
            risks=[
                Risk(category="market", severity="high", description="Macro downturn", mitigation="Diversify"),
                Risk(category="operational", severity="low", description="Supply chain"),
            ],
        )
        md = MemoRenderer.render(memo)
        assert "Risks & Mitigants" in md
        assert "🔴" in md  # high severity
        assert "🟢" in md  # low severity
        assert "Macro downturn" in md

    def test_catalysts_table(self):
        memo = InvestmentMemo(
            company_slug="testco",
            catalysts=[
                Catalyst(description="FDA approval", timeframe="Q2 2026", impact="positive"),
            ],
        )
        md = MemoRenderer.render(memo)
        assert "Catalysts & Timeline" in md
        assert "FDA approval" in md
        assert "Q2 2026" in md

    def test_initial_research_rendered(self):
        memo = InvestmentMemo(
            company_slug="testco",
            initial_research=InitialResearch(
                competitors="1. CompA\n2. CompB",
                tam_sam_som="TAM: $10B, SAM: $2B, SOM: $500M",
                competitive_analysis="White space analysis...",
                market_intelligence="Trends report...",
                swot_analysis="Strengths: technology lead",
                model_used="gemini-3.1-pro-preview",
                generated_at="2026-02-21",
            ),
        )
        md = MemoRenderer.render(memo)
        assert "## Strategic Research" in md
        assert "### Competitor Landscape" in md
        assert "### Market Sizing" in md
        assert "### Competitive Analysis" in md
        assert "### Market Intelligence" in md
        assert "### SWOT" in md
        assert "gemini-3.1-pro-preview" in md

    def test_no_initial_research_when_empty(self):
        memo = InvestmentMemo(company_slug="testco")
        md = MemoRenderer.render(memo)
        assert "Strategic Research" not in md

    def test_revision_history(self):
        memo = InvestmentMemo(
            company_slug="testco",
            version=3,
            revisions=[
                MemoRevision(version=2, date="2026-01-15", source_file="Q3.pdf",
                             thesis_impact="positive", changes_summary="Revenue up"),
                MemoRevision(version=3, date="2026-02-21", source_file="Q4.pdf",
                             thesis_impact="neutral", changes_summary="Margins stable"),
            ],
        )
        md = MemoRenderer.render(memo)
        assert "## Revision History" in md
        assert "v2" in md
        assert "v3" in md
        assert "Q3.pdf" in md
        assert "Revenue up" in md

    def test_action_items(self):
        memo = InvestmentMemo(
            company_slug="testco",
            action_items=["Research competitor pricing", "Follow up on Q4 guidance"],
        )
        md = MemoRenderer.render(memo)
        assert "Action Items" in md
        assert "- Research competitor pricing" in md

    def test_narrative_sections(self):
        memo = InvestmentMemo(
            company_slug="testco",
            executive_summary="This is a great company with strong growth.",
            company_overview="Founded in 2010, builds renewable energy systems.",
            valuation="Trading at 15x EV/EBITDA, 20% discount to peers.",
        )
        md = MemoRenderer.render(memo)
        assert "Executive Summary" in md
        assert "great company" in md
        assert "Company Overview" in md
        assert "Valuation" in md
