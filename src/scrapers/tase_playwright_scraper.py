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
        return asyncio.run(self._fetch_reports_async())
    
    async def _fetch_reports_async(self, years_back: int = 5, company_id: str = None) -> List[ReportMetadata]:
        """
        Fetch report links from TASE Maya using page-based navigation.
        Uses the company reports page with pagination: 
        https://maya.tase.co.il/he/reports/companies?companyId={id}&pageNumber={page}
        """
        if not company_id:
            print("  ⚠ Warning: company_id not provided, may not find reports")
            return []
        
        cutoff_date = (datetime.now() - timedelta(days=365 * years_back))
        print(f"Launching headless browser for TASE (Company ID: {company_id})...")
        print(f"  Targeting reports back to {cutoff_date.strftime('%Y-%m-%d')}...")
        
        all_reports = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = await context.new_page()
            
            try:
                page_num = 1
                max_pages = 1000  # Safety limit
                
                while page_num <= max_pages:
                    url = f"https://maya.tase.co.il/he/reports/companies?companyId={company_id}&pageNumber={page_num}"
                    
                    try:
                        await page.goto(url, timeout=30000, wait_until="networkidle")
                        
                        # Give AJAX content time to load
                        await asyncio.sleep(2)
                        
                        # Try to wait for links but don't fail if they're not immediately visible
                        try:
                            await page.wait_for_selector('a[href*="reports/details"]', timeout=5000)
                        except:
                            pass  # Continue anyway to check if content loaded
                        
                        # Strategy 1 & 2: Robust Locator + JS Fallback
                        # First try getting elements via Playwright locators for better stability
                        # structure: .feed-item-report -> .feed-text -> a[href*="reports/companies"]
                        links = page.locator('a[href*="reports/companies"], a[href*="reports/details"]')
                        count = await links.count()
                        
                        reports_by_id = {}
                        
                        if count > 0:
                            for i in range(count):
                                link = links.nth(i)
                                href = await link.get_attribute('href')
                                if not href:
                                    continue
                                
                                # Match reports/companies/12345 or reports/details/12345
                                report_id_match = re.search(r'(?:companies|details)/(\d+)', href)
                                if not report_id_match:
                                    continue
                                
                                # Ensure absolute URL
                                if href.startswith('/'):
                                    href = f"{self.MAYA_BASE_URL}{href}"
                                    
                                report_id = report_id_match.group(1)
                                
                                # Determine priority: pdf > html > main
                                # We treat main as lowest unless we find no others
                                
                                if report_id not in reports_by_id:
                                    title = await link.text_content()
                                    title = title.strip() if title else 'Unknown'
                                    
                                    # Try to find date in parent container (.feed-item-report)
                                    date_text = ""
                                    try:
                                        # Locate the main feed item container
                                        item_container = link.locator('xpath=./ancestor::*[contains(@class, "feed-item-report")]').first
                                        if await item_container.count() > 0:
                                            # Find date element within this container
                                            date_elem = item_container.locator('.feed-date')
                                            if await date_elem.count() > 0:
                                                date_text = await date_elem.text_content()
                                                # Clean up "04.01.2026" from text
                                                date_match = re.search(r'(\d{1,2}[./-]\d{1,2}[./-]\d{4})', date_text)
                                                if date_match:
                                                    date_text = date_match.group(1)
                                    except Exception as e:
                                        pass
                                        
                                    reports_by_id[report_id] = {
                                        'id': report_id,
                                        'title': title,
                                        'date': date_text,
                                        'urls': []
                                    }
                                
                                # Store URL with type hint
                                type_score = 0
                                if 'attachmentType=pdf' in href: type_score = 3
                                elif 'attachmentType=htm' in href: type_score = 2
                                else: type_score = 1
                                
                                reports_by_id[report_id]['urls'].append((type_score, href))
                        
                        # Process reports_by_id into page_reports
                        page_reports = []
                        for rid, rdata in reports_by_id.items():
                            # Sort by score descending
                            rdata['urls'].sort(key=lambda x: x[0], reverse=True)
                            best_url = rdata['urls'][0][1]
                            
                            page_reports.append({
                                'id': rid,
                                'title': rdata['title'],
                                'date': rdata['date'],
                                'url': best_url
                            })
                        
                        # Fallback to JS if Python locator extraction failed or returned 0
                        if len(page_reports) == 0:
                             print("  Locator found 0 reports, trying JS fallback...")
                             # ... (keeping existing JS fallback but enhanced logic would be good too)
                             # For now, let's assume locator works as we verified it does.

                             print("  Locator found 0 reports, trying JS fallback...")
                             extract_script = """
                             () => {
                                 const reports = [];
                                 // Look for the specific link class found in analysis
                                 const links = document.querySelectorAll('a.feed-text-link, a[href*="reports/companies"], a[href*="reports/details"]');
                                 links.forEach(link => {
                                     const href = link.href;
                                     const match = href.match(/(?:companies|details)\\/(\\d+)/);
                                     if (!match) return;
                                     
                                     let container = link.closest('.feed-item-report');
                                     let dateText = '';
                                     if (container) {
                                         const dateElem = container.querySelector('.feed-date');
                                         if (dateElem) dateText = dateElem.innerText;
                                     }
                                     
                                     // Fallback date extraction
                                     const dateMatch = (dateText || container?.innerText || '').match(/(\\d{1,2}[./-]\\d{1,2}[./-]\\d{4})/);
                                     
                                     reports.push({
                                         id: match[1],
                                         title: link.innerText.trim(),
                                         date: dateMatch ? dateMatch[0] : '',
                                         url: href
                                     });
                                 });
                                 return reports;
                             }
                             """
                             page_reports = await page.evaluate(extract_script)
                        
                        if not page_reports or len(page_reports) == 0:
                            print(f"  No more reports found at page {page_num}")
                            # Debug: Capture screenshot
                            screenshot_path = f"debug_page_{page_num}.png"
                            await page.screenshot(path=screenshot_path)
                            print(f"  Saved screenshot to {screenshot_path}")
                            # Debug: Save content
                            with open(f"debug_page_{page_num}.html", "w") as f:
                                f.write(await page.content())
                            break
                        
                        # Check if we've reached the cutoff date
                        oldest_date = None
                        for report in page_reports:
                            # Parse Hebrew date format (DD/MM/YYYY or similar)
                            date_str = report.get('date', '')
                            try:
                                # Try parsing DD/MM/YYYY format
                                if '/' in date_str:
                                    parts = date_str.split('/')
                                    if len(parts) >= 3:
                                        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                                        report_date = datetime(year, month, day)
                                        
                                        if not oldest_date or report_date < oldest_date:
                                            oldest_date = report_date
                                        
                                        if report_date < cutoff_date:
                                            break
                            except:
                                pass
                        
                        all_reports.extend(page_reports)
                        
                        if page_num % 5 == 0:
                            print(f"  Scanned page {page_num}, total reports: {len(all_reports)}")
                        
                        # Check cutoff
                        if oldest_date and oldest_date < cutoff_date:
                            print(f"  Reached cutoff date at page {page_num}: {oldest_date.strftime('%Y-%m-%d')}")
                            break
                        
                        page_num += 1
                        await asyncio.sleep(0.5)  # Be polite
                        
                    except Exception as e:
                        print(f"  Error on page {page_num}: {e}")
                        break
                        
            finally:
                await browser.close()
            
            print(f"  ✓ Found {len(all_reports)} reports total")
            return self._process_page_reports(all_reports)

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
            try:
                if '/' in date_str:
                    parts = date_str.split('/')
                    if len(parts) >= 3:
                        year = int(parts[2])
            except:
                pass
            
            # Extract period
            period = self._extract_period(title)
            
            # URL
            report_url = item.get('url', f"https://maya.tase.co.il/reports/details/{report_id}")
            
            # Metadata
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
             match = re.search(r'(?:details|companies)/(\d+)', report.url)
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
                    match = re.search(r'reportId=(\d+)', report.url) or re.search(r'(?:details|companies)/(\d+)', report.url)
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

        primary_path = ""
        report.local_paths = []

        async def run_download():
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
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
                                # Try navigation fallback (Print to PDF)
                                try:
                                    print("  Fallback: Navigating to details page for PDF Print...")
                                    # Regex for details/123 or reportId=123
                                    report_id = None
                                    match = re.search(r'details/(\d+)', report.url) or re.search(r'companies/(\d+)', report.url)
                                    
                                    if match: report_id = match.group(1)
                                    else:
                                        match = re.search(r'reportId=(\d+)', report.url)
                                        if match: report_id = match.group(1)
                                    
                                    if report_id:
                                        details_url = f"https://maya.tase.co.il/reports/details/{report_id}"
                                        await page.goto(details_url, wait_until="networkidle", timeout=45000)
                                        await page.pdf(path=local_path, format="A4")
                                        if os.path.exists(local_path):
                                            print(f"  ✓ Saved PDF via Print: {local_path}")
                                            report.local_paths.append(local_path)
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
