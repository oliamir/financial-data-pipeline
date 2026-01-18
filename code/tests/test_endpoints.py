#!/usr/bin/env python3
"""Test company reports endpoints."""

import asyncio
from playwright.async_api import async_playwright

async def test_endpoints():
    company_id = "1082114"
    
    endpoints_to_test = [
        f"https://maya.tase.co.il/api/v1/companies/{company_id}/reports",
        f"https://maya.tase.co.il/api/v1/companies/{company_id}/details", 
        f"https://maya.tase.co.il/api/v1/companies/{company_id}/disclosures",
    ]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        await page.goto("https://maya.tase.co.il/reports/company", timeout=60000, wait_until="commit")
        
        for endpoint in endpoints_to_test:
            test_script = f"""
            async () => {{
                try {{
                    const response = await fetch("{endpoint}", {{
                        headers: {{ "X-Maya-With": "1" }}
                    }});
                    
                    if (response.ok) {{
                        const data = await response.json();
                        const keys = Object.keys(data);
                        const hasReports = data.reports || data.disclosures || data.items;
                        return {{
                            status: response.status,
                            success: true,
                            keys: keys,
                            reportCount: hasReports ? (hasReports.length || 0) : 0,
                            sample: hasReports ? hasReports.slice(0, 2) : null
                        }};
                    }} else {{
                        return {{ status: response.status, success: false }};
                    }}
                }} catch (e) {{
                    return {{ error: e.toString(), success: false }};
                }}
            }}
            """
            
            result = await page.evaluate(test_script)
            print(f"\n{endpoint}")
            print(f"  Status: {result.get('status', 'ERROR')}")
            if result.get('success'):
                print(f"  Keys: {result.get('keys')}")
                print(f"  Report Count: {result.get('reportCount')}")
            else:
                print(f"  Error: {result.get('error', 'Failed')}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_endpoints())
