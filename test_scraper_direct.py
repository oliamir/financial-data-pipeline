#!/usr/bin/env python3
"""Quick test to verify the updated scraper fetches historical data."""

import asyncio
import sys
sys.path.insert(0, 'src')

from scrapers.tase_playwright_scraper import TasePlaywrightScraper

async def test_historical_scraping():
    scraper = TasePlaywrightScraper("Apollo Power", "1074")
    
    print("Testing 6-year historical scraping...")
    print("="*60)
    
    reports = await scraper._fetch_reports_async(years_back=6, company_id="1074")
    
    print(f"\nTotal reports found: {len(reports)}")
    
    # Count by year
    years = {}
    for r in reports:
        y = r.year
        years[y] = years.get(y, 0) + 1
    
    print("\nBreakdown by year:")
    for year in sorted(years.keys()):
        print(f"  {year}: {years[year]} reports")

if __name__ == "__main__":
    asyncio.run(test_historical_scraping())
