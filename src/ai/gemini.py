"""Google Gemini AI provider.

Supports native PDF upload via genai, search grounding, and retry with backoff.
"""

import os
import time
from typing import List, Optional

from .base import BaseProvider
from ..utils.logging import get_logger

logger = get_logger(__name__)


class GeminiProvider(BaseProvider):
    """Google Gemini provider with native PDF support and search grounding."""

    name = "gemini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash",
        max_retries: int = 3,
        rate_limit_delay: int = 10,
    ):
        import google.generativeai as genai

        self.genai = genai
        self._api_key = api_key or os.getenv("GOOGLE_API_KEY", "")
        genai.configure(api_key=self._api_key)
        self.model_name = model
        self.max_retries = max_retries
        self.rate_limit_delay = rate_limit_delay

    def _call_with_retry(self, contents, model=None):
        """Call Gemini API with exponential backoff on rate limits."""
        m = model or self.genai.GenerativeModel(model_name=self.model_name)
        delay = self.rate_limit_delay

        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    time.sleep(delay)
                response = m.generate_content(contents)
                return response.text
            except Exception as e:
                err = str(e)
                if "429" in err or "Quota exceeded" in err or "RESOURCE_EXHAUSTED" in err:
                    if attempt < self.max_retries - 1:
                        logger.warning(f"Gemini rate limit hit. Retry {attempt + 1}/{self.max_retries} in {delay}s")
                        delay *= 1.5
                        continue
                raise

    def generate_text(self, prompt: str) -> str:
        return self._call_with_retry(prompt)

    def generate_with_document(self, doc_path: str, prompt: str) -> str:
        logger.info(f"Uploading {os.path.basename(doc_path)} to Gemini...")
        uploaded = self.genai.upload_file(path=doc_path)
        logger.info(f"Uploaded: {uploaded.uri}")
        return self._call_with_retry([prompt, uploaded])

    def generate_with_search(self, query: str, prompt: str) -> str:
        """Use Gemini's search grounding for real-time web data."""
        try:
            from google.generativeai.types import Tool

            search_tool = Tool(google_search=self.genai.protos.GoogleSearch())
            model = self.genai.GenerativeModel(
                model_name=self.model_name,
                tools=[search_tool],
            )
            full_prompt = f"Search for: {query}\n\n{prompt}"
            return self._call_with_retry(full_prompt, model=model)
        except Exception as e:
            logger.warning(f"Search grounding failed, falling back to text: {e}")
            return self.generate_text(f"Research the following topic:\n\n{query}\n\n{prompt}")

    def health_check(self) -> bool:
        if not self._api_key:
            return False
        return super().health_check()

    def list_models(self) -> List[str]:
        try:
            models = self.genai.list_models()
            return [m.name for m in models if "generateContent" in (m.supported_generation_methods or [])]
        except Exception:
            return [self.model_name]
