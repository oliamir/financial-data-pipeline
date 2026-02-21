"""Pipeline step: extract financial data from documents.

Extracts structured financial data (income statement, balance sheet,
cash flow) from PDF reports using AI providers.
"""

import json
from typing import Optional

from ...ai.task_router import TaskRouter, AITaskType
from ...models.financial import FinancialPeriod, IncomeStatement, BalanceSheet, CashFlow, PerShareData
from ...utils.json_fix import extract_json_from_response
from ...utils.logging import get_logger

logger = get_logger(__name__)

EXTRACT_PROMPT = """Extract ALL financial data from this document into the following JSON structure.
Use the EXACT field names. Leave fields as null if not found. All monetary values should be in the
document's reporting currency (state which currency). Use thousands as units unless stated otherwise.

{
  "company_slug": "<company identifier>",
  "fiscal_year": <year as integer>,
  "period_type": "<FY, Q1, Q2, Q3, Q4, H1>",
  "currency": "<ILS, USD, EUR>",
  "units": "<thousands, millions>",
  "income_statement": {
    "revenue": null, "cost_of_revenue": null, "gross_profit": null,
    "rd_expense": null, "sga_expense": null, "depreciation_amortization": null,
    "other_operating_expense": null, "total_operating_expense": null,
    "operating_income": null, "interest_income": null, "interest_expense": null,
    "other_income_expense": null, "pretax_income": null,
    "income_tax": null, "minority_interest": null, "net_income": null,
    "ebitda": null, "adjusted_ebitda": null,
    "eps_basic": null, "eps_diluted": null,
    "weighted_avg_shares_basic": null, "weighted_avg_shares_diluted": null,
    "stock_based_compensation": null
  },
  "balance_sheet": {
    "cash_and_equivalents": null, "short_term_investments": null,
    "accounts_receivable": null, "inventory": null, "total_current_assets": null,
    "ppe_net": null, "goodwill": null, "intangible_assets": null,
    "total_assets": null, "accounts_payable": null, "short_term_debt": null,
    "total_current_liabilities": null, "long_term_debt": null,
    "total_liabilities": null, "total_equity": null,
    "shares_outstanding": null
  },
  "cash_flow": {
    "net_income": null, "depreciation_amortization": null,
    "stock_based_compensation": null, "change_in_working_capital": null,
    "cash_from_operations": null, "capex": null,
    "acquisitions": null, "cash_from_investing": null,
    "debt_issued": null, "debt_repaid": null, "dividends_paid": null,
    "share_repurchases": null, "cash_from_financing": null,
    "net_change_in_cash": null, "free_cash_flow": null
  }
}

Return ONLY valid JSON. No explanations, markdown, or commentary."""


def extract_financials(
    router: TaskRouter,
    file_path: str,
    company_slug: str,
) -> Optional[FinancialPeriod]:
    """Extract financial data from a document using AI.

    Args:
        router: AI task router for provider selection.
        file_path: Path to the document.
        company_slug: Company identifier.

    Returns:
        FinancialPeriod if extraction succeeds, None otherwise.
    """
    try:
        raw_response = router.execute_with_fallback(
            AITaskType.EXTRACT,
            lambda provider, path: provider.generate_with_document(path, EXTRACT_PROMPT),
            file_path,
        )

        # Parse JSON from response
        data = extract_json_from_response(raw_response)
        if not data:
            logger.error(f"Failed to parse JSON from extraction response")
            return None

        # Override company_slug
        data["company_slug"] = company_slug

        # Validate and create model
        period = FinancialPeriod.model_validate(data)
        logger.info(
            f"Extracted {period.period_type} {period.fiscal_year} for {company_slug} "
            f"(revenue: {period.income_statement.revenue})"
        )
        return period

    except Exception as e:
        logger.error(f"Financial extraction failed for {file_path}: {e}")
        return None


def validate_extraction(
    router: TaskRouter,
    file_path: str,
    extracted: FinancialPeriod,
) -> dict:
    """Cross-validate extraction with a second provider.

    Args:
        router: AI task router.
        file_path: Original document path.
        extracted: Previously extracted data.

    Returns:
        Validation result dict with 'has_errors' and 'corrections'.
    """
    validator = router.get_validation_provider(AITaskType.EXTRACT)
    if not validator:
        return {"has_errors": False, "corrections": []}

    validation_prompt = f"""Compare this extracted financial data against the original document.
Report any errors or discrepancies.

EXTRACTED DATA:
{json.dumps(extracted.model_dump(mode="json"), indent=2)}

If the data is accurate, respond with: {{"has_errors": false, "corrections": []}}
If there are errors, respond with: {{"has_errors": true, "corrections": [{{"field": "...", "extracted": ..., "correct": ...}}]}}

Return ONLY valid JSON."""

    try:
        result = validator.generate_with_document(file_path, validation_prompt)
        validation = extract_json_from_response(result)
        if validation:
            return validation
    except Exception as e:
        logger.warning(f"Validation failed: {e}")

    return {"has_errors": False, "corrections": []}
