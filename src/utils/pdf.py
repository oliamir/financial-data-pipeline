"""PDF text extraction and financial page scoring heuristic.

Ported from: code/src/intelligence/extractor.py -> _extract_financial_pages()
"""

import re
from typing import List, Tuple
from pathlib import Path

# Keywords that indicate financial table pages (Hebrew + English)
FINANCIAL_TABLE_KEYWORDS = [
    # Hebrew keywords for financial statements
    "תוסנכה", "דספה", "חוור", "םיסכנ", "תויובייחתה", "ןוה",
    "םינמוזמ", "יפסכה בצמה", "ימירזת", "ללוכה דספהה",
    # English keywords
    "revenue", "income", "loss", "assets", "liabilities", "equity",
    "cash flow", "consolidated", "balance sheet", "total assets",
    "financial position", "comprehensive loss",
]


def score_page(text: str, page_index: int, total_pages: int) -> int:
    """Score a page for financial content.

    Returns an integer score. Higher = more likely to contain financial tables.
    Threshold for inclusion is typically > 10.
    """
    if len(text.strip()) < 50:
        return 0

    score = 0

    # Count numbers (financial tables have many)
    numbers = re.findall(r"[\d,]{3,}", text)
    score += min(len(numbers), 20)

    # Check for financial keywords
    text_lower = text.lower()
    for kw in FINANCIAL_TABLE_KEYWORDS:
        if kw in text or kw in text_lower:
            score += 5

    # Bonus for pages in the latter half
    if total_pages > 0 and page_index > total_pages * 0.5:
        score += 3

    # Bonus for table-like structure (tab/space separated numbers)
    if len(re.findall(r"\d+\s+\d+", text)) > 3:
        score += 8

    return score


def extract_financial_pages(file_path: str | Path, max_chars: int = 12000) -> str:
    """Extract only the pages containing financial tables from a PDF."""
    import pdfplumber

    with pdfplumber.open(str(file_path)) as pdf:
        total_pages = len(pdf.pages)

        scored_pages: List[Tuple[int, int, str]] = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            page_score = score_page(text, i, total_pages)
            if page_score > 10:
                scored_pages.append((page_score, i, text))

        scored_pages.sort(key=lambda x: -x[0])

        selected_indices = sorted([p[1] for p in scored_pages[:15]])

        result = ""
        for idx in selected_indices:
            text = pdf.pages[idx].extract_text() or ""
            if len(result) + len(text) > max_chars:
                break
            result += f"\n=== Page {idx + 1} of {total_pages} ===\n{text}\n"

        if not result:
            start_page = int(total_pages * 0.6)
            for i in range(start_page, total_pages):
                text = pdf.pages[i].extract_text() or ""
                if len(result) + len(text) > max_chars:
                    break
                result += f"\n=== Page {i + 1} ===\n{text}\n"

        return result


def extract_all_text(file_path: str | Path) -> str:
    """Extract all text from a PDF."""
    import pdfplumber

    parts = []
    with pdfplumber.open(str(file_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n".join(parts)
