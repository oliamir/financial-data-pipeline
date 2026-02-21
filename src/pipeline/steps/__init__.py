"""Pipeline step: classify documents.

Classifies documents by type using AI to determine which pipeline
steps to apply (financial extraction, memo generation, etc.).
"""

from src.ai.base import BaseProvider
from src.ai.task_router import TaskRouter, AITaskType
from src.models.document import DocumentType
from src.utils.logging import get_logger

logger = get_logger(__name__)

CLASSIFY_PROMPT = """Classify this document. It may be in Hebrew or English.
Look for financial tables (דוח כספי), income/loss (רווח/הפסד), balance sheet (מאזן).

Categories:
- financial_report (has income statement, balance sheet, or cash flow data)
- quarterly_report (Q1/Q2/Q3/Q4 financial report)
- annual_report (full-year financial report / דוח שנתי)
- board_report (board of directors report / דוח דירקטוריון)
- presentation (investor presentation / מצגת)
- press_release (press release / הודעה לעיתונות)
- other (anything else)

If the document contains financial statements with numbers, classify as financial_report.
Respond with ONLY the category name, nothing else."""


def classify_document(router: TaskRouter, file_path: str) -> str:
    """Classify a document using AI.

    Args:
        router: AI task router for provider selection.
        file_path: Path to the document file.

    Returns:
        Document type string.
    """
    try:
        result = router.execute_with_fallback(
            AITaskType.CLASSIFY,
            lambda provider, path: provider.generate_with_document(path, CLASSIFY_PROMPT),
            file_path,
        )
        doc_type = result.strip().lower().replace(" ", "_")
        logger.info(f"Classified {file_path} as: {doc_type}")
        return doc_type
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        return "unknown"


def is_financial_document(doc_type: str) -> bool:
    """Check if a classified document type is a financial report."""
    financial_types = {
        "financial_report", "quarterly_report", "annual_report",
        "board_report",
    }
    return doc_type in financial_types
