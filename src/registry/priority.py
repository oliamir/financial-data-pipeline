from enum import Enum
from dataclasses import dataclass


class PriorityTier(Enum):
    HIGH = "high"
    LOW = "low"


@dataclass
class TierPolicy:
    ai_provider_extraction: str         # "ollama" or "gemini"
    ai_provider_memo: str               # "gemini" for high, "ollama" for low
    validation_enabled: bool            # True for high, False for low
    refresh_interval_hours: int         # 24 for high, 168 for low
    analysis_depth: str                 # "full" or "basic"


TIER_POLICIES = {
    PriorityTier.HIGH: TierPolicy(
        ai_provider_extraction="ollama",
        ai_provider_memo="gemini",
        validation_enabled=True,
        refresh_interval_hours=24,
        analysis_depth="full",
    ),
    PriorityTier.LOW: TierPolicy(
        ai_provider_extraction="ollama",
        ai_provider_memo="ollama",
        validation_enabled=False,
        refresh_interval_hours=168,
        analysis_depth="basic",
    ),
}


def get_policy(priority: str) -> TierPolicy:
    tier = PriorityTier(priority)
    return TIER_POLICIES[tier]
