#!/usr/bin/env python3
"""
Download script for financial data collection.
Focuses solely on scraping and downloading reports/materials.
"""

import argparse
import sys
import os
import asyncio
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from scrapers.enlight_scraper import EnlightScraper
from scrapers.tase_playwright_scraper import TasePlaywrightScraper
from scrapers.base_scraper import BaseScraper
from config.companies import RENEWABLE_COMPANIES
from drive_integration.drive_uploader import DriveUploader

async def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description='Financial Data Downloader')
    parser.add_argument('--company', type=str, required=True, help='Company name (e.g. Enlight, Energix, Ormat)')
    parser.add_argument('--years', type=float, default=5, help='Number of years to look back')
    parser.add_argument('--upload', action='store_true', help='Upload to Google Drive after download')
    args = parser.parse_args()
    
    # Load Company Config
    target_company = None
    company_key = None
    
    for key, data in RENEWABLE_COMPANIES.items():
        if key.lower() == args.company.lower():
            target_company = data
            company_key = key
            break
            
    if not target_company:
        print(f"Error: Company '{args.company}' not found in registry.")
        print("Available companies:", ", ".join(RENEWABLE_COMPANIES.keys()))
        return

    company_name = target_company['english_name']
    tase_id = target_company['tase_id']
    ir_url = target_company.get('ir_url')
    
    print(f"======================================================================")
    print(f"FINANCIAL DATA DOWNLOADER: {company_name}")
    print(f"======================================================================\n")
    
    all_reports = []
    
    # 1. Custom IR Scraper (if available) - SYNC
    ir_scraper = None
    if company_key == 'Enlight' and ir_url:
        print(f"  → Scraping {company_name} IR website...")
        try:
            ir_scraper = EnlightScraper(ir_url)
            # Todo: update EnlightScraper to accept years arg if supported
            ir_reports = ir_scraper.fetch_report_links()
            all_reports.extend(ir_reports)
            print(f"    ✓ Found {len(ir_reports)} reports from IR site")
        except Exception as e:
            print(f"    ⚠ Error scraping IR site: {e}")
    elif ir_url:
         print(f"  ⚠ Custom scraper for {company_name} IR site not implemented yet.")
    else:
         print(f"  ℹ No IR site URL configured for {company_name}, relying on TASE.")

    # 2. TASE Scraper (Generic) - ASYNC
    print(f"\n  → Scraping TASE for {company_name} (headless browser)...")
    tase_scraper = None
    try:
        tase_scraper = TasePlaywrightScraper(company_name, tase_id)
        # Pass company_id for web scraping
        company_web_id = target_company.get('company_id')
        tase_reports = await tase_scraper._fetch_reports_async(years_back=args.years, company_id=company_web_id)
        all_reports.extend(tase_reports)
        print(f"    ✓ Found {len(tase_reports)} reports from TASE")
    except Exception as e:
         print(f"    ⚠ Error scraping TASE: {e}")
         import traceback
         traceback.print_exc()

    print(f"\n  Total reports found: {len(all_reports)}\n")
    
    if not all_reports:
        print("No reports found. Exiting.")
        return

    # Download Reports
    print("Downloading reports...\n")
    
    downloaded_reports = []
    total = len(all_reports)
    
    # Create main download directory regarding structure
    # Structure: downloads/Company/Year/Period/
    base_download_dir = os.path.join("downloads", company_name.replace(" ", "_"))
    
    for i, report in enumerate(all_reports):
        # Determine target folder
        year_dir = os.path.join(base_download_dir, str(report.year))
        period_dir = os.path.join(year_dir, report.period)
        
        # We don't know if it's "Financials" or "Others" yet without analysis, 
        # but we can default to a "Raw" or just mix them, or use TASE metadata if reliable.
        # For now, let's put them in period_dir directly. 
        # TasePlaywrightScraper implementation might need updating to respect this path,
        # but currently it takes a specific save path or uses self.output_dir.
        
        # Actually `download_report` takes `save_path`.
        os.makedirs(period_dir, exist_ok=True)
        
        # Naming convention
        is_tase = "tase.co.il" in report.url
        suffix = "TASE" if is_tase else "IR"
        
        # Extract report ID for uniqueness
        import re
        rid_match = re.search(r'(?:details|companies)/(\d+)', report.url) or re.search(r'reportId=(\d+)', report.url)
        rid = rid_match.group(1) if rid_match else str(i)
        
        base_name = f"{report.year}_{report.period}_{company_key}_{rid}_{suffix}" 
        # Note: Scraper appends extension
        
        # For TASE scraper, we pass the directory + base_name prefix to let it handle attachments
        # OR we pass a full path if it's a single file. TASE scraper handles multi-file.
        # Let's target the period directory.
        tase_scraper_target = os.path.join(period_dir, base_name)
        
        print(f"  [{i+1}/{total}] {report.year} {report.period}")
        
        try:
            final_path = ""
            if is_tase:
                if not tase_scraper:
                     tase_scraper = TasePlaywrightScraper(company_name, tase_id)
                
                # Pass the output_dir directly to download_report
                final_path = await tase_scraper.download_report(report, output_dir=period_dir)
            else:
                 # IR Scraper
                 local_path = os.path.join(period_dir, base_name + ".pdf")
                 if ir_scraper:
                     final_path = ir_scraper.download_report(report, local_path)
                 else:
                     dummy = BaseScraper("dummy")
                     final_path = dummy.download_report(report, local_path)

            if final_path or report.local_paths:
                downloaded_reports.append(report)
                
        except Exception as e:
            print(f"  ⚠ Download failed: {e}")

    print(f"\n  ✓ Successfully downloaded {len(downloaded_reports)} reports\n")
    
    if args.upload:
        print("Uploading to Google Drive...")
        try:
            uploader = DriveUploader()
            if uploader.authenticate():
                apps_id = uploader.create_folder("apps")
                finance_id = uploader.create_folder("finance", apps_id)
                company_folder_id = uploader.create_folder(company_name, finance_id)
                
                for report in downloaded_reports:
                    # Upload Logic similar to main.py
                    # Create remote structure
                    year_folder_id = uploader.create_folder(str(report.year), company_folder_id)
                    period_folder_id = uploader.create_folder(report.period, year_folder_id)
                    
                    files = report.local_paths if report.local_paths else ([report.local_path] if report.local_path else [])
                    
                    for file_path in files:
                        if not os.path.exists(file_path): continue
                        print(f"  Uploading {os.path.basename(file_path)}...")
                        uploader.upload_file(file_path, period_folder_id, os.path.basename(file_path))
                        
            else:
                print("  ⚠ Authentication failed")
        except Exception as e:
            print(f"  ⚠ Drive Upload failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
