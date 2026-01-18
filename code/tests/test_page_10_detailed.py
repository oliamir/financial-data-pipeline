#!/usr/bin/env python3
"""Test if waiting or interaction helps load page 10."""

import asyncio
from playwright.async_api import async_playwright

async def test_page_10_detailed():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Visible
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        # Start from page 1, then navigate to page 10
        print("Loading page 1 first...")
        await page.goto("https://maya.tase.co.il/he/reports/companies?companyId=1074&pageNumber=1", 
                        wait_until="networkidle")
        await asyncio.sleep(2)
        
        count_p1 = await page.locator(".feed-item-report").count()
        print(f"  Page 1: {count_p1} reports")
        
        # Now navigate to page 10
        print("\nNavigating to page 10...")
        await page.goto("https://maya.tase.co.il/he/reports/companies?companyId=1074&pageNumber=10",
                        wait_until="networkidle")
        await asyncio.sleep(3)
        
        count_p10 = await page.locator(".feed-item-report").count()
        print(f"  Page 10: {count_p10} reports")
        
        if count_p10 > 0:
            first_date = await page.locator(".feed-date").first.text_content()
            print(f"  First date: {first_date}")
        
        # Check page content for error messages
        body_text = await page.locator("body").text_content()
        if "לא נמצאו" in body_text or "no results" in body_text.lower():
            print("  Found 'no results' message in body")
        
        await asyncio.sleep(5)  # Keep browser open
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_page_10_detailed())
