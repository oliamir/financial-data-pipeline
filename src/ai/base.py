"""Base AI provider interface.

All AI providers implement this interface, enabling pluggable LLM backends
with a uniform API for document analysis, text generation, and health checks.
"""

from abc import ABC, abstractmethod
from typing import Optional, List

from ..utils.logging import get_logger

logger = get_logger(__name__)


class BaseProvider(ABC):
    """Abstract base class for AI providers."""

    name: str = "base"

    @abstractmethod
    def generate_text(self, prompt: str) -> str:
        """Send a text-only prompt and return the response.

        Args:
            prompt: The text prompt to send.

        Returns:
            The model's text response.
        """
        pass

    @abstractmethod
    def generate_with_document(self, doc_path: str, prompt: str) -> str:
        """Send a prompt with a document (PDF) and return the response.

        Args:
            doc_path: Path to the document file (typically PDF).
            prompt: The instruction prompt.

        Returns:
            The model's text response.
        """
        pass

    def generate_with_search(self, query: str, prompt: str) -> str:
        """Send a prompt with web search grounding (optional capability).

        Default implementation falls back to generate_text.

        Args:
            query: The search query for grounding.
            prompt: The instruction prompt.

        Returns:
            The model's text response.
        """
        return self.generate_text(f"Research the following topic and then answer:\n\nTopic: {query}\n\n{prompt}")

    def health_check(self) -> bool:
        """Check if the provider is available and responding.

        Returns:
            True if the provider is healthy.
        """
        try:
            response = self.generate_text("Respond with exactly: OK")
            return len(response.strip()) > 0
        except Exception as e:
            logger.warning(f"Health check failed for {self.name}: {e}")
            return False

    def list_models(self) -> List[str]:
        """List available models for this provider.

        Returns:
            List of model name strings.
        """
        return []
