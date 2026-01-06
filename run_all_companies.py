import sys
import os
import subprocess
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from config.companies import RENEWABLE_COMPANIES

def main():
    print("="*60)
    print("STARTING SECTOR-WIDE DATA COLLECTION")
    print("="*60)
    print(f"Target Companies: {len(RENEWABLE_COMPANIES)}\n")
    
    companies = list(RENEWABLE_COMPANIES.keys())
    
    # Optional: Allow resuming from a specific company if args provided
    start_index = 0
    if len(sys.argv) > 1:
        start_company = sys.argv[1]
        try:
            start_index = companies.index(start_company)
            print(f"Resuming from {start_company}...")
        except ValueError:
            print(f"Company {start_company} not found. Starting from beginning.")
    
    for i, company_key in enumerate(companies[start_index:]):
        company_data = RENEWABLE_COMPANIES[company_key]
        name = company_data['english_name']
        print("\n" + "-"*60)
        print(f"[{i+1+start_index}/{len(companies)}] Processing: {name} ({company_key})")
        print("-"*60)
        
        cmd = [
            "./venv/bin/python3",
            "src/download.py",
            "--company", company_key,
            "--years", "5",
            "--upload"
        ]
        
        try:
            # Run the pipeline for this company
            result = subprocess.run(cmd, check=False)
            
            if result.returncode != 0:
                print(f"⚠ Pipeline failed for {company_key} with exit code {result.returncode}")
            else:
                print(f"✓ Pipeline completed for {company_key}")
                
        except Exception as e:
            print(f"⚠ Execution error for {company_key}: {e}")
            
    print("\n" + "="*60)
    print("SECTOR-WIDE COLLECTION FINISHED")
    print("="*60)

if __name__ == "__main__":
    main()
