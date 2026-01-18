from typing import List
from .base_scraper import BaseScraper, ReportMetadata
import re
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import json
from datetime import datetime, timedelta
import os

class TasePlaywrightScraper(BaseScraper):
    """
    TASE Maya scraper using headless Playwright.
    Handles JavaScript-rendered content without opening visible browser.
    """
    
    MAYA_BASE_URL = "https://maya.tase.co.il"
    
    def __init__(self, company_name: str, company_id: str):
        super().__init__(company_name)
        self.company_id = company_id
    
    def fetch_report_links(self) -> List[ReportMetadata]:
        """Fetch reports using Playwright (async wrapper)"""
        return asyncio.run(self._fetch_reports_async(company_id=self.company_id))
    
    async def _fetch_reports_async(self, years_back: int = 5, company_id: str = None) -> List[ReportMetadata]:
        """Fetch report metadata by scraping company page."""
        if not company_id:
            print("  ⚠ Warning: company_id not provided, may not find reports")
            return []
        
        all_reports = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-http2']
            )
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                viewport={'width': 1920, 'height': 1280}
            )
            page = await context.new_page()
            
            try:
                # Use standard company feed pagination
                print(f"  Using standard Company Feed...")
                feed_reports = await self._fetch_reports_standard(page, company_id, years_back)
                all_reports.extend(feed_reports)

            finally:
                await browser.close()
            
            print(f"  ✓ Found {len(all_reports)} reports total")
            return self._process_page_reports(all_reports)

    async def _extract_reports_from_page(self, page):
        """Extract reports from current page view."""
        items = []
        feed_items = page.locator(".feed-item-report")
        count = await feed_items.count()
        for i in range(count):
            try:
                item = feed_items.nth(i)
                link = item.locator("a.feed-text-link").first
                href = await link.get_attribute("href")
                if not href: continue
                
                title = await link.text_content()
                date_elem = item.locator(".feed-date").first
                date_text = await date_elem.text_content() if await date_elem.count() else ""
                
                # Parse ID and Family ID
                match = re.search(r'(?:companies|details|reports)/(\d+)', href)
                rid = match.group(1) if match else "unknown"
                
                # Check for Financial Report indicators
                # Method 1: Check link href parameters or class
                # Method 2: Check subject text
                # Ideally we want to see eventsFamilyIds=100 but href might be clean
                
                is_financial = False
                if "eventsFamilyIds=100" in href or "family=100" in href:
                    is_financial = True
                
                # Fallback: Check title keywords
                # "דוח כספי", "Financial Report", "Annual Report", "Quarterly Report"
                # Add: "דוח רבעון" (Quarter Report), "דוח תקופתי" (Periodic Report), "דוח שנתי" (Annual Report)
                keywords = [
                    "דוח כספי", "Financial Report", "Annual Report", "Quarterly Report",
                    "דוח רבעון", "דוח תקופתי", "דוח שנתי"
                ]
                if any(x in title for x in keywords):
                    is_financial = True
                
                if is_financial:
                    print(f"  ★ DETECTED FINANCIAL: {title} (ID: {rid})")
                else:
                    # Debug print for first few to see what we are missing
                    if i < 3: 
                        print(f"  [Debug] Not Financial: {title} (Href: {href})")

                items.append({
                    "id": rid,
                    "title": title.strip(),
                    "date": date_text.strip(),
                    "url": f"https://maya.tase.co.il{href}" if href.startswith('/') else href,
                    "is_financial": is_financial
                })
            except: 
                pass
        return items

    async def _fetch_reports_standard(self, page, company_id, years_back):
        """Standard scraping loop using company feed with date filtering"""
        reports = []
        cutoff_date = (datetime.now() - timedelta(days=365 * years_back))
        page_num = 1
        max_pages = 1000 
        
        # Format dates for URL parameters (YYYY-MM-DD)
        from_date_str = cutoff_date.strftime("%Y-%m-%d")
        to_date_str = datetime.now().strftime("%Y-%m-%d")
        
        print(f"  Fetching reports from {from_date_str} to {to_date_str}...")
        
        while page_num <= max_pages:
            # Build URL with date parameters
            url = (f"https://maya.tase.co.il/he/reports/companies?"
                   f"fromDate={from_date_str}&"
                   f"toDate={to_date_str}&"
                   f"isPriority=false&"
                   f"isTradeHalt=false&"
                   f"by=company&"
                   f"companyId={company_id}&"
                   f"pageNumber={page_num}")
            try:
                await page.goto(url, timeout=30000, wait_until="networkidle")
                await asyncio.sleep(2)
                
                try:
                    await page.wait_for_selector('a[href*="reports/details"]', timeout=5000)
                except:
                    pass
                
                # Use shared extraction logic
                # Note: standard page has slightly different structure?
                # Actually, my new _extract_reports_from_page uses .feed-item-report
                # which is common to both Search and Company Feed!
                # Let's verify standard feed structure match.
                # Yes, standard feed items are .feed-item-report.
                
                page_items = await self._extract_reports_from_page(page)
                
                if not page_items:
                     # Attempt JS fallback specific to standard page if needed
                     # But let's rely on the shared extractor first
                     print(f"  No reports found on page {page_num} (Std Feed)")
                     break

                # Check cutoff
                oldest_date = None
                valid_items = []
                for item in page_items:
                     # Filter duplicates? Handled in process_reports
                     valid_items.append(item)
                     
                     # Date check
                     date_str = item.get('date', '')
                     try:
                        if '/' in date_str:
                            parts = date_str.split('/')
                            if len(parts) >= 3:
                                d = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
                                if not oldest_date or d < oldest_date: oldest_date = d
                                if d < cutoff_date: break
                     except: pass
                
                reports.extend(valid_items)
                
                if page_num % 5 == 0:
                    print(f"  Scanned page {page_num}, total: {len(reports)}")
                
                if oldest_date and oldest_date < cutoff_date:
                    print(f"  Reached cutoff date {oldest_date.strftime('%Y-%m-%d')}")
                    break
                
                page_num += 1
                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"  Standard feed error page {page_num}: {e}")
                break
                
        return reports

    def _process_page_reports(self, raw_reports) -> List[ReportMetadata]:
        """Process reports extracted from company pages."""
        reports = []
        for item in raw_reports:
            report_id = item.get('id')
            if not report_id:
                continue
                
            title = item.get('title', 'Unknown Report')
            date_str = item.get('date', '')
            
            # Extract year from date
            year = 2024
            # Extract year from date
            year = 2024
            try:
                # Clean date string
                clean_date = re.sub(r'[^\d/.-]', '', date_str)
                # Normalize separators
                clean_date = clean_date.replace('.', '/').replace('-', '/')
                
                if '/' in clean_date:
                    parts = clean_date.split('/')
                    # Handle DD/MM/YYYY or DD/MM/YY
                    if len(parts) >= 3:
                        y_part = parts[2]
                        if len(y_part) == 4: year = int(y_part)
                        elif len(y_part) == 2: year = 2000 + int(y_part)
            except:
                pass
            
            # Extract period
            period = self._extract_period(title)
            
            # URL
            report_url = item.get('url', f"https://maya.tase.co.il/reports/details/{report_id}")
            
            # Metadata
            is_financial = item.get('is_financial', False)
            # Add tag to period if financial
            if is_financial:
                 period += "_FINANCIAL"
                 
            metadata = ReportMetadata(
                company_name=self.company_name,
                year=year,
                period=period,
                url=report_url,
                source="TASE_Maya",
                description=title,
                file_type="pdf",
                attachments=[]
            )
            reports.append(metadata)
            
        print(f"  ✓ Processed {len(reports)} valid reports")
        return reports
    
    def _process_reports(self, raw_reports) -> List[ReportMetadata]:
        reports = []
        for item in raw_reports:
            report_id = item.get('id') or item.get('reportId')
            if not report_id:
                continue
                
            title = item.get('title') or item.get('subject') or 'Unknown Report'
            pub_date = item.get('publishDate', '')
            attachments = item.get('attachments', [])
            
            # Extract year
            year = 2024
            try:
                if pub_date:
                    year = int(pub_date[:4])
            except:
                pass
            
            # Extract period
            period = self._extract_period(title)
            
            # Base URL
            report_url = f"https://maya.tase.co.il/reports/details/{report_id}"
            
            # Metadata
            metadata = ReportMetadata(
                company_name=self.company_name,
                year=year,
                period=period,
                url=report_url,
                source="TASE_Maya",
                description=title,
                file_type="pdf",
                attachments=attachments
            )
            reports.append(metadata)
            
        print(f"  ✓ Processed {len(reports)} valid reports from TASE API")
        return reports

    def _extract_period(self, text: str) -> str:
        """Extract period from text"""
        text_lower = text.lower()
        if any(q in text_lower for q in ['q1', 'רבעון ראשון', 'רבעון 1', 'first quarter']):
            return 'Q1'
        elif any(q in text_lower for q in ['q2', 'רבעון שני', 'רבעון 2', 'second quarter']):
            return 'Q2'
        elif any(q in text_lower for q in ['q3', 'רבעון שלישי', 'רבעון 3', 'third quarter']):
            return 'Q3'
        elif any(q in text_lower for q in ['q4', 'רבעון רביעי', 'רבעון 4', 'fourth quarter']):
            return 'Q4'
        elif any(a in text_lower for a in ['annual', 'שנתי', 'yearly']):
            return 'Annual'
        return "Other"

    async def download_report(self, report: ReportMetadata, save_path: str = None, output_dir: str = None) -> str:
        """
        Download a report handling TASE's specific protections.
        Iterates through all attachments and downloads them.
        Returns the path of the *primary* file.
        """
        # Determine target directory
        target_dir = output_dir if output_dir else self.output_dir
        os.makedirs(target_dir, exist_ok=True)

        # Extract Report ID for uniqueness
        match = re.search(r'reportId=(\d+)', report.url)
        if not match:
             match = re.search(r'(?:details|companies|reports)/(\d+)', report.url)
        report_id = match.group(1) if match else "unknown"
        
        # Base filename without extension
        base_filename = f"{report.year}_{report.period}_{report.source}_{report_id}"
        
        # Prepare list of targets to download
        targets = []
        
        if report.attachments:
            for att in report.attachments:
                fname = (att.get('fileName') or '').lower()
                ext = (att.get('extension') or '').lower()
                att_id = att.get('id')
                
                # Filter for useful files (PDF, Excel, Word, etc.)
                allowed_exts = ['pdf', 'xls', 'xlsx', 'doc', 'docx', 'ppt', 'pptx', 'zip']
                is_allowed = any(e in ext for e in allowed_exts) or any(e in fname for e in allowed_exts)
                if is_allowed or 'pdf' in ext or 'pdf' in fname:
                    # Construct URL
                    match = re.search(r'reportId=(\d+)', report.url) or re.search(r'(?:details|companies|reports)/(\d+)', report.url)
                    if match:
                        rid = match.group(1)
                        d_url = f"https://maya.tase.co.il/reports/download?reportId={rid}&attachmentId={att_id}"
                        # Unique suffix with extension
                        clean_ext = ext.replace('.', '')
                        suffix = f"_{att_id}.{clean_ext}"
                        targets.append((d_url, suffix))
        
        # If no specific attachments found, or if we want to try the main URL too?
        # Typically the main URL downloads the "main" attachment if valid.
        # Let's fallback to report.url if no PDF attachments found.
        if not targets:
            targets.append((report.url, ".pdf"))

        # Optimization: Check if all files exist to avoid launching browser
        all_exist = True
        existing_paths = []
        preview_primary = ""
        
        for i, (url, suffix) in enumerate(targets):
            file_name = f"{base_filename}{suffix}"
            local_path = os.path.join(target_dir, file_name)
            if i == 0: preview_primary = local_path
            
            if os.path.exists(local_path):
                existing_paths.append(local_path)
            else:
                all_exist = False
                
        if all_exist and targets:
            print(f"  ✓ Files already exist, skipping browser launch.")
            report.local_paths = existing_paths
            report.local_path = preview_primary
            return preview_primary

        primary_path = ""
        report.local_paths = []

        async def run_download():
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-http2']
                )
                
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )
                
                # INJECT COOKIES
                if report.extra_headers and 'Cookie' in report.extra_headers:
                    cookie_str = report.extra_headers['Cookie']
                    cookies_list = []
                    for cookie in cookie_str.split('; '):
                        if '=' in cookie:
                            name, value = cookie.split('=', 1)
                            cookies_list.append({
                                'name': name,
                                'value': value,
                                'domain': 'maya.tase.co.il',
                                'path': '/'
                            })
                    if cookies_list:
                        await context.add_cookies(cookies_list)

                page = await context.new_page()
                
                nonlocal primary_path
                
                try:
                    for i, (url, suffix) in enumerate(targets):
                        # Construct local path
                        file_name = f"{base_filename}{suffix}"
                        local_path = os.path.join(target_dir, file_name)
                        
                        if i == 0: primary_path = local_path # First one is primary
                        
                        # Check exist
                        if os.path.exists(local_path):
                            print(f"  File exists: {local_path}")
                            report.local_paths.append(local_path)
                            continue
                            
                        print(f"  Downloading {i+1}/{len(targets)}: {url} ...")
                        
                        # Download via expect_download (handles redirects/blobs better than fetch)
                        try:
                            async with page.expect_download(timeout=60000) as download_info:
                                # Trigger download by navigating or clicking
                                # Since we have the URL, we can try navigating to it
                                # If it's a file, it will trigger download.
                                # If it's a page, we might need to find a button, but let's try direct nav first.
                                # Important: Some TASE links open in new tab.
                                try:
                                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                                except Exception as nav_err:
                                    # Navigation might "fail" if it becomes a download immediately
                                    pass
                                    
                            download = await download_info.value
                            await download.save_as(local_path)
                            print(f"  ✓ Saved: {local_path}")
                            report.local_paths.append(local_path)
                                
                        except Exception as e:
                            print(f"  ⚠ Failed to download {url}: {e}")
                            
                            # Fallback logic only for the MAIN report if it failed and there were no other targets
                            if len(targets) == 1 and i == 0:
                                # Try navigation fallback (Find Download Button)
                                try:
                                    print("  Fallback: Navigating to details page to find PDF button...")
                                    # Regex for details/123 or reportId=123
                                    report_id = None
                                    match = re.search(r'details/(\d+)', report.url) or re.search(r'companies/(\d+)', report.url)
                                    
                                    if match: report_id = match.group(1)
                                    else:
                                        match = re.search(r'reportId=(\d+)', report.url)
                                        if match: report_id = match.group(1)
                                    
                                    if report_id:
                                        details_url = f"https://maya.tase.co.il/reports/details/{report_id}"
                                        # Use standard goto
                                        await page.goto(details_url, wait_until="networkidle", timeout=45000)
                                        
                                        # Look for the PDF download button
                                        # Strategy 1: The 'pdf' icon link usually has a specific class or structure
                                        # Strategy 2: Link ending in .pdf
                                        
                                        # Common selector on Maya details page for main PDF:
                                        # Strategy: Look for link with attachmentType=pdf or icon-pdf class
                                        
                                        # 1. Try attachmentType=pdf parameter (most reliable)
                                        download_btn = page.locator("a[href*='attachmentType=pdf']").first
                                        
                                        if await download_btn.count() > 0:
                                            print("  Found PDF match by attachmentType")
                                        else:
                                            # 2. Try icon-pdf class
                                            download_btn = page.locator(".icon-pdf").locator("xpath=..").first
                                            if await download_btn.count() > 0:
                                                print("  Found PDF match by icon class")

                                        # If still not found, try text as last resort
                                        if await download_btn.count() == 0:
                                              download_btn = page.locator("a[href$='.pdf']").first

                                        if await download_btn.count() > 0:
                                            print("  Found PDF link, computing download...")
                                            async with page.expect_download(timeout=60000) as dl_info:
                                                # Ensure element is visible/clickable
                                                if await download_btn.is_visible():
                                                    await download_btn.click()
                                                else:
                                                     # Force click if hidden? Or try JS click
                                                     await download_btn.evaluate("e => e.click()")
                                            
                                            download = await dl_info.value
                                            await download.save_as(local_path)
                                            print(f"  ✓ Saved PDF via Button: {local_path}")
                                            report.local_paths.append(local_path)
                                        else:
                                            # Try finding by text or icon
                                            print("  ⚠ Could not find obvious PDF link. Checking for 'פתיחת קובץ'...")
                                            text_btn = page.get_by_text("פתיחת קובץ").first
                                            if await text_btn.count() > 0:
                                                async with page.expect_download(timeout=60000) as dl_info:
                                                    await text_btn.click()
                                                download = await dl_info.value
                                                await download.save_as(local_path) 
                                                print(f"  ✓ Saved PDF via Text Button: {local_path}")
                                                report.local_paths.append(local_path)
                                            else:
                                                 print("  ⚠ No download button found. Skipping PDF generation.")

                                except Exception as e2:
                                    print(f"  Fallback failed: {e2}")

                finally:
                    await browser.close()

        
        try:
            await run_download()
            
            # Ensure primary_path actually exists
            if primary_path and not os.path.exists(primary_path):
                primary_path = ""
                
            if not primary_path and report.local_paths:
                primary_path = report.local_paths[0]
                
            report.local_path = primary_path # Backward compatibility
            return primary_path
        except Exception as e:
            print(f"Download wrapper failed: {e}")
            return ""
