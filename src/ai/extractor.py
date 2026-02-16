import json
import os
from datetime import datetime
from typing import List, Optional

from .providers import BaseProvider
from ..models.financial import FinancialMetric

EXTRACTION_PROMPT = """
You are an expert financial analyst. Extract the consolidated financial statements from this document.

Return a JSON object with this exact structure:
{
    "period_type": "Q3" or "FY" or "H1",
    "period_end_date": "YYYY-MM-DD",
    "fiscal_year": 2024,
    "reporting_currency": "USD" or "ILS",
    "unit": "thousands" or "millions" or "units",
    "income_statement": {
        "revenue": <number or null>,
        "cost_of_revenue": <number or null>,
        "gross_profit": <number or null>,
        "rd_expense": <number or null>,
        "sga_expense": <number or null>,
        "operating_income": <number or null>,
        "interest_expense": <number or null>,
        "net_income": <number or null>,
        "ebitda": <number or null>,
        "eps_basic": <number or null>,
        "eps_diluted": <number or null>
    },
    "balance_sheet": {
        "cash_and_equivalents": <number or null>,
        "total_current_assets": <number or null>,
        "total_assets": <number or null>,
        "short_term_debt": <number or null>,
        "total_current_liabilities": <number or null>,
        "long_term_debt": <number or null>,
        "total_liabilities": <number or null>,
        "total_equity": <number or null>
    },
    "cash_flow": {
        "cfo": <number or null>,
        "capex": <number or null>,
        "fcf": <number or null>
    }
}

CRITICAL RULES:
- Use the CONSOLIDATED statements, not standalone/parent company.
- Numbers should be in the unit specified by the report (thousands, millions, etc.) - state the unit in the "unit" field.
- If a number is clearly stated, extract it. If not found, use null.
- For period_type: use "Q1","Q2","Q3","Q4" for quarterly, "FY" for annual, "H1","H2" for half-year.
- Return ONLY the JSON, no other text.
"""

VALIDATION_PROMPT = """
You are a financial data auditor. I extracted the following JSON from the attached document.
Please verify each number against the document.

EXTRACTED DATA:
{extracted_json}

Return a JSON response:
{{
    "has_errors": true or false,
    "corrections": [
        {{"field": "revenue", "extracted": 150000, "correct": 155000, "page_reference": "page 12"}}
    ],
    "notes": "any general observations"
}}

Only flag CLEAR numerical errors, not formatting differences. If all numbers look correct, return has_errors: false with empty corrections.
Return ONLY the JSON.
"""


def extract_financials(provider: BaseProvider, file_path: str) -> dict:
    """Extract structured financial data from a document. Returns raw JSON dict."""
    print(f"  [Extract] Processing {os.path.basename(file_path)}...")
    response = provider.prompt_with_document(file_path, EXTRACTION_PROMPT)

    # Parse JSON from response
    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        json_str = response[start:end]
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  [Extract] JSON parse error: {e}")
        return {"error": str(e), "raw_response": response}


def validate_extraction(provider: BaseProvider, file_path: str, extracted: dict) -> dict:
    """Validate extracted data against the source document using a different provider."""
    extracted_json = json.dumps(extracted, indent=2)
    prompt = VALIDATION_PROMPT.format(extracted_json=extracted_json)

    print(f"  [Validate] Cross-checking extraction...")
    response = provider.prompt_with_document(file_path, prompt)

    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        return json.loads(response[start:end])
    except (json.JSONDecodeError, ValueError):
        return {"has_errors": False, "corrections": [], "notes": "Validation parse failed"}


def extraction_to_metrics(
    company_slug: str,
    extracted: dict,
    source_file: str,
    provider_name: str,
) -> List[FinancialMetric]:
    """Convert raw extraction dict into a list of FinancialMetric objects."""
    metrics = []
    now = datetime.now().isoformat()

    period_type = extracted.get("period_type", "FY")
    period_end_date = extracted.get("period_end_date", "")
    fiscal_year = extracted.get("fiscal_year", 0)
    unit = extracted.get("unit", "thousands")

    # Category mapping
    sections = {
        "income_statement": "income_statement",
        "balance_sheet": "balance_sheet",
        "cash_flow": "cash_flow",
    }

    for section_key, category in sections.items():
        section_data = extracted.get(section_key, {})
        if not isinstance(section_data, dict):
            continue
        for metric_name, value in section_data.items():
            metrics.append(FinancialMetric(
                company_slug=company_slug,
                metric_name=metric_name,
                category=category,
                period_type=period_type,
                period_end_date=period_end_date,
                fiscal_year=fiscal_year,
                value=value,
                unit=unit,
                source_file=source_file,
                source_provider=provider_name,
                extracted_at=now,
            ))

    return metrics
