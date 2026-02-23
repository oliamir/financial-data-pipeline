"""MemoRenderer — renders InvestmentMemo to markdown using the framework structure.

Section order and titles are driven by ``config/memo_framework.md``.  Editing
that file changes the output structure without touching Python code.

Structured tables (scenarios, risks, catalysts, revisions) have dedicated
rendering helpers because they come from typed sub-models, not free-text fields.
"""

from datetime import datetime
from typing import Optional

from ..models.memo import InvestmentMemo
from .framework_parser import parse_framework
from ..utils.logging import get_logger

logger = get_logger(__name__)

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

# Fields that have special structured rendering (not simple text)
_STRUCTURED_FIELDS = {"scenario_analysis", "risks_mitigants", "catalysts_timeline", "action_items"}


class MemoRenderer:
    """Renders an InvestmentMemo to professional markdown.

    Section order and titles come from the framework file.  Sections with
    no content are silently omitted.
    """

    @staticmethod
    def render(memo: InvestmentMemo) -> str:
        """Render a complete investment memo to markdown.

        Args:
            memo: The structured InvestmentMemo object.

        Returns:
            Formatted markdown string.
        """
        parts = [MemoRenderer._render_header(memo)]

        # Load section definitions from the framework file
        try:
            framework_sections = parse_framework()
        except FileNotFoundError:
            logger.warning("Framework file not found; falling back to minimal render")
            framework_sections = []

        for section in framework_sections:
            rendered = MemoRenderer._render_section(memo, section.field_name, section.number, section.title)
            if rendered:
                parts.append(rendered)

        # Strategic research appendix (from initial_research sub-model)
        research = MemoRenderer._render_initial_research(memo)
        if research:
            parts.append(research)

        # Revision history (always last)
        if memo.revisions:
            parts.append(MemoRenderer._render_revisions(memo))

        return "\n\n---\n\n".join(parts) + "\n"

    # ------------------------------------------------------------------
    # Section dispatch
    # ------------------------------------------------------------------

    @staticmethod
    def _render_section(memo: InvestmentMemo, field_name: str, number: int, title: str) -> Optional[str]:
        """Render a single section by field name.

        Delegates to structured renderers for scenarios/risks/catalysts,
        and uses direct text content for everything else.
        """
        heading = f"## {number}. {title}"

        # --- Structured tables ---
        if field_name == "scenario_analysis":
            if memo.scenarios:
                return MemoRenderer._render_scenarios(memo, heading)
            text = memo.scenario_analysis
            if text and text.strip():
                return f"{heading}\n\n{text.strip()}"
            return None

        if field_name == "risks_mitigants":
            if memo.risks:
                return MemoRenderer._render_risks(memo, heading)
            text = memo.risks_mitigants
            if text and text.strip():
                return f"{heading}\n\n{text.strip()}"
            return None

        if field_name == "catalysts_timeline":
            if memo.catalysts:
                return MemoRenderer._render_catalysts(memo, heading)
            text = memo.catalysts_timeline
            if text and text.strip():
                return f"{heading}\n\n{text.strip()}"
            return None

        if field_name == "action_items":
            if memo.action_items:
                items = "\n".join(f"- {item}" for item in memo.action_items)
                return f"{heading}\n\n{items}"
            return None

        # --- Financial analysis: try sub-sections as fallback ---
        if field_name == "financial_analysis":
            content = memo.financial_analysis or MemoRenderer._build_financial_section(memo)
            if content and content.strip():
                return f"{heading}\n\n{content.strip()}"
            return None

        # --- Standard text fields ---
        content = getattr(memo, field_name, None)
        if content and isinstance(content, str) and content.strip():
            return f"{heading}\n\n{content.strip()}"

        return None

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

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
            "| Field | Value |",
            "|-------|-------|",
            f"| **Recommendation** | {rec} |",
            f"| **Conviction** | {conv} |",
            f"| **Thesis Status** | {thesis} |",
            f"| **Version** | v{memo.version} |",
            f"| **Last Updated** | {updated} |",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Financial sub-section fallback
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Structured tables
    # ------------------------------------------------------------------

    @staticmethod
    def _render_scenarios(memo: InvestmentMemo, heading: str) -> str:
        """Render scenarios as a table."""
        lines = [
            heading,
            "",
            "| Scenario | Probability | Target Price | Description |",
            "|----------|------------|-------------|-------------|",
        ]
        for s in memo.scenarios:
            price = f"{s.currency} {s.target_price:,.2f}" if s.target_price else "\u2014"
            desc = s.description[:120] + "\u2026" if len(s.description) > 120 else s.description
            lines.append(f"| **{s.name.title()}** | {s.probability_pct:.0f}% | {price} | {desc} |")

        for s in memo.scenarios:
            if s.key_assumptions:
                assumptions = ", ".join(s.key_assumptions)
                lines.append(f"\n**{s.name.title()} assumptions**: {assumptions}")

        return "\n".join(lines)

    @staticmethod
    def _render_risks(memo: InvestmentMemo, heading: str) -> str:
        """Render risks as a table."""
        severity_icon = {"high": "\U0001f534", "medium": "\U0001f7e1", "low": "\U0001f7e2"}
        lines = [
            heading,
            "",
            "| # | Category | Severity | Description | Mitigation |",
            "|---|----------|----------|-------------|------------|",
        ]
        for i, r in enumerate(memo.risks, 1):
            icon = severity_icon.get(r.severity, "\u26aa")
            mitigation = r.mitigation or "\u2014"
            lines.append(
                f"| {i} | {r.category.title()} | {icon} {r.severity.title()} "
                f"| {r.description} | {mitigation} |"
            )
        return "\n".join(lines)

    @staticmethod
    def _render_catalysts(memo: InvestmentMemo, heading: str) -> str:
        """Render catalysts as a table."""
        impact_icon = {"positive": "\U0001f4c8", "negative": "\U0001f4c9", "neutral": "\u27a1\ufe0f"}
        lines = [
            heading,
            "",
            "| # | Catalyst | Timeframe | Impact | Probability |",
            "|---|----------|-----------|--------|-------------|",
        ]
        for i, c in enumerate(memo.catalysts, 1):
            icon = impact_icon.get(c.impact, "\u27a1\ufe0f")
            tf = c.timeframe or c.timeline or "\u2014"
            prob = c.probability or "\u2014"
            lines.append(f"| {i} | {c.description} | {tf} | {icon} {c.impact.title()} | {prob} |")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Initial research (strategic research appendix)
    # ------------------------------------------------------------------

    @staticmethod
    def _render_initial_research(memo: InvestmentMemo) -> Optional[str]:
        """Render initial strategic research sections as an appendix."""
        ir = memo.initial_research
        if not ir:
            return None

        # Check if ANY research field has content
        research_fields = [
            ir.competitors, ir.tam_sam_som, ir.competitive_analysis,
            ir.market_intelligence, ir.swot_analysis, ir.seven_powers,
            ir.ownership_structure, ir.israel_risk,
        ]
        if not any(f and f.strip() for f in research_fields):
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
            ("Seven Powers Analysis", ir.seven_powers),
            ("Ownership Structure", ir.ownership_structure),
            ("Israel-Specific Risks", ir.israel_risk),
        ]

        for title, content in sub_sections:
            if content and content.strip():
                lines.append(f"\n### {title}\n\n{content.strip()}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Revision history
    # ------------------------------------------------------------------

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
            impact_icon = {"positive": "\U0001f4c8", "negative": "\U0001f4c9", "neutral": "\u27a1\ufe0f"}.get(
                rev.thesis_impact, "\u27a1\ufe0f"
            )
            summary = rev.changes_summary[:80] + "\u2026" if len(rev.changes_summary) > 80 else rev.changes_summary
            lines.append(
                f"| v{rev.version} | {rev.date} | {rev.source_file or '\u2014'} "
                f"| {impact_icon} {rev.thesis_impact.title()} | {summary} |"
            )
        return "\n".join(lines)
