import asyncio
from playwright.async_api import async_playwright

async def inspect_search_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Intercept and print JSON requests
        page.on("request", lambda request: print(f">> {request.method} {request.url} \n   Payload: {request.post_data}") if "api" in request.url and "reports" in request.url else None)

        # Navigate to Homepage 
        url = "https://maya.tase.co.il/he" 
        print(f"Navigating to: {url}")
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(8) # Generous wait for Angular
        
        print("Scanning for search triggers...")
        elements = await page.evaluate("""() => {
            const items = [];
            // Look for generic search icons
            const candidates = document.querySelectorAll('*');
            candidates.forEach(el => {
                const cls = (el.className || '').toString();
                if (cls.includes('search') || cls.includes('magnify')) {
                    items.push({tag: el.tagName, class: cls, text: el.innerText});
                }
            });
            return items;
        }""")
        
        for item in elements:
            print(f"Candidate: {item}")

        await asyncio.sleep(5)
        print(f"Current URL: {page.url}")
        
        # Take a screenshot to see what it looks like
        await page.screenshot(path="debug_search_page.png")
        print("Saved debug_search_page.png")
        
        # Save HTML
        with open("debug_search_page.html", "w") as f:
            f.write(await page.content())
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_search_page())
