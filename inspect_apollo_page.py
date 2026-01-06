#!/usr/bin/env python3
"""Quick test to inspect Apollo page structure."""

import asyncio
from playwright.async_api import async_playwright

async def inspect_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        url = "https://maya.tase.co.il/he/reports/companies?companyId=1074&pageNumber=1"
        print(f"Loading: {url}")
        await page.goto(url, timeout=30000, wait_until="networkidle")
        
        # Get HTML content
        content = await page.content()
        
        # Save to file
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(content)
        
        print("\nSaved page content to debug_page.html")
        
        # Try to find tables or report elements
        selectors_to_try = [
            "table",
            "tbody tr",
            "[data-test*='report']",
            ".report-row",
            "tr[data-id]",
           ".reports",
            "a[href*='details']"
        ]
        
        for selector in selectors_to_try:
            count = await page.locator(selector).count()
            print(f"  {selector}: {count} elements")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_page())
