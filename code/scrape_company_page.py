#!/usr/bin/env python3
"""
Alternative TASE scraper using company page navigation.
"""

import asyncio
from playwright.async_api import async_playwright
from datetime import datetime, timedelta
import re

async def scrape_company_page(company_id: str, years_back: int = 5):
    """Scrape by navigating to company page and extracting report table."""
    
    cutoff_date = datetime.now() - timedelta(days=365 * years_back)
    print(f"Scraping TASE company page for ID: {company_id}")
    print(f"Looking for reports back to: {cutoff_date.strftime('%Y-%m-%d')}\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        try:
            # Navigate to company page
            url = f"https://maya.tase.co.il/company/{company_id}"
            print(f"Navigating to {url}...")
            await page.goto(url, timeout=60000, wait_until="networkidle")
            
            # Wait for content to load
            await asyncio.sleep(2)
            
            # Extract reports from the page
            extract_script = """
            () => {
                const reports = [];
                // Look for report tables or lists
                const rows = document.querySelectorAll('[data-test-id="report-row"], tr[data-id], .report-item');
                
                rows.forEach(row => {
                    const titleElem = row.querySelector('.report-title, [data-test-id="report-title"], td:nth-child(2)');
                    const dateElem = row.querySelector('.report-date, [data-test-id="report-date"], td:nth-child(1)');
                    const linkElem = row.querySelector('a[href*="reports"]');
                    
                    if (titleElem && linkElem) {
                        reports.push({
                            title: titleElem.textContent.trim(),
                            date: dateElem ? dateElem.textContent.trim() : '',
                            url: linkElem.href
                        });
                    }
                });
                
                return { count: reports.length, reports: reports.slice(0, 10) };
            }
            """
            
            result = await page.evaluate(extract_script)
            print(f"Found {result['count']} reports on page")
            
            if result['count'] > 0:
                print("\nSample reports:")
                for r in result['reports']:
                    print(f"  - {r['date']}: {r['title'][:60]}")
                    print(f"    {r['url']}")
            else:
                print("\n⚠ No reports found via DOM scraping")
                print("The page structure may have changed or requires different selectors")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_company_page("1082114", 5))
