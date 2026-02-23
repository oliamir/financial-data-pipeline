"""Pipeline step: Initial strategic research using framework-driven prompts.

Runs 8 sequential research prompts for a new company, reading prompt templates
from config/memo_framework.md via the framework parser. Each prompt maps to a
field on the InitialResearch model:

    1. Competitor Discovery   (Section 5: competitive_positioning) -> competitors
    2. Market Size            (Section 3: market_size)             -> tam_sam_som
    3. Competitive Analysis   (Section 5 + competitors injected)   -> competitive_analysis
    4. Industry Trends        (Section 4: industry_analysis)       -> market_intelligence
    5. SWOT Analysis          (Section 7: swot_analysis)           -> swot_analysis
    6. Seven Powers           (Section 6: seven_powers)            -> seven_powers
    7. Ownership Structure    (Section 9: ownership_structure)     -> ownership_structure
    8. Israel Risk            (Section 16: israel_risk_factors)    -> israel_risk

Uses the ProviderRegistry to select the best available provider rather than
hardcoding a specific model.
"""

from datetime import datetime
from typing import Dict, List, Optional

from ...ai.base import BaseProvider
from ...memo.framework_parser import FrameworkSection, parse_framework
from ...models.company import Company
from ...models.memo import InitialResearch
from ...utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Framework section field_name -> InitialResearch field_name
# ---------------------------------------------------------------------------

RESEARCH_FIELD_MAP: Dict[str, str] = {
    "competitive_positioning": "competitors",
    "market_size": "tam_sam_som",
    "industry_analysis": "market_intelligence",
    "swot_analysis": "swot_analysis",
    "seven_powers": "seven_powers",
    "ownership_structure": "ownership_structure",
    "israel_risk_factors": "israel_risk",
}

# Ordered execution plan.  Each entry is:
#   (step_label, framework_field_name, result_field_name, search_topic_fragment)
# "competitive_analysis" is a special case handled inline (re-uses the
# competitive_positioning prompt with competitors injected).
_PROMPT_PLAN: List[tuple] = [
    ("Competitor Discovery", "competitive_positioning", "competitors", "competitors"),
    ("Market Size", "market_size", "tam_sam_som", "market size TAM"),
    ("Competitive Analysis", "competitive_positioning", "competitive_analysis", "competitive landscape"),
    ("Industry Trends", "industry_analysis", "market_intelligence", "industry trends funding M&A"),
    ("SWOT Analysis", "swot_analysis", "swot_analysis", "SWOT analysis strengths weaknesses"),
    ("Seven Powers", "seven_powers", "seven_powers", "competitive advantages moat seven powers"),
    ("Ownership Structure", "ownership_structure", "ownership_structure", "ownership shareholders institutional"),
    ("Israel Risk", "israel_risk_factors", "israel_risk", "Israel risk geopolitical regulatory"),
]

TOTAL_PROMPTS = len(_PROMPT_PLAN)


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

def _get_research_provider() -> Optional[BaseProvider]:
    """Get the best available provider for initial research.

    Priority order: claude_code > gemini_deep > gemini > ollama.
    Returns None if no provider is available.
    """
    from ...ai.registry import ProviderRegistry

    registry = ProviderRegistry()

    for name in ["claude_code", "gemini_deep", "gemini", "ollama"]:
        if registry.has(name):
            provider = registry.get(name)
            logger.info(f"  [InitialResearch] Using provider: {name}")
            return provider

    logger.error("No AI provider available for initial research")
    return None


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------

def _format_prompt(
    template: str,
    company: Company,
    market: str,
    sector: str,
    competitors_list: str = "",
    prior_sections: str = "",
) -> str:
    """Fill framework prompt placeholders with company-specific values.

    Handles all standard placeholders defined in the framework:
    {company_name}, {sector}, {market}, {ticker}, {date},
    {competitors_list}, {prior_sections}.
    """
    return template.format(
        company_name=company.name,
        sector=sector,
        market=market,
        ticker=getattr(company, "tase_id", "") or company.slug,
        date=datetime.now().strftime("%Y-%m-%d"),
        competitors_list=competitors_list or "(Not yet available)",
        prior_sections=prior_sections or "(Not yet available)",
    )


# ---------------------------------------------------------------------------
# Helpers preserved from original implementation
# ---------------------------------------------------------------------------

def _determine_market(company: Company) -> str:
    """Determine market description from company data."""
    parts: List[str] = []
    if company.us_exchange:
        parts.append(f"{company.us_exchange}")
    if company.company_type.value == "tase_traded":
        parts.append("TASE (Tel Aviv)")
    if not parts:
        parts.append("Israel")
    return " / ".join(parts)


def _format_sector(sector: str) -> str:
    """Human-readable sector name."""
    return sector.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Prompt execution helpers
# ---------------------------------------------------------------------------

def _build_prompt_index(sections: List[FrameworkSection]) -> Dict[str, FrameworkSection]:
    """Build a lookup dict from framework field_name -> FrameworkSection."""
    return {s.field_name: s for s in sections}


def _call_provider(
    provider: BaseProvider,
    search_query: str,
    formatted_prompt: str,
) -> str:
    """Call the provider with search grounding, falling back to plain text.

    Tries generate_with_search first. If that raises (e.g. the provider does
    not support search), falls back to generate_text.
    """
    try:
        return provider.generate_with_search(search_query, formatted_prompt)
    except Exception:
        logger.debug("  [InitialResearch] generate_with_search unavailable, falling back to generate_text")
        return provider.generate_text(formatted_prompt)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_initial_research(company: Company) -> Optional[InitialResearch]:
    """Run all strategic research prompts for a company.

    Prompts are executed sequentially so that earlier results (e.g. competitor
    discovery) can feed into later prompts (e.g. competitive analysis, SWOT).

    Args:
        company: The Company object with name, sector, etc.

    Returns:
        Populated InitialResearch, or None if no provider is available.
    """
    provider = _get_research_provider()
    if provider is None:
        return None

    # Parse framework prompts
    try:
        sections = parse_framework()
    except FileNotFoundError as e:
        logger.error(f"  [InitialResearch] Framework file not found: {e}")
        return None

    prompt_index = _build_prompt_index(sections)

    market = _determine_market(company)
    sector = _format_sector(company.sector)

    result = InitialResearch(
        model_used=getattr(provider, "name", "unknown"),
        generated_at=datetime.now().isoformat(),
    )

    for step_num, (label, framework_field, result_field, topic_fragment) in enumerate(_PROMPT_PLAN, start=1):
        logger.info(
            f"  [InitialResearch] Prompt {step_num}/{TOTAL_PROMPTS}: {label} for {company.name}..."
        )

        # Look up the framework prompt template
        section = prompt_index.get(framework_field)
        if section is None or not section.prompt_template:
            logger.warning(
                f"  [InitialResearch] No prompt template found for framework field '{framework_field}', skipping"
            )
            continue

        try:
            # Build competitors_list from previous result for prompts that need it
            competitors_list = result.competitors or "(No competitor data available)"

            formatted_prompt = _format_prompt(
                template=section.prompt_template,
                company=company,
                market=market,
                sector=sector,
                competitors_list=competitors_list,
                prior_sections="",
            )

            search_query = f"{company.name} {topic_fragment} {sector}"
            response = _call_provider(provider, search_query, formatted_prompt)

            setattr(result, result_field, response)
            logger.info(f"  [InitialResearch] Prompt {step_num}/{TOTAL_PROMPTS}: {label} complete")

        except Exception as e:
            logger.error(f"  [InitialResearch] Prompt {step_num}/{TOTAL_PROMPTS}: {label} failed: {e}")
            setattr(result, result_field, f"[Error: {e}]")

    logger.info(f"  [InitialResearch] All {TOTAL_PROMPTS} prompts complete for {company.name}")
    return result
