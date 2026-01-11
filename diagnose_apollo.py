#!/usr/bin/env python3
"""
Test script to diagnose TASE API for Apollo Power historical reports.
"""

import asyncio
from playwright.async_api import async_playwright
from datetime import datetime, timedelta
import json

async def test_tase_api():
    """Test TASE API to see what reports exist for Apollo Power."""
    
    target_id = "1082114"  # Apollo Power
    cutoff_date = (datetime.now() - timedelta(days=365 * 5)).isoformat()
    
    print(f"Testing TASE API for Company ID: {target_id}")
    print(f"Looking for reports back to: {cutoff_date}\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        try:
            await page.goto("https://maya.tase.co.il/reports/company", timeout=60000, wait_until="commit")
            
            # Test fetching first few pages to see what data structure we get
            test_script = f"""
            async () => {{
                const targetId = "{target_id}";
                const results = {{
                    totalScanned: 0,
                    matchesFound: 0,
                    sampleMatches: [],
                    sampleNonMatches: [],
                    dateRange: {{ oldest: null, newest: null }}
                }};
                
                // Scan first 50 pages to get a sample
                for (let page = 1; page <= 50; page++) {{
                    try {{
                        const payload = {{
                            "pageNumber": page,
                            "limit": 20,
                            "offset": (page - 1) * 20
                        }};
                        
                        const response = await fetch("https://maya.tase.co.il/api/v1/reports/companies", {{
                            method: "POST",
                            headers: {{
                                "Content-Type": "application/json",
                                "X-Maya-With": "1"
                            }},
                            body: JSON.stringify(payload)
                        }});
                        
                        if (!response.ok) break;
                        
                        const data = await response.json();
                        let items = Array.isArray(data) ? data : (data.reports || data.companies || []);
                        
                        if (!items || items.length === 0) break;
                        
                        results.totalScanned += items.length;
                        
                        // Track date range
                        items.forEach(item => {{
                            const date = new Date(item.publishDate);
                            if (!results.dateRange.oldest || date < new Date(results.dateRange.oldest)) {{
                                results.dateRange.oldest = item.publishDate;
                            }}
                            if (!results.dateRange.newest || date > new Date(results.dateRange.newest)) {{
                                results.dateRange.newest = item.publishDate;
                            }}
                        }});
                        
                        // Check for matches
                        const matches = items.filter(item => {{
                            return (item.reporterSecurityId == targetId) || (item.reporterId == targetId);
                        }});
                        
                        results.matchesFound += matches.length;
                        
                        // Save first few matches
                        if (matches.length > 0 && results.sampleMatches.length < 5) {{
                            matches.slice(0, 5 - results.sampleMatches.length).forEach(m => {{
                                results.sampleMatches.push({{
                                    title: m.title || m.subject,
                                    publishDate: m.publishDate,
                                    reporterId: m.reporterId,
                                    reporterSecurityId: m.reporterSecurityId,
                                    id: m.id || m.reportId
                                }});
                            }});
                        }}
                        
                        // Save first few non-matches for comparison
                        if (results.sampleNonMatches.length < 3) {{
                            const nonMatches = items.filter(item => {{
                                return !((item.reporterSecurityId == targetId) || (item.reporterId == targetId));
                            }});
                            nonMatches.slice(0, 3 - results.sampleNonMatches.length).forEach(m => {{
                                results.sampleNonMatches.push({{
                                    title: m.title || m.subject,
                                    publishDate: m.publishDate,
                                    reporterId: m.reporterId,
                                    reporterSecurityId: m.reporterSecurityId
                                }});
                            }});
                        }}
                        
                        if (page % 10 === 0) {{
                            console.log("Scanned " + page + " pages, found " + results.matchesFound + " matches so far");
                        }}
                        
                        await new Promise(r => setTimeout(r, 100));
                        
                    }} catch (e) {{
                        console.log("Error at page " + page + ": " + e);
                        break;
                    }}
                }}
                
                return results;
            }}
            """
            
            page.set_default_timeout(0)
            results = await page.evaluate(test_script)
            
            print("=" * 70)
            print("TASE API TEST RESULTS")
            print("=" * 70)
            print(f"Total reports scanned: {results['totalScanned']}")
            print(f"Matches found for Apollo Power (ID: {target_id}): {results['matchesFound']}")
            print(f"\nDate range of scanned reports:")
            print(f"  Oldest: {results['dateRange']['oldest']}")
            print(f"  Newest: {results['dateRange']['newest']}")
            
            print(f"\nSample Matching Reports ({len(results['sampleMatches'])}):")
            for match in results['sampleMatches']:
                print(f"  - {match['publishDate']}: {match['title'][:80]}")
                print(f"    reporterId: {match.get('reporterId')}, reporterSecurityId: {match.get('reporterSecurityId')}")
            
            print(f"\nSample NON-Matching Reports ({len(results['sampleNonMatches'])}) for comparison:")
            for non_match in results['sampleNonMatches']:
                print(f"  - {non_match['publishDate']}: {non_match['title'][:80]}")
                print(f"    reporterId: {non_match.get('reporterId')}, reporterSecurityId: {non_match.get('reporterSecurityId')}")
            
            print("\n" + "=" * 70)
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_tase_api())
