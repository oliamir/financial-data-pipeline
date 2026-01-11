#!/usr/bin/env python3
"""Test URL date parameters for historical data access."""

import asyncio
from playwright.async_api import async_playwright

async def test_url_date_params():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Test the URL with date parameters
        url = "https://maya.tase.co.il/he/reports/companies?fromDate=2021-01-01&toDate=2023-12-31&isPriority=false&isTradeHalt=false&by=company&companyId=1074"
        
        print("Testing URL with date parameters (2021-2023)...")
        print(f"URL: {url}\n")
        
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(3)
        
        # Check results
        items = page.locator(".feed-item-report")
        count = await items.count()
        
        print(f"Found {count} reports\n")
        
        if count > 0:
            # Get first 5 dates
            for i in range(min(5, count)):
                item = items.nth(i)
                date_elem = item.locator(".feed-date").first
                title_elem = item.locator("a.feed-text-link").first
                
                date_text = await date_elem.text_content()
                title_text = await title_elem.text_content()
                
                print(f"Report {i+1}:")
                print(f"  Date: {date_text.strip()}")
                print(f"  Title: {title_text[:60]}...")
                print()
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_url_date_params())
