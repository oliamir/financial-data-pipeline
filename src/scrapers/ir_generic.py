"""
Generic IR (Investor Relations) website scraper.

Uses Playwright to scrape any company's IR website for financial report PDFs.
Two-phase link discovery:
  1. Heuristic phase  - find <a> tags with .pdf hrefs or financial keywords
  2. LLM fallback     - if heuristics find <2 results, send cleaned HTML to an
                        LLM for link identification (optional; skipped when no
                        LLM provider is configured)

Designed to work with per-platform selector profiles (see ir_profiles.py) so
that the same code handles Q4, Notified, WordPress, and unknown IR sites.
"""

import asyncio
import hashlib
import re
import time
from typing import List, Optional
from urllib.parse import urljoin, urlparse

from playwright.async_api import (
    async_playwright,
    Page,
    TimeoutError as PlaywrightTimeout,
)

from .base import BaseScraper
from .ir_profiles import IRProfile, get_profile
from ..models.report import ReportMetadata

# ---------------------------------------------------------------------------
# Timeout constants
# ---------------------------------------------------------------------------
OVERALL_TIMEOUT_SECONDS = 120        # hard cap for the entire fetch_reports()
PAGE_GOTO_TIMEOUT_MS = 30_000        # Playwright navigation timeout
SELECTOR_WAIT_TIMEOUT_MS = 10_000    # wait for profile's wait_selector
PAGINATION_CLICK_TIMEOUT_MS = 5_000  # wait after clicking Load More / Next
MAX_PAGINATION_CLICKS = 10           # prevent infinite pagination loops

# ---------------------------------------------------------------------------
# Financial keywords (Hebrew + English) used for scoring / filtering links
# ---------------------------------------------------------------------------
FINANCIAL_KEYWORDS = [
    # Hebrew
    "דוח כספי",
    "דוח רבעון",
    "דוח תקופתי",
    "דוח שנתי",
    "דוחות כספיים",
    "דוח ביניים",
    # English
    "financial report",
    "annual report",
    "quarterly report",
    "interim report",
    "financial statements",
    "10-k",
    "10-q",
    "20-f",
    "6-k",
]

# Broader keywords that suggest the link *might* be a report
REPORT_HINT_KEYWORDS = [
    "report", "דוח", "annual", "שנתי", "quarterly", "רבעון",
    "financial", "כספי", "statements", "filing", "sec",
    "10-k", "10-q", "20-f", "6-k", "תקופתי", "ביניים",
]


class GenericIRScraper(BaseScraper):
    """Scrapes an IR website for financial-report PDF links."""

    def __init__(
        self,
        company_slug: str,
        company_name: str,
        ir_url: str,
        ir_profile: str = "generic",
    ):
        super().__init__(company_slug, company_name)
        self.ir_url = ir_url
        self.profile: IRProfile = get_profile(ir_profile)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_reports(
        self,
        years_back: int = 5,
        **kwargs,
    ) -> List[ReportMetadata]:
        """Navigate to the IR page, discover PDF links, return metadata.

        Keyword args (all optional):
            llm_provider  - callable(prompt: str) -> str for LLM fallback
        """
        llm_provider = kwargs.get("llm_provider", None)
        start_time = time.monotonic()

        print(
            f"  [IR] Scraping {self.company_name} IR: {self.ir_url} "
            f"(profile={self.profile.name})",
            flush=True,
        )

        links: list[dict] = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-http2",
                    ],
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1920, "height": 1280},
                )
                context.set_default_navigation_timeout(PAGE_GOTO_TIMEOUT_MS)
                context.set_default_timeout(SELECTOR_WAIT_TIMEOUT_MS)

                page = await context.new_page()

                try:
                    # Navigate
                    await page.goto(
                        self.ir_url,
                        timeout=PAGE_GOTO_TIMEOUT_MS,
                        wait_until="domcontentloaded",
                    )

                    # Wait for readiness signal
                    await self._wait_for_ready(page)

                    # Handle pagination / "Load More" to reveal hidden links
                    await self._handle_pagination(page)

                    # Phase 1 - heuristic extraction
                    links = await self._extract_links_heuristic(page)
                    print(
                        f"  [IR] Heuristic phase found {len(links)} candidate links",
                        flush=True,
                    )

                    # Phase 2 - LLM fallback when heuristics underperform
                    if len(links) < 2 and llm_provider is not None:
                        elapsed = time.monotonic() - start_time
                        if elapsed < OVERALL_TIMEOUT_SECONDS - 15:
                            llm_links = await self._extract_links_llm(
                                page, llm_provider
                            )
                            if llm_links:
                                print(
                                    f"  [IR] LLM fallback found {len(llm_links)} "
                                    f"additional links",
                                    flush=True,
                                )
                                links = self._merge_links(links, llm_links)
                        else:
                            print(
                                f"  [IR] Skipping LLM fallback (time budget "
                                f"exhausted: {elapsed:.0f}s)",
                                flush=True,
                            )

                finally:
                    try:
                        await asyncio.wait_for(browser.close(), timeout=10)
                    except Exception:
                        print(
                            "  [IR] Warning: browser.close() timed out",
                            flush=True,
                        )

        except PlaywrightTimeout:
            print(
                f"  [IR] Playwright timeout navigating to {self.ir_url}",
                flush=True,
            )
        except Exception as e:
            print(
                f"  [IR] Error scraping {self.ir_url}: {type(e).__name__}: {e}",
                flush=True,
            )

        # Deduplicate by URL
        links = self._deduplicate_links(links)

        # Convert to ReportMetadata
        reports = []
        for link_info in links:
            try:
                report = self._build_report_metadata(link_info)
                if report is not None:
                    reports.append(report)
            except Exception as e:
                print(
                    f"  [IR] Failed to build metadata for {link_info.get('url', '?')}: {e}",
                    flush=True,
                )

        print(
            f"  [IR] Returning {len(reports)} report(s) for {self.company_name} "
            f"(elapsed {time.monotonic() - start_time:.0f}s)",
            flush=True,
        )
        return reports

    # ------------------------------------------------------------------
    # Phase 1: Heuristic link extraction
    # ------------------------------------------------------------------

    async def _extract_links_heuristic(self, page: Page) -> list[dict]:
        """Find all <a> tags with PDF hrefs or financial keywords and score them."""
        results: list[dict] = []

        # Strategy A: use profile-specific selectors
        for selector in self.profile.report_link_selectors:
            try:
                locator = page.locator(selector)
                count = await locator.count()
                for i in range(count):
                    info = await self._extract_anchor_info(locator.nth(i))
                    if info:
                        info["match_source"] = f"profile:{selector}"
                        results.append(info)
            except Exception:
                continue

        # Strategy B: broad sweep - all <a> with href containing .pdf
        try:
            pdf_links = page.locator("a[href*='.pdf']")
            count = await pdf_links.count()
            for i in range(count):
                info = await self._extract_anchor_info(pdf_links.nth(i))
                if info:
                    info["match_source"] = "broad:pdf_href"
                    results.append(info)
        except Exception as e:
            print(f"  [IR] Broad PDF sweep error: {e}", flush=True)

        # Strategy C: links whose visible text contains financial keywords
        for kw in FINANCIAL_KEYWORDS:
            try:
                kw_links = page.locator(f"a:has-text('{kw}')")
                count = await kw_links.count()
                for i in range(count):
                    info = await self._extract_anchor_info(kw_links.nth(i))
                    if info:
                        info["match_source"] = f"keyword:{kw}"
                        results.append(info)
            except Exception:
                continue

        # Score every link
        for link in results:
            link["score"] = self._score_link(link)

        # Sort by score descending
        results.sort(key=lambda x: x.get("score", 0), reverse=True)

        return results

    async def _extract_anchor_info(self, locator) -> Optional[dict]:
        """Extract href, text, and title from a single <a> locator."""
        try:
            href = await locator.get_attribute("href")
            if not href:
                return None

            # Resolve relative URLs
            href = urljoin(self.ir_url, href.strip())

            # Skip non-http links (mailto, javascript, etc.)
            parsed = urlparse(href)
            if parsed.scheme not in ("http", "https", ""):
                return None

            text = ""
            try:
                text = (await locator.text_content()) or ""
            except Exception:
                pass

            title = ""
            try:
                title = (await locator.get_attribute("title")) or ""
            except Exception:
                pass

            return {
                "url": href,
                "text": text.strip(),
                "title": title.strip(),
            }
        except Exception:
            return None

    def _score_link(self, link: dict) -> int:
        """Score a link by relevance. Higher = more likely a financial report PDF."""
        score = 0
        url = link.get("url", "").lower()
        text = link.get("text", "").lower()
        title = link.get("title", "").lower()
        combined = f"{url} {text} {title}"

        # PDF in URL is a strong signal
        if ".pdf" in url:
            score += 10

        # Financial keywords
        for kw in FINANCIAL_KEYWORDS:
            if kw.lower() in combined:
                score += 5

        # Broader hints
        for kw in REPORT_HINT_KEYWORDS:
            if kw.lower() in combined:
                score += 1

        # Year presence (recent years score higher)
        year_match = re.search(r"20(2[0-9]|1[0-9])", combined)
        if year_match:
            yr = int(year_match.group(0))
            if yr >= 2020:
                score += 3
            else:
                score += 1

        # Penalize obviously non-report PDFs
        noise_words = [
            "privacy", "cookie", "terms", "disclaimer", "logo",
            "brochure", "presentation", "press release", "הודעה לעיתונות",
        ]
        for nw in noise_words:
            if nw in combined:
                score -= 5

        return score

    # ------------------------------------------------------------------
    # Pagination / "Load More" handling
    # ------------------------------------------------------------------

    async def _handle_pagination(self, page: Page) -> None:
        """Click 'Load More' / 'Next' buttons to reveal all report links."""
        clicks = 0

        # Try "Load More" first
        if self.profile.load_more_selector:
            while clicks < MAX_PAGINATION_CLICKS:
                try:
                    btn = page.locator(self.profile.load_more_selector).first
                    if await btn.count() == 0:
                        break
                    if not await btn.is_visible():
                        break

                    await btn.click(timeout=PAGINATION_CLICK_TIMEOUT_MS)
                    clicks += 1
                    print(
                        f"  [IR] Clicked 'Load More' (#{clicks})",
                        flush=True,
                    )
                    # Wait for new content
                    await asyncio.sleep(1.5)
                except PlaywrightTimeout:
                    print("  [IR] Load More click timed out, stopping", flush=True)
                    break
                except Exception:
                    break

        # Try pagination (Next) buttons
        if clicks == 0:
            for selector in self.profile.pagination_selectors:
                while clicks < MAX_PAGINATION_CLICKS:
                    try:
                        btn = page.locator(selector).first
                        if await btn.count() == 0:
                            break
                        if not await btn.is_visible():
                            break

                        await btn.click(timeout=PAGINATION_CLICK_TIMEOUT_MS)
                        clicks += 1
                        print(
                            f"  [IR] Clicked pagination '{selector}' (#{clicks})",
                            flush=True,
                        )
                        await asyncio.sleep(1.5)
                    except PlaywrightTimeout:
                        break
                    except Exception:
                        break

                if clicks > 0:
                    break  # found working pagination selector

        if clicks > 0:
            print(
                f"  [IR] Pagination: {clicks} page(s) loaded",
                flush=True,
            )

    # ------------------------------------------------------------------
    # Phase 2: LLM fallback
    # ------------------------------------------------------------------

    async def _extract_links_llm(
        self,
        page: Page,
        llm_provider,
    ) -> list[dict]:
        """Send cleaned page HTML to an LLM to identify report PDF links.

        Args:
            page: current Playwright page
            llm_provider: callable(prompt: str) -> str
        """
        try:
            # Get page HTML, truncate to avoid token limits
            html = await page.content()
            # Strip scripts and style tags to reduce noise
            html = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
            html = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
            # Collapse whitespace
            html = re.sub(r"\s+", " ", html)
            # Truncate to ~30k chars
            html = html[:30_000]

            prompt = (
                "You are an expert web scraper. Below is the HTML of a company's "
                "Investor Relations page. Extract ALL links to financial report PDFs "
                "(annual reports, quarterly reports, financial statements, 10-K, 10-Q, "
                "20-F, 6-K, etc.).\n\n"
                "For each link, return one line in this exact format:\n"
                "URL | LINK_TEXT\n\n"
                "Only include links to actual financial report documents (PDFs or "
                "direct download links). Do NOT include press releases, presentations, "
                "or non-financial documents.\n\n"
                f"HTML:\n{html}"
            )

            response = llm_provider(prompt)
            if not response:
                return []

            links = []
            for line in response.strip().split("\n"):
                line = line.strip()
                if not line or "|" not in line:
                    continue
                parts = line.split("|", 1)
                url = parts[0].strip()
                text = parts[1].strip() if len(parts) > 1 else ""

                if not url.startswith("http"):
                    url = urljoin(self.ir_url, url)

                links.append({
                    "url": url,
                    "text": text,
                    "title": "",
                    "match_source": "llm",
                    "score": 8,  # high base score for LLM picks
                })

            return links

        except Exception as e:
            print(f"  [IR] LLM fallback error: {e}", flush=True)
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _wait_for_ready(self, page: Page) -> None:
        """Wait for the profile's wait_selector, tolerating timeouts."""
        if not self.profile.wait_selector:
            await asyncio.sleep(1)
            return

        try:
            await page.wait_for_selector(
                self.profile.wait_selector,
                timeout=SELECTOR_WAIT_TIMEOUT_MS,
            )
        except PlaywrightTimeout:
            print(
                f"  [IR] wait_selector '{self.profile.wait_selector}' timed out, "
                f"continuing anyway",
                flush=True,
            )
        # Extra settle time for JS-rendered content
        await asyncio.sleep(1)

    @staticmethod
    def _deduplicate_links(links: list[dict]) -> list[dict]:
        """Remove duplicate links by normalized URL, keeping highest-scored."""
        seen: dict[str, dict] = {}
        for link in links:
            url = link.get("url", "")
            # Normalize: strip trailing slashes, fragment, query params for dedup key
            normalized = url.split("#")[0].split("?")[0].rstrip("/").lower()
            if normalized not in seen or link.get("score", 0) > seen[normalized].get("score", 0):
                seen[normalized] = link
        deduped = list(seen.values())
        if len(deduped) < len(links):
            print(
                f"  [IR] Deduplicated {len(links)} -> {len(deduped)} links",
                flush=True,
            )
        return deduped

    @staticmethod
    def _merge_links(existing: list[dict], new_links: list[dict]) -> list[dict]:
        """Merge two link lists, deduplicating by URL."""
        combined = list(existing)
        existing_urls = {l.get("url", "").lower() for l in existing}
        for link in new_links:
            if link.get("url", "").lower() not in existing_urls:
                combined.append(link)
        return combined

    def _build_report_metadata(self, link_info: dict) -> Optional[ReportMetadata]:
        """Convert a scored link dict into a ReportMetadata object."""
        url = link_info.get("url", "")
        if not url:
            return None

        text = link_info.get("text", "")
        title = link_info.get("title", "")
        combined = f"{text} {title} {url}"

        year = self.extract_year(combined, url)
        period = self.extract_period(combined)

        # Determine if it looks like a financial report
        is_financial = False
        combined_lower = combined.lower()
        for kw in FINANCIAL_KEYWORDS:
            if kw.lower() in combined_lower:
                is_financial = True
                break

        # If it's a PDF link and scored well, assume financial if score >= 10
        if not is_financial and link_info.get("score", 0) >= 10:
            is_financial = True

        # Build a stable report_id from the URL
        url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
        report_id = f"ir_{url_hash}"

        description = text if text else title
        if not description:
            # Use filename from URL
            path = urlparse(url).path
            description = path.split("/")[-1] if "/" in path else path

        return ReportMetadata(
            company_slug=self.company_slug,
            company_name=self.company_name,
            year=year,
            period=period,
            url=url,
            source="IR_Website",
            file_type="pdf" if ".pdf" in url.lower() else "html",
            description=description,
            report_id=report_id,
            is_financial=is_financial,
        )

    async def download_report(
        self, report: ReportMetadata, output_dir: str
    ) -> str:
        """Download a report PDF. Returns the local file path or empty string."""
        import os

        os.makedirs(output_dir, exist_ok=True)

        base_name = f"{report.year}_{report.period}_{report.report_id}"
        local_path = os.path.join(output_dir, f"{base_name}.pdf")

        if os.path.exists(local_path) and self.validate_pdf(local_path):
            print(
                f"  [IR] Already downloaded: {os.path.basename(local_path)}",
                flush=True,
            )
            report.local_path = local_path
            report.local_paths = [local_path]
            return local_path

        print(
            f"  [IR] Downloading {report.year} {report.period}: {report.url}",
            flush=True,
        )

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"],
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                )
                page = await context.new_page()

                try:
                    # If it's a direct PDF URL, navigate and capture download
                    if ".pdf" in report.url.lower():
                        try:
                            async with page.expect_download(
                                timeout=60_000
                            ) as download_info:
                                await page.goto(
                                    report.url,
                                    wait_until="domcontentloaded",
                                    timeout=30_000,
                                )
                            download = await download_info.value
                            await download.save_as(local_path)
                        except Exception:
                            # Fallback: use response body directly
                            response = await page.goto(
                                report.url,
                                wait_until="domcontentloaded",
                                timeout=30_000,
                            )
                            if response and response.ok:
                                body = await response.body()
                                with open(local_path, "wb") as f:
                                    f.write(body)
                    else:
                        # Non-PDF URL: just fetch the response
                        response = await page.goto(
                            report.url,
                            wait_until="domcontentloaded",
                            timeout=30_000,
                        )
                        if response and response.ok:
                            body = await response.body()
                            with open(local_path, "wb") as f:
                                f.write(body)
                finally:
                    try:
                        await asyncio.wait_for(browser.close(), timeout=10)
                    except Exception:
                        pass

        except Exception as e:
            print(f"  [IR] Download error: {e}", flush=True)
            return ""

        if os.path.exists(local_path) and self.validate_pdf(local_path):
            report.local_path = local_path
            report.local_paths = [local_path]
            print(
                f"  [IR] Saved: {os.path.basename(local_path)}",
                flush=True,
            )
            return local_path

        # Clean up invalid file
        if os.path.exists(local_path):
            print(
                f"  [IR] Downloaded file failed validation, removing: {local_path}",
                flush=True,
            )
            os.remove(local_path)

        return ""
