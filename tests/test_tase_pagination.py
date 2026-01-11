import asyncio
from playwright.async_api import async_playwright

async def test_pagination():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        


        # Intercept and modify API request
        async def handle_route(route):
            request = route.request
            if request.method == "POST" and "reports/companies" in request.url:
                try:
                    post_data = request.post_data_json
                    if post_data:
                        print(f"Original Payload: {post_data}")
                        # Inject dates for 2021-2023 verification - PascalCase, simple date
                        post_data["DateFrom"] = "2021-01-01"
                        post_data["DateTo"] = "2023-12-31"
                        print(f"Modified Payload: {post_data}")
                        
                        await route.continue_(post_data=post_data)
                        return
                except Exception as e:
                    print(f"Error modifying payload: {e}")
            
            await route.continue_()

        # Capture response
        async def log_response(response):
            if "api/v1/reports/companies" in response.url:
                try:
                    data = await response.json()
                    reports = data.get('reports', [])
                    print(f"<< Response: {len(reports)} reports found")
                except:
                    pass
        page.on("response", log_response)

        await page.route("**/api/v1/reports/companies", handle_route)

        url = "https://maya.tase.co.il/he/reports/companies?companyId=1074"
        print(f"Navigating to: {url}")
        
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(5)
        
        # Count reports
        count = await page.locator(".feed-item-report").count()
        print(f"Found {count} reports with intercepted filter")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_pagination())
