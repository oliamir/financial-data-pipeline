#!/usr/bin/env python3
"""Test accessing older years via high page numbers."""

import asyncio
from playwright.async_api import async_playwright

async def test_high_page_numbers():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Test different page numbers
        test_pages = [1, 10, 20, 30]
        
        for page_num in test_pages:
            url = f"https://maya.tase.co.il/he/reports/companies?companyId=1074&pageNumber={page_num}"
            print(f"\n{'='*60}")
            print(f"Testing Page {page_num}")
            print(f"{'='*60}")
            
            await page.goto(url, wait_until="networkidle")
            await asyncio.sleep(2)
            
            # Check if we have results
            items = page.locator(".feed-item-report")
            count = await items.count()
            
            if count == 0:
                print(f"  No results on page {page_num}")
                continue
            
            print(f"  Found {count} reports")
            
            # Get first and last dates
            first_date = await items.first.locator(".feed-date").text_content()
            last_date = await items.last.locator(".feed-date").text_content()
            
            # Get first title
            first_title = await items.first.locator("a.feed-text-link").first.text_content()
            
            print(f"  First: {first_date.strip()} - {first_title[:50]}...")
            print(f"  Last:  {last_date.strip()}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_high_page_numbers())
