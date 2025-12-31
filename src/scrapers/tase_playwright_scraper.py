from typing import List
from .base_scraper import BaseScraper, ReportMetadata
import re
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

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
    
    async def _fetch_reports_async(self) -> List[ReportMetadata]:
        """Async method to scrape TASE using headless Playwright"""
        reports = []
        
        try:
            async with async_playwright() as p:
                print(f"Launching headless browser for TASE (Company ID: {self.company_id})...")
                
                # Launch browser in headless mode (no visible window)
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )
                
                page = await context.new_page()
                
                # Try multiple URL patterns for TASE Maya
                urls_to_try = [
                    f"{self.MAYA_BASE_URL}/company/{self.company_id}",
                    f"{self.MAYA_BASE_URL}/reports/company/{self.company_id}",
                    f"{self.MAYA_BASE_URL}/bursa/company/{self.company_id}"
                ]
                
                page_loaded = False
                for url in urls_to_try:
                    try:
                        print(f"  Trying URL: {url}")
                        await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                        await asyncio.sleep(2)  # Wait for dynamic content
                        
                        # Check if page has content
                        content = await page.content()
                        if len(content) > 1000:  # Reasonable page size
                            page_loaded = True
                            print(f"  ✓ Successfully loaded page")
                            break
                    except PlaywrightTimeout:
                        print(f"  ✗ Timeout on {url}")
                        continue
                
                if not page_loaded:
                    print("  Could not load any TASE Maya page")
                    await browser.close()
                    return []
                
                # Look for report links using multiple strategies
                
                # Strategy 1: Look for PDF links
                pdf_links = await page.query_selector_all('a[href*=".pdf"]')
                print(f"  Found {len(pdf_links)} PDF links")
                
                # Strategy 2: Look for report table rows
                report_rows = await page.query_selector_all('tr, .report-row, [class*="report"]')
                print(f"  Found {len(report_rows)} potential report rows")
                
                # Strategy 3: Get all links and filter
                all_links = await page.query_selector_all('a')
                print(f"  Found {len(all_links)} total links")
                
                # Process links
                processed_urls = set()
                
                for link in all_links:
                    try:
                        href = await link.get_attribute('href')
                        text = await link.inner_text()
                        
                        if not href or not text:
                            continue
                        
                        # Skip if already processed
                        if href in processed_urls:
                            continue
                        
                        # Check if it's a financial report
                        text_lower = text.lower().strip()
                        href_lower = href.lower()
                        
                        # Look for financial report keywords (Hebrew and English)
                        is_financial = any(keyword in text_lower or keyword in href_lower for keyword in [
                            'financial', 'דוח כספי', 'quarterly', 'רבעון', 
                            'annual', 'שנתי', 'periodic', 'תקופתי',
                            'q1', 'q2', 'q3', 'q4', 'earnings'
                        ])
                        
                        if not is_financial:
                            continue
                        
                        # Extract year
                        year_match = re.search(r'20(2[0-5]|1[0-9])', text + ' ' + href)
                        year = int(year_match.group(0)) if year_match else 2024
                        
                        # Extract period
                        period = self._extract_period(text)
                        
                        if period != "Other":
                            # Make URL absolute
                            if href.startswith('http'):
                                full_url = href
                            elif href.startswith('/'):
                                full_url = f"{self.MAYA_BASE_URL}{href}"
                            else:
                                full_url = f"{self.MAYA_BASE_URL}/{href}"
                            
                            # Avoid duplicates
                            if full_url not in processed_urls:
                                processed_urls.add(full_url)
                                reports.append(ReportMetadata(
                                    company_name=self.company_name,
                                    year=year,
                                    period=period,
                                    url=full_url,
                                    source="TASE_Maya",
                                    file_type="pdf"
                                ))
                                print(f"  Found: {year} {period} - {text[:50]}")
                    
                    except Exception as e:
                        continue  # Skip problematic links
                
                await browser.close()
                print(f"  ✓ Headless scraping complete")
                
        except Exception as e:
            print(f"Error with Playwright scraping: {e}")
            import traceback
            traceback.print_exc()
        
        return reports
    
    def _extract_period(self, text: str) -> str:
        """Extract period from text"""
        text_lower = text.lower()
        
        # Quarterly patterns
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
