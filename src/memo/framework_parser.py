"""Parse config/memo_framework.md into structured section definitions.

The framework file uses HTML comments ``<!-- section: field_name -->`` to map
each section to an ``InvestmentMemo`` model field, and fenced code blocks under
``### Prompt`` headings to store the LLM prompt templates.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from ..utils.logging import get_logger

logger = get_logger(__name__)

# Default location relative to project root
_DEFAULT_FRAMEWORK_PATH = Path(__file__).resolve().parents[2] / "config" / "memo_framework.md"


@dataclass
class FrameworkSection:
    """A single section parsed from the memo framework file."""

    number: int
    """Section number (1-based)."""

    title: str
    """Human-readable section title, e.g. 'Executive Summary & Investment Thesis'."""

    field_name: str
    """Model field name, e.g. 'executive_summary'."""

    purpose: str = ""
    """Brief description of the section's purpose."""

    prompt_template: str = ""
    """Raw LLM prompt with ``{placeholder}`` variables."""


def parse_framework(path: Optional[str] = None) -> List[FrameworkSection]:
    """Parse the memo framework markdown file into section definitions.

    Args:
        path: Path to the framework file.  Defaults to
              ``config/memo_framework.md`` relative to the project root.

    Returns:
        Ordered list of :class:`FrameworkSection` objects.

    Raises:
        FileNotFoundError: If the framework file does not exist.
    """
    framework_path = Path(path) if path else _DEFAULT_FRAMEWORK_PATH

    if not framework_path.exists():
        raise FileNotFoundError(
            f"Memo framework file not found: {framework_path}. "
            "Expected at config/memo_framework.md"
        )

    text = framework_path.read_text(encoding="utf-8")
    sections = _extract_sections(text)

    logger.debug("Parsed %d sections from %s", len(sections), framework_path)
    return sections


def get_section_prompt(
    field_name: str,
    path: Optional[str] = None,
) -> Optional[str]:
    """Convenience: return the prompt template for a single section by field name.

    Args:
        field_name: The model field name (e.g. ``'executive_summary'``).
        path: Optional path override for the framework file.

    Returns:
        The prompt template string, or ``None`` if the section is not found.
    """
    for section in parse_framework(path):
        if section.field_name == field_name:
            return section.prompt_template
    return None


# ---------------------------------------------------------------------------
# Internal parsing helpers
# ---------------------------------------------------------------------------

# Matches: <!-- section: field_name -->
_SECTION_MARKER_RE = re.compile(r"<!--\s*section:\s*(\w+)\s*-->")

# Matches: ## N. Title   or   ## NN. Title
_HEADING_RE = re.compile(r"^##\s+(\d+)\.\s+(.+)$", re.MULTILINE)

# Matches a fenced code block (``` ... ```)
_CODE_BLOCK_RE = re.compile(r"```\s*\n(.*?)```", re.DOTALL)


def _extract_sections(text: str) -> List[FrameworkSection]:
    """Walk through the markdown text and extract sections."""
    # Split the text at each section marker
    marker_positions = [
        (m.start(), m.group(1)) for m in _SECTION_MARKER_RE.finditer(text)
    ]

    if not marker_positions:
        logger.warning("No <!-- section: ... --> markers found in framework file")
        return []

    sections: List[FrameworkSection] = []

    for idx, (start_pos, field_name) in enumerate(marker_positions):
        # Determine the end of this section (start of next marker or EOF)
        end_pos = (
            marker_positions[idx + 1][0] if idx + 1 < len(marker_positions) else len(text)
        )
        chunk = text[start_pos:end_pos]

        # Extract section number and title from the ## heading
        heading_match = _HEADING_RE.search(chunk)
        if heading_match:
            number = int(heading_match.group(1))
            title = heading_match.group(2).strip()
        else:
            number = idx + 1
            title = field_name.replace("_", " ").title()
            logger.warning(
                "No ## heading found for section '%s'; using auto-generated title '%s'",
                field_name,
                title,
            )

        # Extract purpose (text between ### Purpose and the next ### or ---)
        purpose = _extract_subsection(chunk, "Purpose")

        # Extract prompt (first code block after ### Prompt)
        prompt = ""
        prompt_heading_match = re.search(r"###\s+Prompt", chunk)
        if prompt_heading_match:
            after_heading = chunk[prompt_heading_match.end():]
            code_match = _CODE_BLOCK_RE.search(after_heading)
            if code_match:
                prompt = code_match.group(1).strip()

        sections.append(
            FrameworkSection(
                number=number,
                title=title,
                field_name=field_name,
                purpose=purpose,
                prompt_template=prompt,
            )
        )

    return sections


def _extract_subsection(chunk: str, heading_name: str) -> str:
    """Extract text under a ### heading, stopping at the next ### or ---."""
    pattern = re.compile(
        rf"###\s+{re.escape(heading_name)}\s*\n(.*?)(?=###|\n---|\Z)",
        re.DOTALL,
    )
    match = pattern.search(chunk)
    if match:
        return match.group(1).strip()
    return ""
