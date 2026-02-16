"""
IR platform profile registry.

Each profile contains CSS selectors tuned for a specific IR platform
(e.g., Q4 Inc, Notified/GlobeNewsWire, WordPress-based sites).
The GenericIRScraper picks the right profile based on `ir_platform`
from the company registry, falling back to "generic".
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class IRProfile:
    """Selector configuration for a specific IR website platform."""
    name: str

    # CSS selectors for the container holding report links
    report_container_selectors: List[str] = field(default_factory=list)

    # CSS selectors for individual report link elements
    report_link_selectors: List[str] = field(default_factory=list)

    # CSS selectors for pagination (next page) buttons/links
    pagination_selectors: List[str] = field(default_factory=list)

    # CSS selector for "Load More" / "Show More" buttons
    load_more_selector: Optional[str] = None

    # CSS selector to wait for before extraction (page readiness signal)
    wait_selector: Optional[str] = None


# ---------------------------------------------------------------------------
# Platform profiles
# ---------------------------------------------------------------------------

PROFILES: dict[str, IRProfile] = {}


def _register(profile: IRProfile) -> None:
    PROFILES[profile.name] = profile


# Q4 Inc IR platform (common for US/Canadian listed companies)
_register(IRProfile(
    name="q4",
    report_container_selectors=[
        ".module-financial-table",
        ".module_financial-table",
        ".ModuleFinancialTable",
        ".financial-table",
        "#702702702702702702702702702702702702702702",  # placeholder; real Q4 sites vary
    ],
    report_link_selectors=[
        "a.module_link-financial[href$='.pdf']",
        "a[href$='.pdf']",
        "a[data-file-type='pdf']",
        ".module_links a[href*='.pdf']",
    ],
    pagination_selectors=[
        "a.module_paginator-next",
        "button.module_paginator-next",
    ],
    load_more_selector=None,
    wait_selector=".module-financial-table",
))

# Notified / GlobeNewsWire IR platform
_register(IRProfile(
    name="notified",
    report_container_selectors=[
        ".nir-widget--financial-filings",
        "#widget-financial-filings",
        ".nir-widget--sec-filings",
        ".sec-filings-table",
    ],
    report_link_selectors=[
        "a.nir-widget--link[href$='.pdf']",
        "a[href$='.pdf']",
        ".nir-widget--table a[href*='.pdf']",
    ],
    pagination_selectors=[
        "a.nir-widget--pager-next",
        "button.nir-widget--pager-next",
    ],
    load_more_selector=None,
    wait_selector=".nir-widget--financial-filings",
))

# WordPress-based IR pages (common for Israeli companies)
_register(IRProfile(
    name="wordpress",
    report_container_selectors=[
        ".entry-content",
        ".page-content",
        ".wp-block-table",
        "article",
        ".elementor-widget-container",
    ],
    report_link_selectors=[
        "a[href$='.pdf']",
        "a[href*='/wp-content/uploads/'][href$='.pdf']",
        ".elementor-widget-container a[href$='.pdf']",
    ],
    pagination_selectors=[
        "a.next.page-numbers",
        ".nav-previous a",
    ],
    load_more_selector=".elementor-button[data-settings*='load_more']",
    wait_selector=".entry-content, .elementor-widget-container, article",
))

# Generic fallback - broad selectors
_register(IRProfile(
    name="generic",
    report_container_selectors=[
        "main",
        "#content",
        ".content",
        "article",
        "#main",
        "body",
    ],
    report_link_selectors=[
        "a[href$='.pdf']",
        "a[href*='.pdf']",
        "a[href*='download']",
        "a[href*='report']",
    ],
    pagination_selectors=[
        "a[rel='next']",
        "a.next",
        ".pagination a:last-child",
        "a:has-text('Next')",
        "a:has-text('>')",
    ],
    load_more_selector=(
        "button:has-text('Load More'), "
        "button:has-text('Show More'), "
        "button:has-text('More'), "
        "a:has-text('Load More')"
    ),
    wait_selector="body",
))


def get_profile(name: str) -> IRProfile:
    """Return the profile for the given platform name, or 'generic' as fallback."""
    return PROFILES.get(name, PROFILES["generic"])
