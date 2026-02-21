"""Pipeline step: classify documents.

Classifies documents by type using AI to determine which pipeline
steps to apply (financial extraction, memo generation, etc.).
"""

from ..ai.base import BaseProvider
from ..ai.task_router import TaskRouter, AITaskType
from ..models.document import DocumentType
from ..utils.logging import get_logger

logger = get_logger(__name__)

CLASSIFY_PROMPT = """Classify this document into one of these categories:
- financial_report (income statement, balance sheet, cash flow)
- quarterly_report (Q1/Q2/Q3/Q4 financial reports)
- annual_report (full-year financial report)
- board_report (board of directors report)
- presentation (investor presentation)
- press_release (earnings press release)
- prospectus (offering prospectus)
- other (anything else)

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
