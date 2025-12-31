#!/usr/bin/env python3
"""
Main pipeline script for financial data collection and processing.

This script:
1. Scrapes financial reports from company IR sites and TASE
2. Downloads PDFs locally
3. Uploads to Google Drive (optional)
4. Parses PDFs to extract financial data
5. Calculates KPIs
6. Exports results to Excel
"""

import argparse
import sys
import os
import pandas as pd
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from scrapers.enlight_scraper import EnlightScraper
from scrapers.tase_playwright_scraper import TasePlaywrightScraper
from models.financial_parser import PDFFinancialParser
from drive_integration.drive_uploader import DriveUploader

# Company configurations
COMPANIES = {
    'Enlight': {
        'name': 'Enlight_Renewable_Energy',
        'tase_id': '720',
        'has_ir_site': True
    }
}

def main():
    parser = argparse.ArgumentParser(description='Financial Data Collection Pipeline')
    parser.add_argument('--company', type=str, default='Enlight', 
                       choices=list(COMPANIES.keys()),
                       help='Company to scrape')
    parser.add_argument('--skip-drive', action='store_true',
                       help='Skip Google Drive upload')
    parser.add_argument('--skip-parse', action='store_true',
                       help='Skip PDF parsing')
    parser.add_argument('--download-only', action='store_true',
                       help='Only download reports, skip parsing and upload')
    
    args = parser.parse_args()
    
    print("="*70)
    print("FINANCIAL DATA COLLECTION PIPELINE")
    print("="*70)
    
    company_config = COMPANIES[args.company]
    company_name = company_config['name']
    
    # Step 1: Scrape reports
    print(f"\n[1/5] Scraping reports for {args.company}...")
    all_reports = []
    
    # Scrape IR site
    if company_config['has_ir_site']:
        print(f"\n  → Scraping {args.company} IR website...")
        if args.company == 'Enlight':
            scraper = EnlightScraper(company_name)
            ir_reports = scraper.fetch_report_links()
            all_reports.extend(ir_reports)
            print(f"    ✓ Found {len(ir_reports)} reports from IR site")
    
    # Scrape TASE
    print(f"\n  → Scraping TASE for {args.company} (headless browser)...")
    tase_scraper = TasePlaywrightScraper(company_name, company_config['tase_id'])
    tase_reports = tase_scraper.fetch_report_links()
    all_reports.extend(tase_reports)
    print(f"    ✓ Found {len(tase_reports)} reports from TASE")
    
    print(f"\n  Total reports found: {len(all_reports)}")
    
    if not all_reports:
        print("\n  ⚠ No reports found. Exiting.")
        return
    
    # Step 2: Download reports
    print(f"\n[2/5] Downloading reports...")
    downloaded_reports = []
    
    for i, report in enumerate(all_reports, 1):
        print(f"\n  [{i}/{len(all_reports)}] {report.year} {report.period}")
        
        # Determine which scraper to use
        if report.source == "Enlight_IR":
            scraper = EnlightScraper(company_name)
        else:
            scraper = TasePlaywrightScraper(company_name, company_config['tase_id'])
        
        local_path = scraper.download_report(report)
        if local_path:
            downloaded_reports.append(report)
    
    print(f"\n  ✓ Successfully downloaded {len(downloaded_reports)} reports")
    
    if args.download_only:
        print("\n  Download-only mode. Exiting.")
        return
    
    # Step 3: Upload to Google Drive (optional)
    if not args.skip_drive:
        print(f"\n[3/5] Uploading to Google Drive...")
        
        if not os.path.exists('credentials.json'):
            print("  ⚠ No credentials.json found. Skipping Drive upload.")
            print("  Run ./setup_drive.py to set up Google Drive integration.")
        else:
            uploader = DriveUploader()
            if uploader.authenticate():
                for report in downloaded_reports:
                    if not report.local_path:
                        continue
                    
                    print(f"\n  Uploading {report.year} {report.period}...")
                    folder_id = uploader.create_company_structure(
                        company_name, report.year, report.period
                    )
                    
                    if folder_id:
                        file_id = uploader.upload_file(report.local_path, folder_id)
                        if file_id:
                            report.drive_id = file_id
                
                print(f"\n  ✓ Upload complete")
            else:
                print("  ⚠ Authentication failed. Skipping Drive upload.")
    else:
        print(f"\n[3/5] Skipping Google Drive upload (--skip-drive)")
    
    # Step 4: Parse PDFs
    if not args.skip_parse:
        print(f"\n[4/5] Parsing PDFs and extracting financial data...")
        
        parser = PDFFinancialParser()
        financial_data_list = []
        kpi_list = []
        
        for report in downloaded_reports:
            if not report.local_path or not os.path.exists(report.local_path):
                continue
            
            print(f"\n  Parsing {report.year} {report.period}...")
            financial_data = parser.parse_pdf(
                report.local_path, 
                company_name, 
                report.year, 
                report.period
            )
            
            financial_data_list.append(financial_data.to_dict())
            
            # Calculate KPIs
            kpis = parser.calculate_kpis(financial_data)
            kpi_list.append(kpis.to_dict())
        
        print(f"\n  ✓ Parsed {len(financial_data_list)} reports")
        
        # Step 5: Export results
        print(f"\n[5/5] Exporting results...")
        
        output_dir = Path('output')
        output_dir.mkdir(exist_ok=True)
        
        # Export financial data
        if financial_data_list:
            df_financial = pd.DataFrame(financial_data_list)
            financial_output = output_dir / f'{company_name}_financial_data.xlsx'
            df_financial.to_excel(financial_output, index=False)
            print(f"  ✓ Financial data: {financial_output}")
        
        # Export KPIs
        if kpi_list:
            df_kpis = pd.DataFrame(kpi_list)
            kpi_output = output_dir / f'{company_name}_kpis.xlsx'
            df_kpis.to_excel(kpi_output, index=False)
            print(f"  ✓ KPIs: {kpi_output}")
    else:
        print(f"\n[4/5] Skipping PDF parsing (--skip-parse)")
        print(f"\n[5/5] Skipping export")
    
    print("\n" + "="*70)
    print("✓ PIPELINE COMPLETE")
    print("="*70)

if __name__ == "__main__":
    main()
