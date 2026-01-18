#!/usr/bin/env python3
"""
Intercept actual TASE website requests to find correct API for historical data.
"""

import asyncio
from playwright.async_api import async_playwright
import json

async def intercept_tase():
    company_id = "1082114"  # Apollo Power
    
    captured_requests = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        # Capture API requests
        async def handle_request(request):
            if "api" in request.url and "maya.tase.co.il" in request.url:
                captured_requests.append({
                    'url': request.url,
                    'method': request.method,
                    'post_data': request.post_data
                })
        
        page.on("request", handle_request)
        
        try:
            print(f"Navigating to Apollo Power company page...")
            # Navigate to the company page
            await page.goto(f"https://maya.tase.co.il/company/{company_id}", timeout=60000, wait_until="networkidle")
            
            # Wait a moment for any additional requests
            await asyncio.sleep(3)
            
            print(f"\n{'='*70}")
            print(f"CAPTURED API REQUESTS")
            print(f"{'='*70}\n")
            
            for i, req in enumerate(captured_requests, 1):
                print(f"{i}. {req['method']} {req['url']}")
                if req['post_data']:
                    try:
                        data = json.loads(req['post_data'])
                        print(f"   Payload: {json.dumps(data, indent=2)}")
                    except:
                        print(f"   Payload: {req['post_data'][:200]}")
                print()
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(intercept_tase())
