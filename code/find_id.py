import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("Navigating to Maya...")
        await page.goto("https://maya.tase.co.il/en", timeout=60000)
        
        # Click search button/icon if needed, or just type in the input
        # The search input usually has id="term" or similar, or class "ng-pristine..."
        # Let's target the main search input.
        
        print("Waiting for search input...")
        # Try a few selectors
        try:
            await page.wait_for_selector('input[type="search"]', timeout=10000)
            await page.fill('input[type="search"]', "Sofwave")
        except:
             # Fallback selector
             await page.wait_for_selector('.search-input', timeout=10000)
             await page.fill('.search-input', "Sofwave")

        print("Waiting for suggestions...")
        await page.wait_for_selector('.ui-menu-item', timeout=10000)
        
        # Get all links
        items = await page.query_selector_all('.ui-menu-item a')
        for item in items:
            text = await item.inner_text()
            href = await item.get_attribute('href')
            print(f"Found: {text} -> {href}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
