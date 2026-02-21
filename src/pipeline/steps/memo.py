"""Pipeline step: generate/update investment memo.

Creates or updates a 13-section investment memo from financial data
and raw document content.
"""

import json
from typing import Optional

from ...ai.task_router import TaskRouter, AITaskType
from ...models.memo import InvestmentMemo
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

CURRENT MEMO:
{current_memo}

Update the memo based on the new financial report. Preserve existing analysis where still valid,
but update financial figures and revise thesis if warranted.

Return the COMPLETE updated memo as JSON (same format as original).
Return ONLY valid JSON."""


def generate_memo(
    router: TaskRouter,
    file_path: str,
    company_slug: str,
    current_memo: Optional[InvestmentMemo] = None,
) -> Optional[InvestmentMemo]:
    """Generate or update an investment memo.

    Args:
        router: AI task router.
        file_path: Path to the financial document.
        company_slug: Company identifier.
        current_memo: Existing memo to update (None for new memo).

    Returns:
        InvestmentMemo if generation succeeds.
    """
    if current_memo:
        prompt = UPDATE_MEMO_PROMPT.format(
            current_memo=json.dumps(current_memo.model_dump(mode="json"), indent=2)
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

        data["company_slug"] = company_slug
        memo = InvestmentMemo.model_validate(data)
        logger.info(f"Generated memo for {company_slug}: {memo.recommendation}")
        return memo

    except Exception as e:
        logger.error(f"Memo generation failed for {company_slug}: {e}")
        return None
