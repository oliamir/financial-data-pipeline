"""Unit tests for AI layer — providers, registry, and router."""

import pytest
from unittest.mock import MagicMock, patch

from src.ai.base import BaseProvider
from src.ai.registry import ProviderRegistry
from src.ai.task_router import TaskRouter, AITaskType


# --- Mock provider for testing ---

class MockProvider(BaseProvider):
    name = "mock"

    def __init__(self, response: str = "mock response"):
        self._response = response

    def generate_text(self, prompt: str) -> str:
        return self._response

    def generate_with_document(self, doc_path: str, prompt: str) -> str:
        return self._response

    def health_check(self) -> bool:
        return True

    def list_models(self):
        return ["mock-model"]


class FailingProvider(BaseProvider):
    name = "failing"

    def generate_text(self, prompt: str) -> str:
        raise RuntimeError("Provider unavailable")

    def generate_with_document(self, doc_path: str, prompt: str) -> str:
        raise RuntimeError("Provider unavailable")


# --- BaseProvider tests ---

class TestBaseProvider:
    def test_abstract_methods(self):
        """Cannot instantiate BaseProvider directly."""
        with pytest.raises(TypeError):
            BaseProvider()

    def test_mock_provider_generate_text(self):
        provider = MockProvider("hello")
        assert provider.generate_text("test") == "hello"

    def test_mock_provider_health_check(self):
        provider = MockProvider()
        assert provider.health_check() is True

    def test_generate_with_search_fallback(self):
        provider = MockProvider("search result")
        result = provider.generate_with_search("query", "prompt")
        assert result == "search result"


# --- ProviderRegistry tests ---

class TestProviderRegistry:
    def test_empty_config(self):
        registry = ProviderRegistry(config={"providers": {}})
        assert registry.available() == []

    def test_disabled_provider_skipped(self):
        config = {
            "providers": {
                "test": {"type": "google", "enabled": False}
            }
        }
        registry = ProviderRegistry(config=config)
        assert not registry.has("test")

    def test_unknown_type_skipped(self):
        config = {
            "providers": {
                "xyz": {"type": "unknown_type"}
            }
        }
        registry = ProviderRegistry(config=config)
        assert not registry.has("xyz")

    def test_get_missing_raises(self):
        registry = ProviderRegistry(config={"providers": {}})
        with pytest.raises(KeyError, match="not available"):
            registry.get("nonexistent")

    def test_manual_registration(self):
        registry = ProviderRegistry(config={"providers": {}})
        mock = MockProvider()
        registry.providers["mock"] = mock
        assert registry.has("mock")
        assert registry.get("mock") is mock
        assert "mock" in registry.available()


# --- TaskRouter tests ---

class TestTaskRouter:
    @pytest.fixture
    def registry_with_mocks(self):
        registry = ProviderRegistry(config={"providers": {}})
        registry.providers["gemini"] = MockProvider("gemini response")
        registry.providers["ollama"] = MockProvider("ollama response")
        return registry

    @pytest.fixture
    def routing_config(self):
        return {
            "classify": {"primary": "ollama", "fallback": ["gemini"]},
            "extract": {"primary": "ollama", "fallback": ["gemini"], "validation": "gemini"},
            "memo": {"primary": "gemini", "fallback": ["ollama"]},
            "research": {"primary": "gemini", "fallback": []},
        }

    def test_get_primary_provider(self, registry_with_mocks, routing_config):
        router = TaskRouter(registry_with_mocks, routing_config)
        provider = router.get_provider(AITaskType.CLASSIFY)
        assert provider.generate_text("test") == "ollama response"

    def test_fallback_when_primary_missing(self, routing_config):
        registry = ProviderRegistry(config={"providers": {}})
        registry.providers["gemini"] = MockProvider("gemini fallback")
        # ollama is NOT registered
        router = TaskRouter(registry, routing_config)
        provider = router.get_provider(AITaskType.CLASSIFY)
        assert provider.generate_text("test") == "gemini fallback"

    def test_runtime_override(self, registry_with_mocks, routing_config):
        router = TaskRouter(registry_with_mocks, routing_config, override_provider="gemini")
        provider = router.get_provider(AITaskType.CLASSIFY)
        # Override forces gemini even though primary is ollama
        assert provider.generate_text("test") == "gemini response"

    def test_validation_provider(self, registry_with_mocks, routing_config):
        router = TaskRouter(registry_with_mocks, routing_config)
        validator = router.get_validation_provider(AITaskType.EXTRACT)
        assert validator is not None
        assert validator.generate_text("test") == "gemini response"

    def test_no_validation_for_memo(self, registry_with_mocks, routing_config):
        router = TaskRouter(registry_with_mocks, routing_config)
        validator = router.get_validation_provider(AITaskType.MEMO)
        assert validator is None

    def test_no_providers_raises(self, routing_config):
        registry = ProviderRegistry(config={"providers": {}})
        router = TaskRouter(registry, routing_config)
        with pytest.raises(RuntimeError, match="No AI provider"):
            router.get_provider(AITaskType.CLASSIFY)

    def test_execute_with_fallback_success(self, registry_with_mocks, routing_config):
        router = TaskRouter(registry_with_mocks, routing_config)
        result = router.execute_with_fallback(
            AITaskType.CLASSIFY,
            lambda provider, prompt: provider.generate_text(prompt),
            "test prompt",
        )
        assert result == "ollama response"

    def test_execute_with_fallback_on_failure(self, routing_config):
        registry = ProviderRegistry(config={"providers": {}})
        registry.providers["ollama"] = FailingProvider()
        registry.providers["gemini"] = MockProvider("gemini saved us")
        router = TaskRouter(registry, routing_config)
        result = router.execute_with_fallback(
            AITaskType.CLASSIFY,
            lambda provider, prompt: provider.generate_text(prompt),
            "test prompt",
        )
        assert result == "gemini saved us"

    def test_set_override(self, registry_with_mocks, routing_config):
        router = TaskRouter(registry_with_mocks, routing_config)
        router.set_override("gemini")
        assert router.override == "gemini"
        provider = router.get_provider(AITaskType.CLASSIFY)
        assert provider.generate_text("test") == "gemini response"
        router.set_override(None)
        assert router.override is None
