"""MemoRenderer — converts structured InvestmentMemo into professional markdown.

Renders all sections, structured tables (scenarios, risks, catalysts),
initial research, and revision history into a single cohesive document.
"""

from datetime import datetime
from typing import Optional

from ..models.memo import InvestmentMemo


# Badge mappings for visual indicators
_RECOMMENDATION_BADGE = {
    "buy": "🟢 BUY",
    "speculative_buy": "🟡 SPECULATIVE BUY",
    "hold": "🟡 HOLD",
    "sell": "🔴 SELL",
    "monitor": "⚪ MONITOR",
}

_CONVICTION_BADGE = {
    "high": "🔥 High",
    "medium": "⚡ Medium",
    "low": "💤 Low",
}

_THESIS_BADGE = {
    "new": "🆕 New",
    "intact": "✅ Intact",
    "strengthening": "📈 Strengthening",
    "weakening": "📉 Weakening",
    "broken": "🚫 Broken",
    "confirmed": "✅ Confirmed",
    "revised": "🔄 Revised",
}


class MemoRenderer:
    """Renders an InvestmentMemo to professional markdown."""

    @staticmethod
    def render(memo: InvestmentMemo) -> str:
        """Render a complete investment memo to markdown.

        Args:
            memo: The structured InvestmentMemo object.

        Returns:
            Formatted markdown string.
        """
        sections = []
        sections.append(MemoRenderer._render_header(memo))

        # Core narrative sections
        _section_map = [
            ("Executive Summary", memo.executive_summary),
            ("Company Overview", memo.company_overview),
            ("Industry Analysis", memo.industry_analysis),
            ("Competitive Positioning", memo.competitive_positioning),
            ("Management & Governance", memo.management_governance),
            ("Financial Analysis", memo.financial_analysis or MemoRenderer._build_financial_section(memo)),
            ("Valuation", memo.valuation),
            ("ESG & Governance", memo.esg_notes),
        ]

        for title, content in _section_map:
            if content and content.strip():
                sections.append(f"## {title}\n\n{content.strip()}")

        # Structured tables
        if memo.scenarios:
            sections.append(MemoRenderer._render_scenarios(memo))
        elif memo.scenario_analysis:
            sections.append(f"## Scenario Analysis\n\n{memo.scenario_analysis.strip()}")

        if memo.risks:
            sections.append(MemoRenderer._render_risks(memo))
        elif memo.risks_mitigants:
            sections.append(f"## Risks & Mitigants\n\n{memo.risks_mitigants.strip()}")

        if memo.catalysts:
            sections.append(MemoRenderer._render_catalysts(memo))
        elif memo.catalysts_timeline:
            sections.append(f"## Catalysts & Timeline\n\n{memo.catalysts_timeline.strip()}")

        # Initial research (Strategic Research section)
        research_section = MemoRenderer._render_initial_research(memo)
        if research_section:
            sections.append(research_section)

        # Open questions & action items
        if memo.open_questions and memo.open_questions.strip():
            sections.append(f"## Open Questions\n\n{memo.open_questions.strip()}")

        if memo.action_items:
            items = "\n".join(f"- {item}" for item in memo.action_items)
            sections.append(f"## Action Items\n\n{items}")

        # Appendix
        if memo.appendix and memo.appendix.strip():
            sections.append(f"## Appendix\n\n{memo.appendix.strip()}")

        # Revision history
        if memo.revisions:
            sections.append(MemoRenderer._render_revisions(memo))

        return "\n\n---\n\n".join(sections) + "\n"

    @staticmethod
    def _render_header(memo: InvestmentMemo) -> str:
        """Render the header block with badges and metadata."""
        rec = _RECOMMENDATION_BADGE.get(memo.recommendation, memo.recommendation.upper())
        conv = _CONVICTION_BADGE.get(memo.conviction, memo.conviction)
        thesis = _THESIS_BADGE.get(memo.thesis_status, memo.thesis_status)

        updated = ""
        if memo.last_updated:
            if isinstance(memo.last_updated, datetime):
                updated = memo.last_updated.strftime("%Y-%m-%d %H:%M")
            else:
                updated = str(memo.last_updated)

        lines = [
            f"# Investment Memo — {memo.company_slug.replace('_', ' ').title()}",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| **Recommendation** | {rec} |",
            f"| **Conviction** | {conv} |",
            f"| **Thesis Status** | {thesis} |",
            f"| **Version** | v{memo.version} |",
            f"| **Last Updated** | {updated} |",
        ]
        return "\n".join(lines)

    @staticmethod
    def _build_financial_section(memo: InvestmentMemo) -> str:
        """Combine alternative financial sub-sections into one."""
        parts = []
        if memo.revenue_analysis:
            parts.append(f"### Revenue Analysis\n\n{memo.revenue_analysis.strip()}")
        if memo.profitability_analysis:
            parts.append(f"### Profitability Analysis\n\n{memo.profitability_analysis.strip()}")
        if memo.balance_sheet_review:
            parts.append(f"### Balance Sheet Review\n\n{memo.balance_sheet_review.strip()}")
        if memo.cash_flow_analysis:
            parts.append(f"### Cash Flow Analysis\n\n{memo.cash_flow_analysis.strip()}")
        return "\n\n".join(parts)

    @staticmethod
    def _render_scenarios(memo: InvestmentMemo) -> str:
        """Render scenarios as a table."""
        lines = [
            "## Scenario Analysis",
            "",
            "| Scenario | Probability | Target Price | Description |",
            "|----------|------------|-------------|-------------|",
        ]
        for s in memo.scenarios:
            price = f"{s.currency} {s.target_price:,.2f}" if s.target_price else "—"
            desc = s.description[:120] + "…" if len(s.description) > 120 else s.description
            lines.append(f"| **{s.name.title()}** | {s.probability_pct:.0f}% | {price} | {desc} |")

        # Key assumptions below table
        for s in memo.scenarios:
            if s.key_assumptions:
                assumptions = ", ".join(s.key_assumptions)
                lines.append(f"\n**{s.name.title()} assumptions**: {assumptions}")

        return "\n".join(lines)

    @staticmethod
    def _render_risks(memo: InvestmentMemo) -> str:
        """Render risks as a table."""
        severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        lines = [
            "## Risks & Mitigants",
            "",
            "| # | Category | Severity | Description | Mitigation |",
            "|---|----------|----------|-------------|------------|",
        ]
        for i, r in enumerate(memo.risks, 1):
            icon = severity_icon.get(r.severity, "⚪")
            mitigation = r.mitigation or "—"
            lines.append(f"| {i} | {r.category.title()} | {icon} {r.severity.title()} | {r.description} | {mitigation} |")

        return "\n".join(lines)

    @staticmethod
    def _render_catalysts(memo: InvestmentMemo) -> str:
        """Render catalysts as a table."""
        impact_icon = {"positive": "📈", "negative": "📉", "neutral": "➡️"}
        lines = [
            "## Catalysts & Timeline",
            "",
            "| # | Catalyst | Timeframe | Impact | Probability |",
            "|---|----------|-----------|--------|-------------|",
        ]
        for i, c in enumerate(memo.catalysts, 1):
            icon = impact_icon.get(c.impact, "➡️")
            tf = c.timeframe or c.timeline or "—"
            prob = c.probability or "—"
            lines.append(f"| {i} | {c.description} | {tf} | {icon} {c.impact.title()} | {prob} |")

        return "\n".join(lines)

    @staticmethod
    def _render_initial_research(memo: InvestmentMemo) -> Optional[str]:
        """Render initial strategic research sections."""
        ir = memo.initial_research
        if not ir or not any([ir.competitors, ir.tam_sam_som, ir.competitive_analysis,
                             ir.market_intelligence, ir.swot_analysis]):
            return None

        lines = ["## Strategic Research"]
        if ir.model_used or ir.generated_at:
            meta_parts = []
            if ir.model_used:
                meta_parts.append(f"Model: `{ir.model_used}`")
            if ir.generated_at:
                meta_parts.append(f"Generated: {ir.generated_at}")
            lines.append(f"\n> {' | '.join(meta_parts)}")

        sub_sections = [
            ("Competitor Landscape", ir.competitors),
            ("Market Sizing (TAM / SAM / SOM)", ir.tam_sam_som),
            ("Competitive Analysis", ir.competitive_analysis),
            ("Market Intelligence", ir.market_intelligence),
            ("SWOT & Strategic Positioning", ir.swot_analysis),
        ]

        for title, content in sub_sections:
            if content and content.strip():
                lines.append(f"\n### {title}\n\n{content.strip()}")

        return "\n".join(lines)

    @staticmethod
    def _render_revisions(memo: InvestmentMemo) -> str:
        """Render revision history as a table."""
        lines = [
            "## Revision History",
            "",
            "| Version | Date | Source | Thesis Impact | Summary |",
            "|---------|------|--------|--------------|---------|",
        ]
        for rev in sorted(memo.revisions, key=lambda r: r.version, reverse=True):
            impact_icon = {"positive": "📈", "negative": "📉", "neutral": "➡️"}.get(
                rev.thesis_impact, "➡️"
            )
            summary = rev.changes_summary[:80] + "…" if len(rev.changes_summary) > 80 else rev.changes_summary
            lines.append(
                f"| v{rev.version} | {rev.date} | {rev.source_file or '—'} "
                f"| {impact_icon} {rev.thesis_impact.title()} | {summary} |"
            )

        return "\n".join(lines)
