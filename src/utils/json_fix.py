"""Fix common LLM JSON output issues.

Ported from: code/src/intelligence/extractor.py -> _fix_json_numbers(), _parse_response()
"""

import re
import json
from typing import Optional


def fix_json_numbers(json_str: str) -> str:
    """Fix common LLM JSON issues: comma-separated numbers and accounting notation."""
    # Fix accounting notation: (1,234) -> -1234
    json_str = re.sub(
        r"\((\d[\d,]*)\)",
        lambda m: "-" + m.group(1).replace(",", ""),
        json_str,
    )

    # Fix comma-separated numbers in JSON values: "key": 43,536 -> "key": 43536
    json_str = re.sub(
        r":\s*(-?\d{1,3}(?:,\d{3})+)(?=[,\s\n\r}])",
        lambda m: ": " + m.group(1).replace(",", ""),
        json_str,
    )

    # Remove JavaScript-style comments
    json_str = re.sub(r"//.*?$", "", json_str, flags=re.MULTILINE)

    # Remove trailing commas before } or ]
    json_str = re.sub(r",\s*([}\]])", r"\1", json_str)

    return json_str


def extract_json_from_response(response_text: str) -> Optional[dict]:
    """Extract and parse JSON from an LLM response that may contain markdown fences."""
    json_str = response_text

    # Handle markdown code blocks
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0]
    elif "```" in json_str:
        parts = json_str.split("```")
        if len(parts) >= 3:
            json_str = parts[1]

    # Find JSON boundaries
    start = json_str.find("{")
    end = json_str.rfind("}") + 1
    if start >= 0 and end > start:
        json_str = json_str[start:end]
    else:
        start = json_str.find("[")
        end = json_str.rfind("]") + 1
        if start >= 0 and end > start:
            json_str = json_str[start:end]
        else:
            return None

    # Apply fixes
    json_str = fix_json_numbers(json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def clean_numeric_value(value) -> Optional[float]:
    """Clean a value that should be numeric."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    cleaned = value.replace(",", "").replace(" ", "").replace("%", "").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None
