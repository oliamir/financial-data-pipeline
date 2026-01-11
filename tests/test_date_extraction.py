#!/usr/bin/env python3
"""Test date extraction from Advanced Search results."""

import asyncio
import re
from playwright.async_api import async_playwright

async def test_date_extraction():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Navigate to search
        await page.goto("https://maya.tase.co.il/he", wait_until="domcontentloaded")
        await asyncio.sleep(1)
        await page.goto("https://maya.tase.co.il/he/reports/search", wait_until="networkidle")
        
        # Fill search
        await page.fill('input[placeholder="טקסט חופשי"]', "אפולו פאוור")
        
        from_input = page.locator('input[placeholder="מתאריך"]')
        await from_input.click()
        await from_input.type("01/01/2021", delay=100)
        await from_input.press("Enter")
        
        to_input = page.locator('input[placeholder="עד תאריך"]')
        await to_input.click()
        await to_input.type("31/12/2023", delay=100)
        await to_input.press("Enter")
        
        await page.click("button.panel-filter-bt")
        await asyncio.sleep(3)
        
        # Extract first 10 items with dates
        await page.wait_for_selector(".feed-item-report", timeout=10000)
        
        items = page.locator(".feed-item-report")
        count = await items.count()
        print(f"Found {count} items for 2021-2023 filter\n")
        
        for i in range(min(10, count)):
            item = items.nth(i)
            link = item.locator("a.feed-text-link").first
            title = await link.text_content()
            
            date_elem = item.locator(".feed-date").first
            date_text = await date_elem.text_content() if await date_elem.count() else "N/A"
            
            # Test date parsing
            clean_date = re.sub(r'[^\d/.-]', '', date_text)
            clean_date = clean_date.replace('.', '/').replace('-', '/')
            
            year = 2024  # default
            if '/' in clean_date:
                parts = clean_date.split('/')
                if len(parts) >= 3:
                    y_part = parts[2]
                    if len(y_part) == 4:
                        year = int(y_part)
                    elif len(y_part) == 2:
                        year = 2000 + int(y_part)
            
            print(f"Item {i}:")
            print(f"  Title: {title[:60]}...")
            print(f"  Raw Date: '{date_text}'")
            print(f"  Clean Date: '{clean_date}'")
            print(f"  Extracted Year: {year}\n")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_date_extraction())
