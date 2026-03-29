"""Pipeline step: generate/update investment memo.

Creates or updates a 13-section investment memo from financial data
and raw document content. Tracks revisions with version history.
"""

import json
import os
from datetime import datetime
from typing import Optional

from ...ai.task_router import TaskRouter, AITaskType
from ...memo.framework_parser import parse_framework
from ...models.memo import InvestmentMemo, MemoRevision
from ...utils.json_fix import extract_json_from_response
from ...utils.logging import get_logger

logger = get_logger(__name__)

def _build_memo_prompt(company_slug: str) -> str:
    """Build the memo generation prompt dynamically from the framework file.

    Reads ``config/memo_framework.md`` via :func:`parse_framework`, enumerates
    every section the LLM must populate, and embeds the framework's analytical
    philosophy into the system prompt.

    Args:
        company_slug: Company identifier used in the prompt context.

    Returns:
        Fully-formed prompt string ready to send to the LLM.
    """
    try:
        framework = parse_framework()
    except FileNotFoundError:
        logger.warning("Memo framework file not found; using fallback section list")
        framework = []

    # Build the section instruction list from the framework
    if framework:
        section_instructions = []
        for section in framework:
            purpose_snippet = section.purpose[:120] if section.purpose else section.title
            section_instructions.append(
                f'- "{section.field_name}": {section.title} -- {purpose_snippet}'
            )
        sections_list = "\n".join(section_instructions)
    else:
        # Fallback: list the model fields directly so the prompt still works
        # even if the framework file is missing.
        sections_list = "\n".join([
            '- "executive_summary": Executive Summary & Investment Thesis',
            '- "company_overview": Company Overview & Business Model',
            '- "market_size": Market Size -- TAM / SAM / SOM',
            '- "industry_analysis": Industry Trends & Dynamics',
            '- "competitive_positioning": Competitive Landscape',
            '- "seven_powers": Seven Powers Analysis',
            '- "swot_analysis": SWOT Analysis',
            '- "management_governance": Management Quality & Governance',
            '- "ownership_structure": Ownership Structure & Shareholder Dynamics',
            '- "financial_analysis": Financial Analysis',
            '- "valuation": Valuation',
            '- "scenario_analysis": Scenario Analysis',
            '- "risks_mitigants": Risks & Mitigants',
            '- "catalysts_timeline": Catalysts & Timeline',
            '- "esg_notes": ESG & Governance Notes',
            '- "israel_risk_factors": Israel-Specific Risk Factors',
            '- "investment_conclusion": Qualitative Investment Conclusion',
            '- "open_questions": Open Questions',
            '- "action_items": Action Items (return as list of strings)',
            '- "appendix": Appendix',
        ])

    return f"""You are a senior buy-side equity research analyst specializing in Israeli public companies (TASE).
You are skeptical by default and opinionated by conclusion.

Analyze the attached financial document for company "{company_slug}" and produce a structured investment memo.

ANALYTICAL PHILOSOPHY:
- Start from skepticism. Default assumption: company has NO structural competitive power.
- For every tailwind, name a headwind. For every claimed moat, identify the erosion mechanism.
- Be specific and falsifiable. "Strong brand" is not a strength.
- If data is insufficient, say so explicitly. Do not fabricate conviction.
- TASE rewards this approach: Israel's small market makes structural advantages and their absence unusually visible.

Return a JSON object with these text section fields (each 200-800 words of professional analysis):

{sections_list}

Also include these structured fields:
- "recommendation": one of "buy", "speculative_buy", "hold", "sell", "monitor"
- "conviction": one of "high", "medium", "low"
- "thesis_status": one of "new", "confirmed", "revised", "weakening", "broken"
- "scenarios": list of objects with "name", "probability_pct", "target_price", "currency", "description", "key_assumptions"
- "risks": list of objects with "category", "severity", "description", "mitigation"
- "catalysts": list of objects with "description", "timeframe", "impact", "probability"

IMPORTANT:
- For Israel/TASE companies, always address Israel-specific factors (geopolitical, regulatory, liquidity, currency).
- Return ONLY valid JSON. No markdown wrapping, no explanation outside the JSON.
"""


def _build_update_prompt(
    company_slug: str,
    version: int,
    current_memo_json: str,
    filename: str,
) -> str:
    """Build the memo update prompt dynamically from the framework file.

    Similar to :func:`_build_memo_prompt` but instructs the LLM to update an
    existing memo rather than create one from scratch.

    Args:
        company_slug: Company identifier.
        version: Current memo version number.
        current_memo_json: JSON string of the existing memo data.
        filename: Name of the new document being incorporated.

    Returns:
        Fully-formed update prompt string.
    """
    try:
        framework = parse_framework()
    except FileNotFoundError:
        logger.warning("Memo framework file not found; using fallback section list for update")
        framework = []

    # Build the section instruction list from the framework
    if framework:
        section_instructions = []
        for section in framework:
            purpose_snippet = section.purpose[:120] if section.purpose else section.title
            section_instructions.append(
                f'- "{section.field_name}": {section.title} -- {purpose_snippet}'
            )
        sections_list = "\n".join(section_instructions)
    else:
        sections_list = "\n".join([
            '- "executive_summary": Executive Summary & Investment Thesis',
            '- "company_overview": Company Overview & Business Model',
            '- "market_size": Market Size -- TAM / SAM / SOM',
            '- "industry_analysis": Industry Trends & Dynamics',
            '- "competitive_positioning": Competitive Landscape',
            '- "seven_powers": Seven Powers Analysis',
            '- "swot_analysis": SWOT Analysis',
            '- "management_governance": Management Quality & Governance',
            '- "ownership_structure": Ownership Structure & Shareholder Dynamics',
            '- "financial_analysis": Financial Analysis',
            '- "valuation": Valuation',
            '- "scenario_analysis": Scenario Analysis',
            '- "risks_mitigants": Risks & Mitigants',
            '- "catalysts_timeline": Catalysts & Timeline',
            '- "esg_notes": ESG & Governance Notes',
            '- "israel_risk_factors": Israel-Specific Risk Factors',
            '- "investment_conclusion": Qualitative Investment Conclusion',
            '- "open_questions": Open Questions',
            '- "action_items": Action Items (return as list of strings)',
            '- "appendix": Appendix',
        ])

    return f"""You are a senior buy-side equity research analyst updating an investment memo with new data.
You are skeptical by default and opinionated by conclusion.

ANALYTICAL PHILOSOPHY:
- Start from skepticism. Default assumption: company has NO structural competitive power.
- For every tailwind, name a headwind. For every claimed moat, identify the erosion mechanism.
- Be specific and falsifiable. "Strong brand" is not a strength.
- If data is insufficient, say so explicitly. Do not fabricate conviction.
- TASE rewards this approach: Israel's small market makes structural advantages and their absence unusually visible.

CURRENT MEMO (v{version}) for "{company_slug}":
{current_memo_json}

NEW DOCUMENT: {filename}

Update the memo based on the new financial report. Preserve existing analysis where still valid,
but update financial figures and revise thesis if warranted. Pay special attention to populating
any sections that are currently empty.

Return the COMPLETE updated memo as a JSON object with ALL of these text section fields:

{sections_list}

Also include these structured fields:
- "recommendation": one of "buy", "speculative_buy", "hold", "sell", "monitor"
- "conviction": one of "high", "medium", "low"
- "thesis_status": one of "new", "confirmed", "revised", "weakening", "broken"
- "scenarios": list of objects with "name", "probability_pct", "target_price", "currency", "description", "key_assumptions"
- "risks": list of objects with "category", "severity", "description", "mitigation"
- "catalysts": list of objects with "description", "timeframe", "impact", "probability"

Plus these revision-tracking fields:
- "changes_summary": 2-3 sentence summary of what changed vs the previous version
- "thesis_impact": "positive" or "negative" or "neutral"

IMPORTANT:
- Each text field should contain 200-800 words of professional analysis.
- For Israel/TASE companies, always address Israel-specific factors.
- Return ONLY valid JSON. No markdown wrapping, no explanation outside the JSON.
"""


def generate_memo(
    router: TaskRouter,
    file_path: str,
    company_slug: str,
    current_memo: Optional[InvestmentMemo] = None,
) -> Optional[InvestmentMemo]:
    """Generate or update an investment memo with versioning.

    Args:
        router: AI task router.
        file_path: Path to the financial document.
        company_slug: Company identifier.
        current_memo: Existing memo to update (None for new memo).

    Returns:
        InvestmentMemo if generation succeeds.
    """
    filename = os.path.basename(file_path)

    if current_memo:
        # Exclude initial_research from the memo dump sent to LLM (too large)
        memo_data = current_memo.model_dump(mode="json")
        memo_data.pop("initial_research", None)
        memo_data.pop("revisions", None)
        prompt = _build_update_prompt(
            company_slug=company_slug,
            version=current_memo.version,
            current_memo_json=json.dumps(memo_data, indent=2),
            filename=filename,
        )
    else:
        prompt = _build_memo_prompt(company_slug)

    try:
        raw_response = router.execute_with_fallback(
            AITaskType.MEMO,
            lambda provider, path, p: provider.generate_with_document(path, p),
            file_path,
            prompt,
        )

        data = extract_json_from_response(raw_response)
        if not data:
            logger.error("Failed to parse memo JSON")
            return None

        # Extract revision tracking fields before model validation
        changes_summary = data.pop("changes_summary", "")
        thesis_impact = data.pop("thesis_impact", "neutral")

        data["company_slug"] = company_slug

        if current_memo:
            # Preserve fields that shouldn't be overwritten
            new_version = current_memo.version + 1
            data["version"] = new_version

            # Preserve initial research
            data["initial_research"] = current_memo.initial_research.model_dump(mode="json")

            # Carry over existing revisions and append new one
            revisions = [r.model_dump(mode="json") for r in current_memo.revisions]
            revisions.append(MemoRevision(
                version=new_version,
                date=datetime.now().strftime("%Y-%m-%d"),
                source_file=filename,
                changes_summary=changes_summary,
                thesis_impact=thesis_impact,
            ).model_dump(mode="json"))
            data["revisions"] = revisions
        else:
            data["version"] = 1
            data["revisions"] = []

        data["last_updated"] = datetime.now().isoformat()

        memo = InvestmentMemo.model_validate(data)
        logger.info(f"Generated memo v{memo.version} for {company_slug}: {memo.recommendation}")
        return memo

    except Exception as e:
        logger.error(f"Memo generation failed for {company_slug}: {e}")
        return None

