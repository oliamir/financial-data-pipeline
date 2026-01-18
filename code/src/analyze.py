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
    parser.add_argument('--agent', type=str, help='Subagent persona name (e.g. data-analyst)')
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
    if args.agent:
        print(f"Subagent: {args.agent}")
    print(f"Mode: {'WATCH' if args.watch else 'SINGLE RUN'}")
    print(f"======================================================================\n")

    # Initialize Client
    try:
        # Pass provider preference, but keys are loaded from env automatically
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
        # Note: Extractor might need update to accept system prompt override, 
        # or we just assume the 'agent' prompt is for general analysis/thesis generation.
        # For now, let's say it affects the Thesis Generator primarily.
        extractor = FinancialExtractor(llm_client)
        thesis_gen = ThesisGenerator(llm_client, system_prompt=agent_system_prompt)
    except Exception as e:
        print(f"Error initializing AI client: {e}")
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
                
                if file_path in processed_paths or args.dry_run:
                    print("  (Dry Run/Processed) Skipping")
                    continue
                
                if not os.path.exists(file_path):
                    print(f"  ⚠ File not found (moved?): {file_path}")
                    continue

                try:
                    # SMART ROUTING LOGIC
                    active_client = llm_client
                    active_model = args.model
                    
                    is_financial = "_FINANCIAL" in file
                    if is_financial:
                        print("  ★ High Priority File Detected (Financial Report)")
                        # Switch to Gemini if not already using Google
                        if args.provider != 'google':
                            print("    -> Switching to Gemini for this file...")
                            try:
                                active_client = LLMClient(provider='google', enable_fallback=True)
                                active_model = "gemini-2.0-flash" 
                            except:
                                print("    ⚠ Failed to switch to Gemini, staying with default.")

                    # 1. Classify
                    print("  -> Classifying...")
                    doc_type = classifier.classify(file_path, model_name=active_model)
                    print(f"     Type: {doc_type.value}")
                    
                    # 2. Extract & Thesis
                    if doc_type == DocumentType.FINANCIAL_REPORT or is_financial:
                        print("  -> Extracting Financials...")
                        special_extractor = FinancialExtractor(active_client)
                        data = special_extractor.extract_financials(file_path, model_name=active_model)
                        
                        # Try to infer year/period
                        parts = file.split('_')
                        if len(parts) >= 2 and parts[0].isdigit():
                            data['year'] = parts[0]
                            data['period'] = parts[1]
                        
                        data['source_file'] = file
                        if is_financial:
                            data['is_high_priority'] = True
                        
                        financial_models.append(data)
                        
                        print("  -> Updating Thesis...")
                        special_thesis = ThesisGenerator(active_client, system_prompt=agent_system_prompt)
                        current_thesis = special_thesis.update_thesis(current_thesis, file_path, model_name=active_model)
                        with open(thesis_path, "w") as f:
                            f.write(current_thesis)

                    # 3. Move File
                    target_subdir = "Financials" if doc_type == DocumentType.FINANCIAL_REPORT else "Others"
                    target_dir = os.path.join(root, target_subdir)
                    os.makedirs(target_dir, exist_ok=True)
                    new_path = os.path.join(target_dir, file)
                    
                    if file_path != new_path:
                        if not args.dry_run:
                            try:
                                if os.path.exists(file_path):
                                    shutil.move(file_path, new_path)
                                    print(f"  -> Moved to {target_subdir}/")
                                    processed_paths.add(new_path)
                                else:
                                    print(f"  ⚠ File vanished before move: {file_path}")
                            except Exception as e:
                                print(f"  ⚠ Error moving file {file}: {e}")
                    
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
