#!/usr/bin/env python3
"""
Analysis script for financial data.
Processes downloaded reports using AI (Gemini or Claude).

Usage:
  # Standard run (skips already-processed files in Financials/Others)
  python3 code/src/analyze.py --company Sofwave --provider google

  # Reprocess all files (including those in Financials/Others)
  python3 code/src/analyze.py --company Sofwave --provider google --reprocess

  # Extract only (no thesis generation)
  python3 code/src/analyze.py --company Sofwave --extract-only

  # Watch mode (continuous monitoring)
  python3 code/src/analyze.py --company Sofwave --watch
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
    parser.add_argument('--model', type=str, help='Model name (e.g. gemini-2.0-flash)')
    parser.add_argument('--watch', action='store_true', help='Continuously monitor for new files')
    parser.add_argument('--dry-run', action='store_true', help='Do not move files or write outputs')
    parser.add_argument('--no-fallback', action='store_true', help='Disable automatic provider fallback')
    parser.add_argument('--agent', type=str, help='Subagent persona name')
    parser.add_argument('--reprocess', action='store_true', help='Reprocess all files, including those already in Financials/Others')
    parser.add_argument('--extract-only', action='store_true', help='Only extract financials, skip thesis generation')
    parser.add_argument('--financial-only', action='store_true', help='Only process files tagged as FINANCIAL, skip Others')
    args = parser.parse_args()

    # Resolve Company
    target_company = None
    company_key = None
    for key, data in RENEWABLE_COMPANIES.items():
        if key.lower() == args.company.lower():
            target_company = data
            company_key = key
            break
            
    if not target_company:
        print(f"Error: Company '{args.company}' not found.")
        print(f"Available: {', '.join(RENEWABLE_COMPANIES.keys())}")
        return

    company_name = target_company['english_name']
    
    # Defaults
    if not args.model:
        model_defaults = {
            'google': 'gemini-2.0-flash',
            'anthropic': 'claude-3-5-sonnet-20241022',
            'openai': 'gpt-4o',
            'ollama': 'llama3.1'
        }
        args.model = model_defaults.get(args.provider, 'gemini-2.0-flash')

    print(f"======================================================================")
    print(f"AI ANALYST: {company_name}")
    print(f"Provider: {args.provider.upper()} | Model: {args.model}")
    if args.agent:
        print(f"Subagent: {args.agent}")
    print(f"Mode: {'WATCH' if args.watch else 'REPROCESS' if args.reprocess else 'SINGLE RUN'}")
    print(f"======================================================================\n")

    # Initialize Client
    try:
        llm_client = LLMClient(provider=args.provider, enable_fallback=not args.no_fallback)
        
        # Load Subagent System Prompt if requested
        agent_system_prompt = None
        if args.agent:
            from intelligence.agent_manager import AgentManager
            am = AgentManager()
            agent_system_prompt = am.get_agent_prompt(args.agent)
            if agent_system_prompt:
                print(f"  ✓ Loaded specialized persona: {args.agent}")
            else:
                print(f"  ⚠ Agent '{args.agent}' not found. Using default persona.")

        # Warn if keys missing
        if args.provider == 'google' and not llm_client.keys["google"]:
            print("Warning: GOOGLE_API_KEY expected but not found.")
        if args.provider == 'anthropic' and not llm_client.keys["anthropic"]:
            print("Warning: ANTHROPIC_API_KEY expected but not found.")
        if args.provider == 'openai' and not llm_client.keys["openai"]:
            print("Warning: OPENAI_API_KEY expected but not found.")

        classifier = DocumentClassifier(llm_client)
        extractor = FinancialExtractor(llm_client)
        thesis_gen = ThesisGenerator(llm_client, system_prompt=agent_system_prompt)
    except Exception as e:
        print(f"Error initializing AI client: {e}")
        import traceback
        traceback.print_exc()
        return

    # Check Directory
    download_dir = os.path.join("output", company_name.replace(" ", "_"))
    if not os.path.exists(download_dir):
        print(f"Waiting for directory: {download_dir}...")
        while args.watch and not os.path.exists(download_dir):
            import time
            time.sleep(5)
        
        if not os.path.exists(download_dir):
            print(f"No downloads found at {download_dir}")
            return

    # If reprocessing, clear existing CSV and memo
    if args.reprocess:
        csv_path = os.path.join(download_dir, "Financial_Model.csv")
        memo_path = os.path.join(download_dir, "Investment_Memo.md")
        if os.path.exists(csv_path):
            os.remove(csv_path)
            print(f"  Cleared existing {csv_path}")
        if os.path.exists(memo_path):
            os.remove(memo_path)
            print(f"  Cleared existing {memo_path}")

    # Tracking
    processed_paths = set()
    stats = {"total": 0, "extracted": 0, "skipped": 0, "failed": 0}
    
    import time
    
    while True:
        print(f"\nScanning {download_dir}...")
        
        financial_models = []
        
        thesis_path = os.path.join(download_dir, "Investment_Memo.md")
        current_thesis = ""
        if os.path.exists(thesis_path):
            with open(thesis_path, "r") as f:
                current_thesis = f.read()

        # Collect all PDF files
        files_found_this_cycle = 0
        
        for root, dirs, files in os.walk(download_dir):
            for file in sorted(files):
                if not file.lower().endswith('.pdf'):
                    continue
                if file.startswith("."):
                    continue
                    
                file_path = os.path.join(root, file)
                
                # Skip tracking files
                if file in ["Financial_Model.csv", "Investment_Memo.md"]:
                    continue
                
                # Deduplication
                if file_path in processed_paths:
                    continue
                
                # Unless reprocessing, skip files already in Financials/Others
                parent_dir = os.path.basename(root)
                if not args.reprocess and parent_dir in ["Financials", "Others"]:
                    processed_paths.add(file_path)
                    continue
                
                # If --financial-only, skip non-FINANCIAL files
                if args.financial_only and "_FINANCIAL" not in file:
                    processed_paths.add(file_path)
                    continue
                
                files_found_this_cycle += 1
                stats["total"] += 1
                
                if args.dry_run:
                    print(f"  [DRY RUN] Would process: {file}")
                    processed_paths.add(file_path)
                    continue
                
                if not os.path.exists(file_path):
                    print(f"  ⚠ File not found (moved?): {file_path}")
                    continue

                try:
                    print(f"\n  ┌─ Processing: {file}")
                    
                    # Choose model based on file priority
                    active_client = llm_client
                    active_model = args.model
                    
                    is_financial = "_FINANCIAL" in file
                    if is_financial:
                        print(f"  │  ★ Financial Report")

                    # 1. Classify
                    if is_financial:
                        doc_type = DocumentType.FINANCIAL_REPORT
                        print(f"  │  Classification: {doc_type.value} (from filename)")
                    else:
                        print(f"  │  → Classifying...")
                        doc_type = classifier.classify(file_path, model_name=active_model)
                        print(f"  │  Classification: {doc_type.value}")
                    
                    # 2. Extract if financial
                    if doc_type == DocumentType.FINANCIAL_REPORT:
                        print(f"  │  → Extracting financials...")
                        data = extractor.extract_financials(file_path, model_name=active_model)
                        
                        # Infer year/period from filename
                        parts = file.split('_')
                        if len(parts) >= 2 and parts[0].isdigit():
                            data['year'] = parts[0]
                            data['period'] = parts[1]
                        
                        data['source_file'] = file
                        
                        # Validate extraction quality
                        if extractor.is_extraction_valid(data):
                            financial_models.append(data)
                            stats["extracted"] += 1
                            print(f"  │  ✓ Valid extraction ({_count_fields(data)} data points)")
                        else:
                            stats["skipped"] += 1
                            print(f"  │  ⚠ Extraction had insufficient data, skipping")
                            if "error" in data:
                                print(f"  │    Error: {data['error'][:100]}")
                        
                        # 3. Update thesis (unless extract-only)
                        if not args.extract_only and extractor.is_extraction_valid(data):
                            print(f"  │  → Updating thesis...")
                            try:
                                current_thesis = thesis_gen.update_thesis(
                                    current_thesis, file_path, 
                                    company_name=company_name,
                                    model_name=active_model
                                )
                                with open(thesis_path, "w") as f:
                                    f.write(current_thesis)
                            except Exception as e:
                                print(f"  │  ⚠ Thesis update failed: {e}")
                    else:
                        stats["skipped"] += 1

                    # 4. Move File (if not reprocessing from Financials/Others)
                    if not args.reprocess or parent_dir not in ["Financials", "Others"]:
                        target_subdir = "Financials" if doc_type == DocumentType.FINANCIAL_REPORT else "Others"
                        target_dir = os.path.join(root, target_subdir)
                        os.makedirs(target_dir, exist_ok=True)
                        new_path = os.path.join(target_dir, file)
                        
                        if file_path != new_path and not args.dry_run:
                            try:
                                if os.path.exists(file_path):
                                    shutil.move(file_path, new_path)
                                    print(f"  │  → Moved to {target_subdir}/")
                                    processed_paths.add(new_path)
                            except Exception as e:
                                print(f"  │  ⚠ Error moving: {e}")
                    
                    processed_paths.add(file_path)
                    print(f"  └─ Done")
                        
                except Exception as e:
                    stats["failed"] += 1
                    print(f"  │  ⚠ Failed: {e}")
                    import traceback
                    traceback.print_exc()
                    print(f"  └─ Failed")
                    processed_paths.add(file_path)

        # Update CSV
        if financial_models and not args.dry_run:
            out_path = os.path.join(download_dir, "Financial_Model.csv")
            
            # Flatten nested dicts for CSV
            flat_models = []
            for model in financial_models:
                flat = {}
                for key, value in model.items():
                    if isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            flat[f"{key}.{sub_key}" if key not in ["income_statement", "balance_sheet", "cash_flow"] else sub_key] = sub_value
                    else:
                        flat[key] = value
                flat_models.append(flat)
            
            if os.path.exists(out_path) and not args.reprocess:
                existing_df = pd.read_csv(out_path)
                new_df = pd.DataFrame(flat_models)
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                combined_df.to_csv(out_path, index=False)
            else:
                df = pd.DataFrame(flat_models)
                df.to_csv(out_path, index=False)
                
            print(f"\n✓ Updated Financial Model at {out_path}")
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"SUMMARY: {stats['total']} files processed")
        print(f"  ✓ Extracted: {stats['extracted']}")
        print(f"  ⊘ Skipped:   {stats['skipped']}")
        print(f"  ✗ Failed:    {stats['failed']}")
        print(f"{'='*60}")
        
        if not args.watch:
            break
            
        if files_found_this_cycle == 0:
            print("  No new files found.")
            
        print("Waiting 60s...")
        time.sleep(60)


def _count_fields(data: dict) -> int:
    """Count non-null numeric fields in extraction result."""
    count = 0
    for section in ["income_statement", "balance_sheet", "cash_flow"]:
        if section in data and isinstance(data[section], dict):
            for val in data[section].values():
                if val is not None:
                    count += 1
    return count


if __name__ == "__main__":
    main()
