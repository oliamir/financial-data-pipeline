import os
from .providers import BaseProvider

CLASSIFICATION_PROMPT = """
Analyze this document and classify it into one of the following categories:
1. FINANCIAL_REPORT (Quarterly/Annual financial statements, balance sheets, income statements, cash flow)
2. PRESENTATION (Investor presentation, deck, slides)
3. IMMEDIATE_REPORT (Material event, meeting results, appointment of officers)
4. LEGAL_DOCUMENT (Voting deed, bylaws, official certificates)
5. OTHER

Return ONLY the category name, nothing else.
"""


def classify_document(provider: BaseProvider, file_path: str) -> str:
    """Classify a document into a category. Returns one of:
    'financial_report', 'presentation', 'immediate_report', 'legal_document', 'other'
    """
    # Quick heuristic check on filename
    fname = os.path.basename(file_path).lower()
    if "presentation" in fname or "מצגת" in fname:
        return "presentation"

    response = provider.prompt_with_document(file_path, CLASSIFICATION_PROMPT)
    text = response.strip().upper().replace(" ", "_")

    if "FINANCIAL" in text:
        return "financial_report"
    if "PRESENTATION" in text:
        return "presentation"
    if "IMMEDIATE" in text:
        return "immediate_report"
    if "LEGAL" in text:
        return "legal_document"
    return "other"
