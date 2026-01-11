import asyncio
from playwright.async_api import async_playwright

async def test_search_flow():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Use verified viewport/agent
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        # 1. Homepage -> Search (Session)
        await page.goto("https://maya.tase.co.il/he", wait_until="networkidle")
        await asyncio.sleep(2)
        await page.goto("https://maya.tase.co.il/he/reports/search", wait_until="networkidle")
        
        # 2. Fill Data
        print("Filling search form...")
        # Free Text: "אפולו פאוור"
        await page.fill("#formly_2_maya-input_freeText_0", "אפולו פאוור")
        
        # Dates (dd/mm/yyyy) for 2022
        # Use type and enter for Angular inputs
        await page.click("#formly_4_datepicker_fromDate_0")
        await page.fill("#formly_4_datepicker_fromDate_0", "")
        await page.type("#formly_4_datepicker_fromDate_0", "01/01/2022", delay=100)
        await page.press("#formly_4_datepicker_fromDate_0", "Enter")
        
        await page.click("#formly_4_datepicker_toDate_1")
        await page.fill("#formly_4_datepicker_toDate_1", "")
        await page.type("#formly_4_datepicker_toDate_1", "31/12/2022", delay=100)
        await page.press("#formly_4_datepicker_toDate_1", "Enter")
        
        # 3. Click Filter
        print("Clicking Filter...")
        await page.click("button.panel-filter-bt")
        
        # 4. Wait for results
        print("Waiting for results...")
        try:
            # Wait for at least one report item
            await page.wait_for_selector(".feed-item-report", timeout=15000)
            
            count = await page.locator(".feed-item-report").count()
            print(f"SUCCESS: Found {count} reports for request!")
            
            # Debug first few items
            for i in range(min(3, count)):
                item = page.locator(".feed-item-report").nth(i)
                link = item.locator("a.feed-text-link").first
                href = await link.get_attribute("href")
                
                # Date
                date_elem = item.locator(".feed-date").first
                date_text = await date_elem.text_content() if await date_elem.count() else "N/A"
                print(f"Item {i}: Date={date_text}, Href={href}")
            
            # Dump all buttons to find pagination
            print("Dumping Page Buttons:")
            buttons = page.locator("button")
            cnt = await buttons.count()
            for i in range(cnt):
                btn = buttons.nth(i)
                txt = await btn.text_content()
                aria = await btn.get_attribute("aria-label") or ""
                cls = await btn.get_attribute("class") or ""
                if await btn.is_visible():
                    print(f"  Btn {i}: Text='{txt.strip()[:20]}', Aria='{aria}', Class='{cls}'")

            
        except Exception as e:
            print(f"FAILURE: No reports found. Error: {e}")
            await page.screenshot(path="debug_search_fail.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_search_flow())
