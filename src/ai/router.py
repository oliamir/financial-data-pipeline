from enum import Enum
from typing import Optional, List

from .providers import ProviderRegistry, BaseProvider
from .classifier import classify_document
from .extractor import extract_financials, validate_extraction, extraction_to_metrics
from .memo_writer import generate_memo
from ..registry.priority import TierPolicy
from ..models.financial import FinancialMetric
from ..models.memo import InvestmentMemo


class AITask(Enum):
    CLASSIFY = "classify"
    EXTRACT_FINANCIALS = "extract_financials"
    WRITE_MEMO = "write_memo"


class TaskRouter:
    """Routes AI tasks to the correct provider based on company priority."""

    def __init__(self, providers: ProviderRegistry, policy: TierPolicy):
        self.providers = providers
        self.policy = policy

    def _get_extraction_provider(self) -> BaseProvider:
        """Get the provider for extraction tasks."""
        pref = self.policy.ai_provider_extraction
        if self.providers.has(pref):
            return self.providers.get(pref)
        # Fallback to whatever is available
        if self.providers.has("gemini"):
            return self.providers.get("gemini")
        return self.providers.get(self.providers.available()[0])

    def _get_memo_provider(self) -> BaseProvider:
        """Get the provider for memo generation."""
        pref = self.policy.ai_provider_memo
        if self.providers.has(pref):
            return self.providers.get(pref)
        if self.providers.has("gemini"):
            return self.providers.get("gemini")
        return self.providers.get(self.providers.available()[0])

    def _get_validation_provider(self) -> Optional[BaseProvider]:
        """Get the provider for validation (always Gemini if available)."""
        if not self.policy.validation_enabled:
            return None
        if self.providers.has("gemini"):
            return self.providers.get("gemini")
        return None

    def classify(self, file_path: str) -> str:
        """Classify a document. Returns document type string."""
        provider = self._get_extraction_provider()
        return classify_document(provider, file_path)

    def extract(self, file_path: str, company_slug: str) -> tuple[list[FinancialMetric], str]:
        """Extract financials with optional validation. Returns (metrics, provider_name)."""
        extractor = self._get_extraction_provider()
        validator = self._get_validation_provider()

        # Step 1: Extract with primary provider
        raw = extract_financials(extractor, file_path)
        provider_name = self.policy.ai_provider_extraction

        if "error" in raw:
            # Extraction failed - escalate to Gemini if available
            if self.providers.has("gemini") and provider_name != "gemini":
                print(f"  [Router] Extraction failed with {provider_name}, escalating to Gemini...")
                gemini = self.providers.get("gemini")
                raw = extract_financials(gemini, file_path)
                provider_name = "gemini_escalated"
            if "error" in raw:
                return [], provider_name

        # Step 2: Heuristic quality check
        income = raw.get("income_statement", {})
        if income.get("revenue") is None and income.get("net_income") is None:
            # Both key fields missing - likely bad extraction
            if self.providers.has("gemini") and provider_name != "gemini":
                print(f"  [Router] Extraction looks incomplete, escalating to Gemini...")
                gemini = self.providers.get("gemini")
                raw = extract_financials(gemini, file_path)
                provider_name = "gemini_escalated"

        # Step 3: Validation (high-priority only)
        if validator and provider_name not in ("gemini", "gemini_escalated"):
            validation_result = validate_extraction(validator, file_path, raw)
            if validation_result.get("has_errors"):
                print(f"  [Router] Validation found errors, re-extracting with Gemini...")
                corrections = validation_result.get("corrections", [])
                for c in corrections:
                    print(f"    - {c.get('field')}: {c.get('extracted')} -> {c.get('correct')}")
                raw = extract_financials(validator, file_path)
                provider_name = "gemini_corrected"
            else:
                provider_name = f"{provider_name}_validated"

        # Convert to metrics
        source_file = file_path.split("/")[-1] if "/" in file_path else file_path
        metrics = extraction_to_metrics(company_slug, raw, source_file, provider_name)

        return metrics, provider_name

    def write_memo(
        self,
        file_path: str,
        company_slug: str,
        current_memo: Optional[dict] = None,
    ) -> InvestmentMemo:
        """Generate or update investment memo."""
        provider = self._get_memo_provider()
        return generate_memo(provider, file_path, company_slug, current_memo)
