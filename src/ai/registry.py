"""Provider registry — loads and manages AI provider instances from config."""

import os
from typing import Dict, List, Optional

from .base import BaseProvider
from ..config.loader import load_providers_config
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ProviderRegistry:
    """Manages AI provider instances loaded from providers.yaml."""

    def __init__(self, config: Optional[dict] = None):
        self.providers: Dict[str, BaseProvider] = {}
        if config is None:
            config = load_providers_config()
        self._load(config)

    def _load(self, config: dict) -> None:
        """Initialize providers from config dict."""
        for name, cfg in config.get("providers", {}).items():
            if cfg.get("enabled") is False:
                logger.debug(f"Provider '{name}' disabled, skipping")
                continue

            try:
                provider = self._create_provider(name, cfg)
                if provider:
                    self.providers[name] = provider
                    logger.info(f"Provider '{name}' configured ({cfg.get('model', '?')})")
            except Exception as e:
                logger.warning(f"Provider '{name}' failed to initialize: {e}")

    def _create_provider(self, name: str, cfg: dict) -> Optional[BaseProvider]:
        """Create a provider instance from config."""
        provider_type = cfg.get("type", name)

        if provider_type == "google":
            api_key = os.getenv(cfg.get("api_key_env", "GOOGLE_API_KEY"))
            if not api_key:
                logger.debug(f"Gemini skipped (no API key in {cfg.get('api_key_env')})")
                return None
            from .gemini import GeminiProvider
            return GeminiProvider(
                api_key=api_key,
                model=cfg.get("model", "gemini-2.0-flash"),
                max_retries=cfg.get("max_retries", 3),
                rate_limit_delay=cfg.get("rate_limit_delay", 10),
            )

        elif provider_type == "ollama":
            host = os.getenv(
                cfg.get("host_env", "OLLAMA_HOST"),
                cfg.get("host_default", "http://localhost:11434"),
            )
            from .ollama_provider import OllamaProvider
            return OllamaProvider(
                host=host,
                model=cfg.get("model", "qwen2.5:7b"),
                fallback_model=cfg.get("fallback_model"),
            )

        elif provider_type == "anthropic":
            api_key = os.getenv(cfg.get("api_key_env", "ANTHROPIC_API_KEY"))
            if not api_key:
                logger.debug(f"Anthropic skipped (no API key)")
                return None
            from .anthropic_provider import AnthropicProvider
            return AnthropicProvider(
                api_key=api_key,
                model=cfg.get("model", "claude-sonnet-4-20250514"),
            )

        elif provider_type == "openai":
            api_key = os.getenv(cfg.get("api_key_env", "OPENAI_API_KEY"))
            if not api_key:
                logger.debug(f"OpenAI skipped (no API key)")
                return None
            from .openai_provider import OpenAIProvider
            return OpenAIProvider(
                api_key=api_key,
                model=cfg.get("model", "gpt-4o"),
            )

        else:
            logger.warning(f"Unknown provider type: {provider_type}")
            return None

    def get(self, name: str) -> BaseProvider:
        """Get a provider by name. Raises KeyError if not available."""
        if name not in self.providers:
            raise KeyError(f"Provider '{name}' not available. Available: {self.available()}")
        return self.providers[name]

    def has(self, name: str) -> bool:
        """Check if a provider is available."""
        return name in self.providers

    def available(self) -> List[str]:
        """List available provider names."""
        return list(self.providers.keys())

    def health_check_all(self) -> Dict[str, bool]:
        """Run health checks on all providers."""
        results = {}
        for name, provider in self.providers.items():
            results[name] = provider.health_check()
        return results
