#!/usr/bin/env python3
"""Test company-specific endpoint for historical reports."""

import asyncio
from playwright.async_api import async_playwright
import json

async def test_company_endpoint():
    company_id = "1082114"  # Apollo Power
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        try:
            await page.goto("https://maya.tase.co.il/reports/company", timeout=60000, wait_until="commit")
            
            # Test company-specific endpoint
            test_script = f"""
            async () => {{
                const companyId = "{company_id}";
                
                // Try /reports/company/{{id}} endpoint
                const url = `https://maya.tase.co.il/api/v1/reports/company/${{companyId}}`;
                
                try {{
                    const response = await fetch(url, {{
                        method: "GET",
                        headers: {{
                            "X-Maya-With": "1"
                        }}
                    }});
                    
                    if (response.ok) {{
                        const data = await response.json();
                        return {{
                            success: true,
                            totalReports: data.reports ? data.reports.length : 0,
                            dateRange: data.reports && data.reports.length > 0 ? {{
                                oldest: data.reports[data.reports.length - 1].publishDate,
                                newest: data.reports[0].publishDate
                            }} : null,
                            sampleReports: data.reports ? data.reports.slice(0, 5).map(r => ({{
                                title: r.title,
                                date: r.publishDate,
                                id: r.id
                            }})) : []
                        }};
                    }} else {{
                        return {{ success: false, error: `HTTP ${{response.status}}` }};
                    }}
                }} catch (e) {{
                    return {{ success: false, error: e.toString() }};
                }}
            }}
            """
            
            result = await page.evaluate(test_script)
            
            print("="* 70)
            print("TESTING COMPANY-SPECIFIC ENDPOINT")
            print("=" * 70)
            print(f"Endpoint: GET /api/v1/reports/company/{company_id}")
            
            if result['success']:
                print(f"\n✓ SUCCESS")
                print(f"Total Reports: {result['totalReports']}")
                if result['dateRange']:
                    print(f"Date Range: {result['dateRange']['oldest']} to {result['dateRange']['newest']}")
                print(f"\nSample Reports:")
                for r in result['sampleReports']:
                    print(f"  - {r['date']}: {r['title'][:80]}")
            else:
                print(f"\n✗ FAILED: {result['error']}")
            
            print("=" * 70)
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_company_endpoint())
