"""Pipeline step: Initial strategic research using Gemini deep thinking.

Runs 5 sequential prompts for a new company:
  Prompt 0: Competitor discovery (top 7)
  Prompt 1: TAM / SAM / SOM market sizing
  Prompt 2: Competitive analysis with 2×2 matrix
  Prompt 3: Market intelligence quarterly brief
  Prompt 4: SWOT + action matrix

Uses Gemini 3.1 Pro Preview directly (bypasses normal task router).
"""

import os
from datetime import datetime
from typing import Optional

from ...models.memo import InitialResearch
from ...models.company import Company
from ...utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

DEEP_THINKING_MODEL = "gemini-3.1-pro-preview"

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

COMPETITOR_DISCOVERY_PROMPT = """You are a senior equity research analyst covering {sector} companies.

Company: {company_name}
Market: {market} (traded on TASE — Tel Aviv Stock Exchange)
Sector: {sector}

Identify the top 7 direct competitors for {company_name}. For each competitor provide:
1. Company name
2. Ticker / exchange (if publicly traded)
3. Headquarters country
4. Why they compete with {company_name} (1 sentence)
5. Estimated revenue (latest available)

Return a numbered list of exactly 7 competitors. Be specific — these should be real companies that directly compete in the same product/service space, not tangentially related firms.

After the list, provide a 2-sentence summary of the competitive landscape.
"""

TAM_SAM_SOM_PROMPT = """You are a senior market research analyst at McKinsey.

Calculate the TAM, SAM, and SOM for {company_name}'s products/services in {market}.

Company: {company_name}
Sector: {sector}
Products/Services: Research what {company_name} does and identify their core product/service lines.

For each (TAM, SAM, SOM):
- Show your math (top-down AND bottom-up approach)
- Cite the assumptions you're making
- Flag where your estimates are weakest
- Compare to any known market reports if applicable

Format as an investor-ready slide with numbers, not paragraphs.
"""

COMPETITIVE_ANALYSIS_PROMPT = """Analyze these competitors in {sector}:

{competitors_list}

Company being analyzed: {company_name}

For each competitor:
1. What's their actual positioning? (not what they say — what customers believe)
2. Pricing model + who they're optimized for
3. Biggest weakness based on public reviews and market perception
4. What customer segment are they ignoring?

Then: Map all competitors on a 2x2 matrix. You pick the two axes that reveal the biggest gap in the market.

Tell me where the white space is and what positioning would let {company_name} win it.
"""

MARKET_INTELLIGENCE_PROMPT = """<role>You are a senior analyst at a top-tier consulting firm preparing a quarterly intelligence brief</role>

<task>Create a comprehensive market intelligence report for {sector} covering:

1. Top 5 trends reshaping the industry right now (with evidence, not vibes)
2. 3 emerging threats most companies aren't tracking yet
3. What the smartest players are doing differently (name names)
4. Where capital is flowing (recent funding rounds, M&A activity, IPO signals)
5. Your "hot take" prediction for the next 12 months</task>

<context>This brief is for the investment team evaluating {company_name} in the {sector} sector, traded on the {market} market.</context>

<format>
- Executive summary (3 sentences max)
- Each section: insight + evidence + "so what" implication
- End with 3 strategic recommendations for a company entering this space
</format>

Write like a partner presenting to a C-suite. No filler.
"""

SWOT_ANALYSIS_PROMPT = """You are a corporate strategist at JP Morgan advising on competitive positioning.

Company: {company_name}
Industry: {sector}
Market: {market}
Top competitors: {competitors_list}

Run a SWOT analysis, but make it useful:

STRENGTHS: What does {company_name} do that competitors literally cannot copy in the next 12 months?
WEAKNESSES: What's the honest reason customers choose competitors over {company_name}?
OPPORTUNITIES: What market shift is happening RIGHT NOW that {company_name} is not exploiting?
THREATS: What could put {company_name} out of business in 2 years? (not generic "competition" — specific scenarios)

Then: Create a 2x2 action matrix:
- Strengths × Opportunities = Attack moves
- Weaknesses × Threats = Survival moves

End with: "If {company_name} could only do ONE thing this quarter, it should be ___" and defend it.
"""


def _get_gemini_provider():
    """Create a GeminiProvider with the deep thinking model.

    Returns None if GOOGLE_API_KEY is not available.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY not set — cannot run initial research")
        return None

    from ...ai.gemini import GeminiProvider
    return GeminiProvider(
        api_key=api_key,
        model=DEEP_THINKING_MODEL,
        max_retries=3,
        rate_limit_delay=15,
    )


def _determine_market(company: Company) -> str:
    """Determine market description from company data."""
    parts = []
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


def run_initial_research(company: Company) -> Optional[InitialResearch]:
    """Run all 5 strategic research prompts against Gemini deep thinking.

    Prompts are run sequentially:
      0. Competitor discovery → feeds into prompts 2 and 4
      1. TAM/SAM/SOM market sizing
      2. Competitive analysis (uses prompt 0 output)
      3. Market intelligence
      4. SWOT analysis (uses prompt 0 output)

    Args:
        company: The Company object with name, sector, etc.

    Returns:
        Populated InitialResearch, or None on failure.
    """
    provider = _get_gemini_provider()
    if not provider:
        return None

    market = _determine_market(company)
    sector = _format_sector(company.sector)

    result = InitialResearch(
        model_used=DEEP_THINKING_MODEL,
        generated_at=datetime.now().isoformat(),
    )

    # --- Prompt 0: Competitor Discovery ---
    logger.info(f"  [InitialResearch] Prompt 0/4: Competitor discovery for {company.name}...")
    try:
        prompt_0 = COMPETITOR_DISCOVERY_PROMPT.format(
            company_name=company.name,
            sector=sector,
            market=market,
        )
        result.competitors = provider.generate_with_search(
            f"{company.name} competitors {sector}",
            prompt_0,
        )
        logger.info(f"  [InitialResearch] ✓ Competitor discovery complete")
    except Exception as e:
        logger.error(f"  [InitialResearch] ✗ Competitor discovery failed: {e}")
        result.competitors = f"[Error: {e}]"

    # --- Prompt 1: TAM / SAM / SOM ---
    logger.info(f"  [InitialResearch] Prompt 1/4: TAM/SAM/SOM for {company.name}...")
    try:
        prompt_1 = TAM_SAM_SOM_PROMPT.format(
            company_name=company.name,
            sector=sector,
            market=market,
        )
        result.tam_sam_som = provider.generate_with_search(
            f"{company.name} market size TAM {sector}",
            prompt_1,
        )
        logger.info(f"  [InitialResearch] ✓ TAM/SAM/SOM complete")
    except Exception as e:
        logger.error(f"  [InitialResearch] ✗ TAM/SAM/SOM failed: {e}")
        result.tam_sam_som = f"[Error: {e}]"

    # --- Prompt 2: Competitive Analysis (uses Prompt 0 output) ---
    logger.info(f"  [InitialResearch] Prompt 2/4: Competitive analysis for {company.name}...")
    try:
        prompt_2 = COMPETITIVE_ANALYSIS_PROMPT.format(
            company_name=company.name,
            sector=sector,
            competitors_list=result.competitors or "(No competitor data available)",
        )
        result.competitive_analysis = provider.generate_with_search(
            f"{company.name} competitive landscape {sector}",
            prompt_2,
        )
        logger.info(f"  [InitialResearch] ✓ Competitive analysis complete")
    except Exception as e:
        logger.error(f"  [InitialResearch] ✗ Competitive analysis failed: {e}")
        result.competitive_analysis = f"[Error: {e}]"

    # --- Prompt 3: Market Intelligence ---
    logger.info(f"  [InitialResearch] Prompt 3/4: Market intelligence for {sector}...")
    try:
        prompt_3 = MARKET_INTELLIGENCE_PROMPT.format(
            company_name=company.name,
            sector=sector,
            market=market,
        )
        result.market_intelligence = provider.generate_with_search(
            f"{sector} industry trends funding M&A 2025 2026",
            prompt_3,
        )
        logger.info(f"  [InitialResearch] ✓ Market intelligence complete")
    except Exception as e:
        logger.error(f"  [InitialResearch] ✗ Market intelligence failed: {e}")
        result.market_intelligence = f"[Error: {e}]"

    # --- Prompt 4: SWOT Analysis (uses Prompt 0 output) ---
    logger.info(f"  [InitialResearch] Prompt 4/4: SWOT analysis for {company.name}...")
    try:
        prompt_4 = SWOT_ANALYSIS_PROMPT.format(
            company_name=company.name,
            sector=sector,
            market=market,
            competitors_list=result.competitors or "(No competitor data available)",
        )
        result.swot_analysis = provider.generate_with_search(
            f"{company.name} SWOT analysis strengths weaknesses",
            prompt_4,
        )
        logger.info(f"  [InitialResearch] ✓ SWOT analysis complete")
    except Exception as e:
        logger.error(f"  [InitialResearch] ✗ SWOT analysis failed: {e}")
        result.swot_analysis = f"[Error: {e}]"

    logger.info(f"  [InitialResearch] All prompts complete for {company.name}")
    return result
