import asyncio
from playwright.async_api import async_playwright
import json

async def test_browser_fetch():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("Navigating to homepage to establish session...")
        await page.goto("https://maya.tase.co.il/he", wait_until="networkidle")
        await asyncio.sleep(5)
        
        # Test 1: Advanced Search API
        print("Test 1: Fetching from api/v1/reports/search...")
        result_search = await page.evaluate("""async () => {
            const payload = {
                "PageNumber": 1,
                "CompanyId": 1074,
                "DateFrom": "2021-01-01T00:00:00",
                "DateTo": "2023-12-31T23:59:59",
                "Limit": 10,
                "Sort": 2
            };
            
            try {
                const response = await fetch("https://maya.tase.co.il/api/v1/reports/search", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Maya-With": "allow"
                    },
                    body: JSON.stringify(payload)
                });
                if (response.ok) return await response.json();
                return { status: response.status, text: await response.text() };
            } catch (e) {
                return { error: e.toString() };
            }
        }""")
        
        print(f"Search API Result: {json.dumps(result_search)[:200]}...")

        if 'reports' in result_search and len(result_search['reports']) > 0:
             print("SUCCESS: Found reports via Search API!")
             print(f"First report: {result_search['reports'][0].get('publishDate')}")
        
        # Test 2: Standard Companies API with date filter injection
        print("\nTest 2: Fetching from api/v1/reports/companies (with DateFrom)...")
        result_comp = await page.evaluate("""async () => {
            const payload = {
                "pageNumber": 1,
                "companyId": 1074,
                "limit": 10,
                "dateFrom": "2021-01-01T00:00:00",
                "dateTo": "2023-12-31T23:59:59"
            };
            
            try {
                const response = await fetch("https://maya.tase.co.il/api/v1/reports/companies", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                if (response.ok) return await response.json();
                return { status: response.status, text: await response.text() };
            } catch (e) {
                return { error: e.toString() };
            }
        }""")
        
        print(f"Companies API Result: {json.dumps(result_comp)[:200]}...")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_browser_fetch())
