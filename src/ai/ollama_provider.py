"""Ollama local LLM provider.

Supports auto-detection of available models and pdfplumber text extraction
for document analysis.
"""

import os
from typing import List, Optional

from .base import BaseProvider
from ..utils.logging import get_logger

logger = get_logger(__name__)


class OllamaProvider(BaseProvider):
    """Ollama provider for local LLM inference."""

    name = "ollama"

    # Known good models for financial analysis tasks
    PRECONFIGURED_MODELS = [
        "qwen3:8b",
        "qwen2.5:7b",
        "qwen2.5:14b",
        "llama3.1",
        "llama3.1:70b",
        "mixtral",
        "deepseek-r1:7b",
    ]

    def __init__(
        self,
        host: Optional[str] = None,
        model: str = "qwen3:8b",
        fallback_model: Optional[str] = None,
    ):
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = model
        self.fallback_model = fallback_model
        self._client = None

    @property
    def client(self):
        """Lazy-initialize Ollama client."""
        if self._client is None:
            try:
                from ollama import Client
                self._client = Client(host=self.host)
            except ImportError:
                logger.error("'ollama' package not installed. Run: pip install ollama")
                raise RuntimeError("Ollama package not available")
        return self._client

    def _extract_pdf_text(self, doc_path: str) -> str:
        """Extract text from PDF using pdfplumber."""
        from ..utils.pdf import extract_financial_pages
        return extract_financial_pages(doc_path)

    def generate_text(self, prompt: str) -> str:
        try:
            response = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response["message"]["content"]
        except Exception as e:
            if self.fallback_model and self.fallback_model != self.model:
                logger.warning(f"Ollama {self.model} failed, trying {self.fallback_model}: {e}")
                response = self.client.chat(
                    model=self.fallback_model,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response["message"]["content"]
            raise

    def generate_with_document(self, doc_path: str, prompt: str) -> str:
        text_content = self._extract_pdf_text(doc_path)
        full_prompt = f"DOCUMENT CONTENT:\n{text_content}\n\nINSTRUCTIONS:\n{prompt}"
        return self.generate_text(full_prompt)

    def health_check(self) -> bool:
        try:
            models = self.client.list()
            return len(models.get("models", [])) > 0
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    def list_models(self) -> List[str]:
        try:
            result = self.client.list()
            return [m["name"] for m in result.get("models", [])]
        except Exception:
            return []
