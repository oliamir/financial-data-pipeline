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
from dotenv import load_dotenv

# Load env immediately
load_dotenv()

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
    parser.add_argument('--provider', type=str, default='google', choices=['google', 'anthropic', 'openai', 'ollama'], help='AI Provider')
    parser.add_argument('--model', type=str, help='Model name (e.g. gemini-2.0-flash, claude-3-5-sonnet-20241022, gpt-4o, llama3.1)')
    parser.add_argument('--watch', action='store_true', help='Continuously monitor for new files')
    parser.add_argument('--dry-run', action='store_true', help='Do not move files or write outputs')
    parser.add_argument('--no-fallback', action='store_true', help='Disable automatic provider fallback')
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
    print(f"Mode: {'WATCH' if args.watch else 'SINGLE RUN'}")
    print(f"======================================================================\n")

    # Initialize Client
    # Initialize Client
    try:
        # Pass provider preference, but keys are loaded from env automatically
        llm_client = LLMClient(provider=args.provider, enable_fallback=not args.no_fallback)
        
        # Warn if keys missing
        if args.provider == 'google' and not llm_client.keys["google"]:
             print("Warning: GOOGLE_API_KEY expected but not found.")
        if args.provider == 'anthropic' and not llm_client.keys["anthropic"]:
             print("Warning: ANTHROPIC_API_KEY expected but not found.")
        if args.provider == 'openai' and not llm_client.keys["openai"]:
             print("Warning: OPENAI_API_KEY expected but not found.")

        classifier = DocumentClassifier(llm_client)
        extractor = FinancialExtractor(llm_client)
        thesis_gen = ThesisGenerator(llm_client)
    except Exception as e:
        print(f"Error initializing AI client: {e}")
        return

    # Check Directory
    download_dir = os.path.join("downloads", company_name.replace(" ", "_"))
    if not os.path.exists(download_dir):
        print(f"Waiting for directory: {download_dir}...")
        while args.watch and not os.path.exists(download_dir):
            import time
            time.sleep(5)
        
        if not os.path.exists(download_dir):
            print(f"No downloads found at {download_dir}")
            return

    # Tracking sets
    processed_paths = set()
    
    import time
    
    while True:
        print(f"Scanning {download_dir}...")
        
        financial_models = []
        # Load existing models if any? No, we might append or rewrite. 
        # For simplicity in watch mode, maybe we just append to CSV or re-read it?
        # Let's simple re-read CSV to memory if needed, or just append new rows.
        # But for 'thesis', we definitely need to read current state each time.
        
        thesis_path = os.path.join(download_dir, "Investment_Memo.md")
        current_thesis = ""
        if os.path.exists(thesis_path):
            with open(thesis_path, "r") as f:
                current_thesis = f.read()

        # Walk through year/period directories
        files_found_this_cycle = 0
        
        for root, dirs, files in os.walk(download_dir):
            for file in files:
                if file.startswith(".") or file in ["Financial_Model.csv", "Investment_Memo.md"]: continue
                
                file_path = os.path.join(root, file)
                
                # Deduplication for watch mode
                if file_path in processed_paths: continue
                
                parent_dir = os.path.basename(root)
                if parent_dir in ["Financials", "Others"]: 
                    processed_paths.add(file_path)
                    continue 
                
                print(f"Processing: {file}")
                files_found_this_cycle += 1
                
                if args.dry_run:
                    print("  (Dry Run) Skipping AI calls")
                    processed_paths.add(file_path)
                    continue

                try:
                    # 1. Classify
                    print("  -> Classifying...")
                    doc_type = classifier.classify(file_path, model_name=args.model)
                    print(f"     Type: {doc_type.value}")
                    
                    # 2. Extract & Thesis
                    if doc_type == DocumentType.FINANCIAL_REPORT:
                        print("  -> Extracting Financials...")
                        data = extractor.extract_financials(file_path, model_name=args.model)
                        
                        # Try to infer year/period
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
                        # Update processed path to the NEW path so we don't re-process it if we scan again
                        processed_paths.add(new_path)
                    
                    processed_paths.add(file_path) # Mark original as processed too just in case
                        
                except Exception as e:
                    print(f"  ⚠ Failed to process {file}: {e}")
                    import traceback
                    traceback.print_exc()

        # Update CSV
        if financial_models and not args.dry_run:
            out_path = os.path.join(download_dir, "Financial_Model.csv")
            
            # If exists, load and append
            if os.path.exists(out_path):
                existing_df = pd.read_csv(out_path)
                new_df = pd.DataFrame(financial_models)
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                combined_df.to_csv(out_path, index=False)
            else:
                df = pd.DataFrame(financial_models)
                df.to_csv(out_path, index=False)
                
            print(f"✓ Updated Financial Model at {out_path}")
        
        if not args.watch:
            break
            
        if files_found_this_cycle == 0:
            print("  No new files found.")
            
        print("Waiting 60s...")
        time.sleep(60)

if __name__ == "__main__":
    main()
