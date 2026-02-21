"""OpenAI GPT AI provider.

Uses pdfplumber text fallback for document analysis since OpenAI
doesn't support native PDF upload.
"""

import os
from typing import List, Optional

from .base import BaseProvider
from ..utils.logging import get_logger

logger = get_logger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI GPT provider with pdfplumber text extraction fallback."""

    name = "openai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
    ):
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model_name = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self._api_key)
            except ImportError:
                raise RuntimeError("'openai' package not installed")
        return self._client

    def generate_text(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        return response.choices[0].message.content

    def generate_with_document(self, doc_path: str, prompt: str) -> str:
        """Extract text from PDF and send as context."""
        from ..utils.pdf import extract_financial_pages

        text_content = extract_financial_pages(doc_path)
        full_prompt = f"DOCUMENT CONTENT:\n{text_content}\n\nINSTRUCTIONS:\n{prompt}"
        return self.generate_text(full_prompt)

    def health_check(self) -> bool:
        if not self._api_key:
            return False
        return super().health_check()

    def list_models(self) -> List[str]:
        try:
            models = self.client.models.list()
            return [m.id for m in models.data if "gpt" in m.id]
        except Exception:
            return [self.model_name]
