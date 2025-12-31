from scrapers.base_scraper import ReportMetadata
from scrapers.enlight_scraper import EnlightScraper
from scrapers.tase_scraper import TaseScraper
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

def main():
    company_name = "Enlight_Renewable_Energy"
    
    print("="*70)
    print("FINANCIAL DATA SCRAPER - DEMO")
    print("="*70)
    
    # 1. Enlight IR Scraper Test
    print(f"\n--- Testing Enlight IR Scraper for {company_name} ---")
    try:
        enlight_scraper = EnlightScraper(company_name)
        ir_reports = enlight_scraper.fetch_report_links()
        
        print(f"\n✓ Found {len(ir_reports)} reports from Enlight IR:")
        for r in ir_reports[:10]:  # Show first 10
            print(f"  - {r.year} {r.period}: {r.url.split('/')[-1]}")
        
        # Download first report as test
        if ir_reports:
            print(f"\n--- Downloading Sample Report (First IR Report) ---")
            downloaded_path = enlight_scraper.download_report(ir_reports[0])
            if downloaded_path:
                print(f"✓ Successfully downloaded to: {downloaded_path}")
    except Exception as e:
        print(f"✗ Enlight Scraper Failed: {e}")
        import traceback
        traceback.print_exc()
    
    # 2. TASE Scraper Test
    print(f"\n--- Testing TASE Scraper for {company_name} ---")
    try:
        tase_scraper = TaseScraper(company_name, company_id="720") 
        tase_reports = tase_scraper.fetch_report_links()
        
        print(f"\n✓ Found {len(tase_reports)} reports from TASE:")
        for r in tase_reports[:10]:  # Show first 10
            print(f"  - {r.year} {r.period}: {r.url.split('/')[-1] if '/' in r.url else r.url[:50]}")
        
        # Download first report as test
        if tase_reports:
            print(f"\n--- Downloading Sample Report (First TASE Report) ---")
            downloaded_path = tase_scraper.download_report(tase_reports[0])
            if downloaded_path:
                print(f"✓ Successfully downloaded to: {downloaded_path}")
    except Exception as e:
        print(f"✗ TASE Scraper Failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)
    print("DEMO COMPLETE")
    print("="*70)

if __name__ == "__main__":
    main()
