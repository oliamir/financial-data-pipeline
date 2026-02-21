"""Pipeline step: generate/update investment memo.

Creates or updates a 13-section investment memo from financial data
and raw document content. Tracks revisions with version history.
"""

import json
import os
from datetime import datetime
from typing import Optional

from ...ai.task_router import TaskRouter, AITaskType
from ...models.memo import InvestmentMemo, MemoRevision
from ...utils.json_fix import extract_json_from_response
from ...utils.logging import get_logger

logger = get_logger(__name__)

MEMO_PROMPT = """You are a senior financial analyst. Generate a comprehensive investment memo
for this company based on the financial report provided. Include:

1. Company Overview (business description, market position)
2. Financial Summary (key highlights from latest period)
3. Revenue Analysis (trends, segmentation, growth drivers)
4. Profitability Analysis (margins, operating leverage)
5. Balance Sheet Review (capital structure, liquidity)
6. Cash Flow Analysis (quality of earnings, free cash flow)
7. Key Risks (top 3-5 risks with severity ratings)
8. Catalysts (near-term catalysts with timeline)
9. Valuation (multiples, peer comparison if possible)
10. Bull/Bear/Base scenarios with target prices
11. Investment Thesis (buy/hold/sell recommendation)
12. ESG considerations
13. Action items for follow-up research

Return the memo as a JSON object matching this structure:
{
  "company_slug": "<slug>",
  "recommendation": "<buy|hold|sell|speculative_buy>",
  "thesis_status": "<new|confirmed|revised|weakened>",
  "summary": "<1 paragraph executive summary>",
  "revenue_analysis": "<detailed analysis>",
  "profitability_analysis": "<detailed analysis>",
  "balance_sheet_review": "<detailed analysis>",
  "cash_flow_analysis": "<detailed analysis>",
  "risks": [{"description": "...", "severity": "<high|medium|low>", "category": "..."}],
  "catalysts": [{"description": "...", "timeline": "...", "probability": "<high|medium|low>"}],
  "scenarios": [
    {"name": "Bull", "description": "...", "target_price": null, "probability": 0.25},
    {"name": "Base", "description": "...", "target_price": null, "probability": 0.50},
    {"name": "Bear", "description": "...", "target_price": null, "probability": 0.25}
  ],
  "esg_notes": "<ESG considerations>",
  "action_items": ["follow up on...", "research..."]
}

Return ONLY valid JSON."""

UPDATE_MEMO_PROMPT = """You are a senior financial analyst updating an investment memo with new data.

CURRENT MEMO (v{version}):
{current_memo}

NEW DOCUMENT: {filename}

Update the memo based on the new financial report. Preserve existing analysis where still valid,
but update financial figures and revise thesis if warranted.

Return the COMPLETE updated memo as JSON (same format as original), plus these additional fields:
  "changes_summary": "2-3 sentence summary of what changed vs the previous version",
  "thesis_impact": "positive" or "negative" or "neutral"

Return ONLY valid JSON."""


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
        prompt = UPDATE_MEMO_PROMPT.format(
            version=current_memo.version,
            current_memo=json.dumps(memo_data, indent=2),
            filename=filename,
        )
    else:
        prompt = MEMO_PROMPT

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

