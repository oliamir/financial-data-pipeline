"""AI task router — routes tasks to providers based on config routing table.

Supports primary provider selection, fallback chains, runtime override,
and validation with a separate provider.
"""

from enum import Enum
from typing import Optional, List, Dict

from .base import BaseProvider
from .registry import ProviderRegistry
from ..config.loader import load_providers_config
from ..utils.logging import get_logger

logger = get_logger(__name__)


class AITaskType(str, Enum):
    """Types of AI tasks that can be routed."""
    CLASSIFY = "classify"
    EXTRACT = "extract"
    MEMO = "memo"
    RESEARCH = "research"


class TaskRouter:
    """Routes AI tasks to the appropriate provider with fallback support.

    Uses the routing table from providers.yaml to determine which provider
    handles each task type, with configurable fallback chains and runtime override.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        routing_config: Optional[dict] = None,
        override_provider: Optional[str] = None,
    ):
        self.registry = registry
        self.override = override_provider

        if routing_config is None:
            config = load_providers_config()
            routing_config = config.get("routing", {})
        self._routing = routing_config

    def _get_route(self, task_type: AITaskType) -> dict:
        """Get routing config for a task type."""
        return self._routing.get(task_type.value, {})

    def get_provider(self, task_type: AITaskType) -> BaseProvider:
        """Get the best available provider for a task type.

        Resolution order:
        1. Runtime override (if set and available)
        2. Primary provider from routing table
        3. Fallback chain from routing table
        4. Any available provider

        Args:
            task_type: The AI task to route.

        Returns:
            A BaseProvider instance.

        Raises:
            RuntimeError: If no provider is available.
        """
        # 1. Runtime override
        if self.override and self.registry.has(self.override):
            return self.registry.get(self.override)

        route = self._get_route(task_type)

        # 2. Primary
        primary = route.get("primary", "gemini")
        if self.registry.has(primary):
            return self.registry.get(primary)

        # 3. Fallback chain
        for fallback in route.get("fallback", []):
            if self.registry.has(fallback):
                logger.info(f"Using fallback '{fallback}' for {task_type.value} (primary '{primary}' unavailable)")
                return self.registry.get(fallback)

        # 4. Any available
        available = self.registry.available()
        if available:
            provider_name = available[0]
            logger.warning(f"No configured provider for {task_type.value}, using '{provider_name}'")
            return self.registry.get(provider_name)

        raise RuntimeError(f"No AI provider available for task: {task_type.value}")

    def get_validation_provider(self, task_type: AITaskType) -> Optional[BaseProvider]:
        """Get the validation provider for a task (if configured).

        Validation uses a separate provider (typically Gemini) to cross-check
        extraction results from the primary provider.

        Args:
            task_type: The AI task type.

        Returns:
            A BaseProvider for validation, or None if not configured.
        """
        route = self._get_route(task_type)
        validation_provider = route.get("validation")
        if validation_provider and self.registry.has(validation_provider):
            return self.registry.get(validation_provider)
        return None

    def execute_with_fallback(
        self,
        task_type: AITaskType,
        fn,
        *args,
        **kwargs,
    ) -> str:
        """Execute a function with the routed provider, falling back on failure.

        Args:
            task_type: The AI task type for routing.
            fn: A callable that takes (provider, *args, **kwargs) and returns str.
            *args: Arguments passed to fn after the provider.
            **kwargs: Keyword arguments passed to fn.

        Returns:
            The result from fn.

        Raises:
            RuntimeError: If all providers fail.
        """
        # Collect providers to try in order
        providers_to_try = []

        # Override
        if self.override and self.registry.has(self.override):
            providers_to_try.append(self.override)

        route = self._get_route(task_type)
        primary = route.get("primary", "gemini")
        if primary not in providers_to_try and self.registry.has(primary):
            providers_to_try.append(primary)

        for fb in route.get("fallback", []):
            if fb not in providers_to_try and self.registry.has(fb):
                providers_to_try.append(fb)

        # Add any remaining available providers
        for name in self.registry.available():
            if name not in providers_to_try:
                providers_to_try.append(name)

        if not providers_to_try:
            raise RuntimeError(f"No AI provider available for task: {task_type.value}")

        last_error = None
        for name in providers_to_try:
            provider = self.registry.get(name)
            try:
                result = fn(provider, *args, **kwargs)
                return result
            except Exception as e:
                logger.warning(f"{task_type.value} failed with '{name}': {e}")
                last_error = e

        raise RuntimeError(f"All providers failed for {task_type.value}. Last error: {last_error}")

    def set_override(self, provider_name: Optional[str]) -> None:
        """Set or clear the runtime provider override."""
        self.override = provider_name
        if provider_name:
            logger.info(f"Provider override set to: {provider_name}")
        else:
            logger.info("Provider override cleared")
