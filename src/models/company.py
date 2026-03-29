from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class CompanyType(str, Enum):
    US_TRADED = "us_traded"
    TASE_TRADED = "tase_traded"
    PRIVATE = "private"

class PriorityTier(str, Enum):
    HIGH = "high"
    LOW = "low"

class Company(BaseModel):
    """Company definition loaded from companies.yaml."""
    slug: str
    name: str
    company_type: CompanyType = CompanyType.TASE_TRADED
    priority: PriorityTier = PriorityTier.LOW
    sector: str = ""

    # TASE identifiers
    tase_id: Optional[str] = None
    tase_company_id: Optional[str] = None

    # US listing
    us_ticker: Optional[str] = None
    us_exchange: Optional[str] = None       # "NASDAQ", "NYSE"

    # IR website
    ir_url: Optional[str] = None
    ir_platform: Optional[str] = None       # "wordpress", "q4", "notified", "generic"

    # Financial
    reporting_currency: str = "ILS"
    dual_listed: bool = False
