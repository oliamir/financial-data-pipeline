"""Pipeline step: calculate KPI metrics.

Computes financial ratios and metrics from extracted FinancialPeriod data.
"""

from typing import Optional

from ...models.financial import FinancialPeriod
from ...models.kpi import KPIMetrics
from ...utils.logging import get_logger

logger = get_logger(__name__)


def calculate_kpis(
    current: FinancialPeriod,
    prior: Optional[FinancialPeriod] = None,
) -> KPIMetrics:
    """Calculate KPI metrics from financial period data.

    Args:
        current: Current period financial data.
        prior: Prior period for growth calculations.

    Returns:
        Calculated KPIMetrics.
    """
    kpi = KPIMetrics.calculate(current, prior)
    logger.info(
        f"KPIs calculated for {current.company_slug} "
        f"{current.period_type} {current.fiscal_year}: "
        f"gross_margin={kpi.gross_margin}, revenue_growth={kpi.revenue_growth}"
    )
    return kpi
