import asyncio
from playwright.async_api import async_playwright

async def verify_search():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        # 1. Homepage
        print("1. Visiting Homepage...")
        await page.goto("https://maya.tase.co.il/he", wait_until="networkidle")
        await asyncio.sleep(2)
        
        # 2. Navigate to Search
        target_url = "https://maya.tase.co.il/he/reports/search"
        print(f"2. Navigating to {target_url}...")
        await page.goto(target_url, wait_until="networkidle")
        await asyncio.sleep(5)
        
        # 3. Check for specific elements
        print(f"Current URL: {page.url}")
        content = await page.content()
        
        if "The page does not exist" in content or "העמוד שחיפשת אינו קיים" in content:
            print("FAILURE: Page still 404/Soft-404")
        else:
            print("SUCCESS: Page loaded!")
            # Dump inputs
            inputs = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('input')).map(i => ({id: i.id, placeholder: i.placeholder, type: i.type}));
            }""")
            for i in inputs:
                print(f"Input: {i}")

            # Dump buttons
            buttons = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('button')).map(b => ({text: b.innerText, type: b.type, class: b.className}));
            }""")
            for b in buttons:
                print(f"Button: {b}")

        # Screenshot
        await page.screenshot(path="verify_search.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(verify_search())
