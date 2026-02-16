"""
TASE Maya Playwright scraper - adapted from the existing tase_playwright_scraper.py.
Handles JavaScript-rendered content with headless Chromium.
"""
import re
import os
import asyncio
import time
from typing import List
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from .base import BaseScraper
from ..models.report import ReportMetadata
from ..storage import paths

# Overall timeout for the entire fetch_reports operation (seconds)
OVERALL_TIMEOUT_SECONDS = 120
# Per-page Playwright navigation timeout (ms)
PAGE_GOTO_TIMEOUT_MS = 25000
# Per-page selector wait timeout (ms)
SELECTOR_TIMEOUT_MS = 8000
# Per-item extraction timeout (seconds) - for individual DOM element reads
ITEM_TIMEOUT_SECONDS = 5
# Maximum pages to scrape (~1 year of data)
MAX_PAGES = 15


class TaseScraper(BaseScraper):
    MAYA_BASE_URL = "https://maya.tase.co.il"

    def __init__(self, company_slug: str, company_name: str, tase_id: str):
        super().__init__(company_slug, company_name)
        self.tase_id = tase_id

    async def fetch_reports(self, years_back: int = 5, company_id: str = None) -> List[ReportMetadata]:
        if not company_id:
            print(f"  [TASE] Warning: company_id not provided for {self.company_name}", flush=True)
            return []

        # Overall hard timeout for the entire scraping operation
        start_time = time.monotonic()

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-http2"],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1280},
            )
            # Set default navigation and action timeouts on the context
            context.set_default_navigation_timeout(PAGE_GOTO_TIMEOUT_MS)
            context.set_default_timeout(SELECTOR_TIMEOUT_MS)

            page = await context.new_page()

            try:
                raw_reports = await self._fetch_pages(page, company_id, years_back, start_time)
            finally:
                # Force-close browser even if Playwright is stuck
                try:
                    await asyncio.wait_for(browser.close(), timeout=10)
                except Exception:
                    print(f"  [TASE] Warning: browser.close() timed out, killing process", flush=True)

            return self._process_reports(raw_reports)

    async def _fetch_pages(self, page, company_id: str, years_back: int, start_time: float) -> list:
        """Paginate through TASE company feed."""
        reports = []
        cutoff = datetime.now() - timedelta(days=365 * years_back)
        from_date = cutoff.strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")
        page_num = 1

        print(f"  [TASE] Fetching reports {from_date} to {to_date} (max {MAX_PAGES} pages, {OVERALL_TIMEOUT_SECONDS}s overall timeout)...", flush=True)

        while page_num <= MAX_PAGES:
            # Check overall timeout
            elapsed = time.monotonic() - start_time
            if elapsed > OVERALL_TIMEOUT_SECONDS:
                print(f"  [TASE] Overall timeout reached ({elapsed:.0f}s), stopping after {page_num - 1} pages", flush=True)
                break

            url = (
                f"https://maya.tase.co.il/he/reports/companies?"
                f"fromDate={from_date}&toDate={to_date}&"
                f"isPriority=false&isTradeHalt=false&"
                f"by=company&companyId={company_id}&pageNumber={page_num}"
            )

            try:
                page_items = await self._fetch_single_page(page, url, page_num)

                if not page_items:
                    print(f"  [TASE] No reports on page {page_num}", flush=True)
                    break

                reports.extend(page_items)
                print(f"  [TASE] Page {page_num}: got {len(page_items)} items (total: {len(reports)}, elapsed: {time.monotonic() - start_time:.0f}s)", flush=True)

                # Check if we've gone past cutoff
                oldest = self._get_oldest_date(page_items)
                if oldest and oldest < cutoff:
                    print(f"  [TASE] Reached cutoff date", flush=True)
                    break

                page_num += 1
                await asyncio.sleep(0.5)

            except PlaywrightTimeout:
                print(f"  [TASE] Page {page_num} Playwright timeout, stopping pagination", flush=True)
                break
            except asyncio.TimeoutError:
                print(f"  [TASE] Page {page_num} asyncio timeout, stopping pagination", flush=True)
                break
            except Exception as e:
                print(f"  [TASE] Error on page {page_num}: {type(e).__name__}: {e}", flush=True)
                break

        print(f"  [TASE] Found {len(reports)} raw reports across {page_num} pages", flush=True)
        return reports

    async def _fetch_single_page(self, page, url: str, page_num: int) -> list:
        """Fetch and extract reports from a single page.

        Uses Playwright's own timeout mechanisms (not asyncio.wait_for)
        so that timeouts actually cancel the underlying browser operations.
        """
        print(f"  [TASE] Loading page {page_num}...", flush=True)

        # Use Playwright timeout directly - this actually cancels the navigation
        await page.goto(url, timeout=PAGE_GOTO_TIMEOUT_MS, wait_until="domcontentloaded")

        # Short sleep for JS rendering, but not too long
        await asyncio.sleep(2)

        # Wait for content with Playwright timeout (not asyncio)
        try:
            await page.wait_for_selector('a[href*="reports/details"]', timeout=SELECTOR_TIMEOUT_MS)
        except PlaywrightTimeout:
            print(f"  [TASE] Page {page_num}: link selector timeout, trying fallback...", flush=True)
            try:
                await page.wait_for_selector('.feed-item-report', timeout=4000)
            except PlaywrightTimeout:
                print(f"  [TASE] Page {page_num}: no feed items found", flush=True)
                return []

        return await self._extract_from_page(page, page_num)

    async def _extract_from_page(self, page, page_num: int = 0) -> list:
        """Extract report items from current page.

        Each individual item extraction is wrapped in a try/except with
        a per-item timeout so one stuck element cannot hang the whole page.
        """
        items = []
        try:
            feed_items = page.locator(".feed-item-report")
            count = await feed_items.count()
        except Exception as e:
            print(f"  [TASE] Page {page_num}: failed to count feed items: {e}", flush=True)
            return []

        print(f"  [TASE] Page {page_num}: extracting from {count} feed items", flush=True)

        for i in range(count):
            try:
                item_data = await asyncio.wait_for(
                    self._extract_single_item(feed_items.nth(i)),
                    timeout=ITEM_TIMEOUT_SECONDS,
                )
                if item_data:
                    items.append(item_data)
            except asyncio.TimeoutError:
                print(f"  [TASE] Page {page_num}, item {i}: extraction timed out, skipping", flush=True)
                continue
            except Exception as e:
                print(f"  [TASE] Page {page_num}, item {i}: extraction error: {type(e).__name__}: {e}", flush=True)
                continue

        return items

    async def _extract_single_item(self, item) -> dict | None:
        """Extract data from a single feed item element. Returns dict or None."""
        link = item.locator("a.feed-text-link").first
        href = await link.get_attribute("href")
        if not href:
            return None

        title = (await link.text_content()) or ""
        date_elem = item.locator(".feed-date").first
        date_text = ""
        try:
            if await date_elem.count() > 0:
                date_text = (await date_elem.text_content()) or ""
        except Exception:
            pass

        match = re.search(r"(?:companies|details|reports)/(\d+)", href)
        rid = match.group(1) if match else "unknown"

        # Detect financial reports
        is_financial = False
        if "eventsFamilyIds=100" in href or "family=100" in href:
            is_financial = True

        keywords = [
            "דוח כספי", "Financial Report", "Annual Report",
            "Quarterly Report", "דוח רבעון", "דוח תקופתי", "דוח שנתי",
        ]
        if any(kw in title for kw in keywords):
            is_financial = True

        full_url = f"https://maya.tase.co.il{href}" if href.startswith("/") else href

        return {
            "id": rid,
            "title": title.strip(),
            "date": date_text.strip(),
            "url": full_url,
            "is_financial": is_financial,
        }

    def _get_oldest_date(self, items: list) -> datetime | None:
        for item in items:
            date_str = item.get("date", "")
            try:
                if "/" in date_str:
                    parts = date_str.split("/")
                    if len(parts) >= 3:
                        return datetime(int(parts[2]), int(parts[1]), int(parts[0]))
            except:
                pass
        return None

    def _process_reports(self, raw_reports: list) -> List[ReportMetadata]:
        """Convert raw items into ReportMetadata objects."""
        reports = []
        seen_ids = set()

        for item in raw_reports:
            rid = item.get("id")
            if not rid or rid in seen_ids:
                continue
            seen_ids.add(rid)

            title = item.get("title", "")
            date_str = item.get("date", "")

            # Extract year
            year = self.extract_year(title + " " + date_str)
            # Try from date (DD/MM/YYYY)
            try:
                parts = date_str.replace(".", "/").replace("-", "/").split("/")
                if len(parts) >= 3:
                    y = parts[2]
                    if len(y) == 4:
                        year = int(y)
            except:
                pass

            period = self.extract_period(title)
            is_financial = item.get("is_financial", False)
            if is_financial and "FINANCIAL" not in period:
                period += "_FINANCIAL"

            report = ReportMetadata(
                company_slug=self.company_slug,
                company_name=self.company_name,
                year=year,
                period=period,
                url=item.get("url", f"https://maya.tase.co.il/reports/details/{rid}"),
                source="TASE_Maya",
                description=title,
                report_id=rid,
                is_financial=is_financial,
            )
            reports.append(report)

        print(f"  [TASE] Processed {len(reports)} unique reports")
        return reports

    async def download_report(self, report: ReportMetadata, output_dir: str) -> str:
        """Download a report using Playwright. Returns local file path."""
        os.makedirs(output_dir, exist_ok=True)

        base_name = f"{report.year}_{report.period}_{report.report_id}"
        local_path = os.path.join(output_dir, f"{base_name}.pdf")

        if os.path.exists(local_path) and self.validate_pdf(local_path):
            print(f"  [TASE] Already downloaded: {os.path.basename(local_path)}")
            report.local_path = local_path
            report.local_paths = [local_path]
            return local_path

        print(f"  [TASE] Downloading {report.year} {report.period} (ID: {report.report_id})...")

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-http2"],
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    viewport={"width": 1920, "height": 1080},
                )
                page = await context.new_page()

                try:
                    async with page.expect_download(timeout=60000) as download_info:
                        try:
                            await page.goto(report.url, wait_until="domcontentloaded", timeout=30000)
                        except:
                            pass

                    download = await download_info.value
                    await download.save_as(local_path)
                    print(f"  [TASE] Saved: {local_path}")

                except Exception as e:
                    # Fallback: navigate to details page and find PDF button
                    print(f"  [TASE] Direct download failed, trying details page fallback...")
                    details_url = f"https://maya.tase.co.il/reports/details/{report.report_id}"

                    try:
                        await page.goto(details_url, wait_until="domcontentloaded", timeout=45000)
                        await asyncio.sleep(3)

                        # Try various PDF button selectors
                        selectors = [
                            "a[href*='attachmentType=pdf']",
                            ".icon-pdf",
                            "a[href$='.pdf']",
                        ]
                        for selector in selectors:
                            btn = page.locator(selector).first
                            if await btn.count() > 0:
                                async with page.expect_download(timeout=60000) as dl:
                                    if await btn.is_visible():
                                        await btn.click()
                                    else:
                                        await btn.evaluate("e => e.click()")
                                download = await dl.value
                                await download.save_as(local_path)
                                print(f"  [TASE] Saved via fallback: {local_path}")
                                break

                        # Hebrew text button as last resort
                        if not os.path.exists(local_path):
                            text_btn = page.get_by_text("פתיחת קובץ").first
                            if await text_btn.count() > 0:
                                async with page.expect_download(timeout=60000) as dl:
                                    await text_btn.click()
                                download = await dl.value
                                await download.save_as(local_path)
                                print(f"  [TASE] Saved via Hebrew button: {local_path}")

                    except Exception as e2:
                        print(f"  [TASE] Fallback failed: {e2}")

                finally:
                    await browser.close()

        except Exception as e:
            print(f"  [TASE] Download error: {e}")
            return ""

        if os.path.exists(local_path) and self.validate_pdf(local_path):
            report.local_path = local_path
            report.local_paths = [local_path]
            return local_path

        return ""
