"""Anthropic Claude AI provider.

Supports native PDF via base64 encoding.
"""

import os
import base64
from typing import List, Optional

from .base import BaseProvider
from ..utils.logging import get_logger

logger = get_logger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic Claude provider with native PDF support via base64."""

    name = "anthropic"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model_name = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
            except ImportError:
                raise RuntimeError("'anthropic' package not installed")
        return self._client

    def generate_text(self, prompt: str) -> str:
        message = self.client.messages.create(
            model=self.model_name,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    def generate_with_document(self, doc_path: str, prompt: str) -> str:
        """Send PDF as base64 to Claude."""
        with open(doc_path, "rb") as f:
            pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")

        message = self.client.messages.create(
            model=self.model_name,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return message.content[0].text

    def health_check(self) -> bool:
        if not self._api_key:
            return False
        return super().health_check()

    def list_models(self) -> List[str]:
        return [self.model_name]
