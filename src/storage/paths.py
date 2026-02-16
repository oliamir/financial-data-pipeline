import os

# Project root is two levels up from src/storage/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "companies")


def company_dir(slug: str) -> str:
    path = os.path.join(DATA_DIR, slug)
    os.makedirs(path, exist_ok=True)
    return path


def reports_dir(slug: str) -> str:
    path = os.path.join(company_dir(slug), "reports")
    os.makedirs(path, exist_ok=True)
    return path


def financials_csv(slug: str) -> str:
    return os.path.join(company_dir(slug), "financials.csv")


def memo_json(slug: str) -> str:
    return os.path.join(company_dir(slug), "memo.json")


def revisions_jsonl(slug: str) -> str:
    return os.path.join(company_dir(slug), "revisions.jsonl")


def meta_json(slug: str) -> str:
    return os.path.join(company_dir(slug), "meta.json")


def report_path(slug: str, year: int, period: str, report_id: str, ext: str = "pdf") -> str:
    """Build path for a specific report file."""
    filename = f"{year}_{period}_{report_id}.{ext}"
    return os.path.join(reports_dir(slug), filename)
