#!/usr/bin/env python3
"""Test different date input methods for Angular datepicker."""

import asyncio
from playwright.async_api import async_playwright

async def test_date_methods():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Visible for debugging
        page = await browser.new_page()
        
        await page.goto("https://maya.tase.co.il/he", wait_until="domcontentloaded")
        await asyncio.sleep(1)
        await page.goto("https://maya.tase.co.il/he/reports/search", wait_until="networkidle")
        
        # Fill company name
        await page.fill('input[placeholder="טקסט חופשי"]', "אפולו פאוור")
        
        print("Testing date input methods...")
        
        # Method 1: Direct fill (current implementation)
        print("\n1. Testing direct fill...")
        from_input = page.locator('input[placeholder="מתאריך"]')
        await from_input.fill("01/01/2021")
        value1 = await from_input.input_value()
        print(f"   After fill: '{value1}'")
        
        # Method 2: Focus + keyboard
        print("\n2. Testing focus + keyboard...")
        await from_input.focus()
        await page.keyboard.press("Control+A")
        await page.keyboard.type("01012021", delay=100)
        value2 = await from_input.input_value()
        print(f"   After keyboard: '{value2}'")
        
        # Method 3: Clear + type + blur
        print("\n3. Testing clear + type + blur...")
        await from_input.clear()
        await from_input.type("01/01/2021", delay=100)
        await page.keyboard.press("Tab")  # Blur to trigger validation
        await asyncio.sleep(1)
        value3 = await from_input.input_value()
        print(f"   After type+blur: '{value3}'")
        
        # Now test if filter actually works
        print("\n4. Testing filter with 2021 dates...")
        await from_input.clear()
        await from_input.type("01/01/2021", delay=50)
        await page.keyboard.press("Tab")
        
        to_input = page.locator('input[placeholder="עד תאריך"]')
        await to_input.clear()
        await to_input.type("31/12/2021", delay=50)
        await page.keyboard.press("Tab")
        
        await asyncio.sleep(2)
        
        # Check actual input values before clicking filter
        from_val = await from_input.input_value()
        to_val = await to_input.input_value()
        print(f"   From date value: '{from_val}'")
        print(f"   To date value: '{to_val}'")
        
        # Click filter
        await page.click("button.panel-filter-bt")
        await asyncio.sleep(4)
        
        # Check first result
        try:
            await page.wait_for_selector(".feed-item-report", timeout=10000)
            first_date = await page.locator(".feed-date").first.text_content()
            print(f"   First result date: '{first_date}'")
        except Exception as e:
            print(f"   No results: {e}")
        
        await asyncio.sleep(5)  # Keep browser open to inspect
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_date_methods())
