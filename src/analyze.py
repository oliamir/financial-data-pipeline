#!/usr/bin/env python3
"""
Analysis script for financial data.
Processes downloaded reports using AI (Gemini or Claude).
"""

import argparse
import sys
import os
import shutil
import pandas as pd
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from intelligence.llm_client import LLMClient
from intelligence.classifier import DocumentClassifier, DocumentType
from intelligence.extractor import FinancialExtractor
from intelligence.thesis import ThesisGenerator
from config.companies import RENEWABLE_COMPANIES

def main():
    parser = argparse.ArgumentParser(description='Financial Report AI Analyst')
    parser.add_argument('--company', type=str, required=True, help='Company name')
    parser.add_argument('--provider', type=str, default='google', choices=['google', 'anthropic'], help='AI Provider')
    parser.add_argument('--model', type=str, help='Model name (e.g. gemini-2.0-flash, claude-3-5-sonnet-20241022)')
    parser.add_argument('--dry-run', action='store_true', help='Do not move files or write outputs')
    args = parser.parse_args()

    # Resolve Company
    target_company = None
    for key, data in RENEWABLE_COMPANIES.items():
        if key.lower() == args.company.lower():
            target_company = data
            break
            
    if not target_company:
        print(f"Error: Company '{args.company}' not found.")
        return

    company_name = target_company['english_name']
    
    # Defaults
    if not args.model:
        args.model = "gemini-2.0-flash" if args.provider == 'google' else "claude-3-5-sonnet-20241022"

    print(f"======================================================================")
    print(f"AI ANALYST: {company_name}")
    print(f"Provider: {args.provider.upper()} | Model: {args.model}")
    print(f"======================================================================\n")

    # Initialize Client
    try:
        if args.provider == 'google':
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key: raise ValueError("GOOGLE_API_KEY not set")
            llm_client = LLMClient(api_key=api_key)
        else:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key: raise ValueError("ANTHROPIC_API_KEY not set")
            # We'll update LLMClient to accept provider/client type
            llm_client = LLMClient(api_key=api_key, provider='anthropic')

        classifier = DocumentClassifier(llm_client)
        extractor = FinancialExtractor(llm_client)
        thesis_gen = ThesisGenerator(llm_client)
    except Exception as e:
        print(f"Error initializing AI client: {e}")
        return

    # Scan Downloads Directory
    download_dir = os.path.join("downloads", company_name.replace(" ", "_"))
    if not os.path.exists(download_dir):
        print(f"No downloads found at {download_dir}")
        return

    print(f"Scanning {download_dir}...\n")
    
    financial_models = []
    thesis_path = os.path.join(download_dir, "Investment_Memo.md")
    current_thesis = ""
    if os.path.exists(thesis_path):
        with open(thesis_path, "r") as f:
            current_thesis = f.read()

    # Walk through year/period directories
    for root, dirs, files in os.walk(download_dir):
        for file in files:
            if file.startswith(".") or file in ["Financial_Model.csv", "Investment_Memo.md"]: continue
            
            file_path = os.path.join(root, file)
            
            # Skip if already in Financials/Others (already processed)
            # Actually, we might want to re-process if --force? 
            # For now, let's process anything that is NOT in "Financials" or "Others" subfolder of a period?
            # Or simplified: Process everything, move to final location.
            
            parent_dir = os.path.basename(root)
            if parent_dir in ["Financials", "Others"]: continue # Already sorted
            
            print(f"Processing: {file}")
            
            if args.dry_run:
                print("  (Dry Run) Skipping AI calls")
                continue

            try:
                # 1. Classify
                print("  -> Classifying...")
                # Note: We need to pass model_name to classify if supported, or set in client
                doc_type = classifier.classify(file_path, model_name=args.model)
                print(f"     Type: {doc_type.value}")
                
                # 2. Extract & Thesis
                if doc_type == DocumentType.FINANCIAL_REPORT:
                    print("  -> Extracting Financials...")
                    data = extractor.extract_financials(file_path, model_name=args.model)
                    
                    # Try to infer year/period from path or filename if not in data
                    # Filename format: YYYY_Period_...
                    parts = file.split('_')
                    if len(parts) >= 2 and parts[0].isdigit():
                        data['year'] = parts[0]
                        data['period'] = parts[1]
                    
                    data['source_file'] = file
                    financial_models.append(data)
                    
                    print("  -> Updating Thesis...")
                    current_thesis = thesis_gen.update_thesis(current_thesis, file_path, model_name=args.model)
                    with open(thesis_path, "w") as f:
                        f.write(current_thesis)

                # 3. Move File
                target_subdir = "Financials" if doc_type == DocumentType.FINANCIAL_REPORT else "Others"
                target_dir = os.path.join(root, target_subdir)
                os.makedirs(target_dir, exist_ok=True)
                new_path = os.path.join(target_dir, file)
                
                if file_path != new_path:
                    shutil.move(file_path, new_path)
                    print(f"  -> Moved to {target_subdir}/")
                    
            except Exception as e:
                print(f"  ⚠ Failed to process {file}: {e}")

    # Save Model
    if financial_models and not args.dry_run:
        df = pd.DataFrame(financial_models)
        out_path = os.path.join(download_dir, "Financial_Model.csv")
        df.to_csv(out_path, index=False)
        print(f"\n✓ Saved Financial Model to {out_path}")

if __name__ == "__main__":
    main()
