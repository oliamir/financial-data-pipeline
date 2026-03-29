"""Currency conversion helpers."""

from typing import Optional

DEFAULT_ILS_USD_RATE = 3.65


def ils_to_usd(amount: Optional[float], rate: Optional[float] = None) -> Optional[float]:
    """Convert ILS amount to USD."""
    if amount is None:
        return None
    r = rate or DEFAULT_ILS_USD_RATE
    return round(amount / r, 2)


def usd_to_ils(amount: Optional[float], rate: Optional[float] = None) -> Optional[float]:
    """Convert USD amount to ILS."""
    if amount is None:
        return None
    r = rate or DEFAULT_ILS_USD_RATE
    return round(amount * r, 2)
