#!/usr/bin/env python3
"""
Pipeline orchestrator for financial data collection and analysis.
Runs download.py followed by analyze.py for a specific company.
Includes logic to skip download if run recently (within 7 days).
"""

import argparse
import sys
import subprocess
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))
try:
    from config.companies import RENEWABLE_COMPANIES
except ImportError:
    # Fallback if running from wrong dir? Should be fine given cwd.
    print("Warning: Could not import companies config. Directory resolution might fail.")
    RENEWABLE_COMPANIES = {}

def run_step(step_name, command):
    print(f"\n{'='*60}")
    print(f"RUNNING STEP: {step_name}")
    print(f"Command: {' '.join(command)}")
    print(f"{'='*60}\n")
    
    try:
        # Stream output to console
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        with process.stdout:
            for line in iter(process.stdout.readline, ''):
                print(line, end='')
                
        returncode = process.wait()
        
        if returncode != 0:
            print(f"\n⚠ Step '{step_name}' failed with exit code {returncode}")
            return False
            
        print(f"\n✓ Step '{step_name}' completed successfully")
        return True
        
    except Exception as e:
        print(f"\n⚠ Failed to execute step '{step_name}': {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Data Pipeline Orchestrator')
    parser.add_argument('--company', type=str, required=True, help='Company name (Sofwave or Apollo)')
    parser.add_argument('--years', type=str, default="all", help='Years to fetch (e.g. 2021-2023)')
    parser.add_argument('--skip-download', action='store_true', help='Skip download step')
    parser.add_argument('--skip-analyze', action='store_true', help='Skip analysis step')
    parser.add_argument('--force-download', action='store_true', help='Force re-download')
    parser.add_argument('--provider', type=str, default='google', help='AI Provider')
    parser.add_argument('--model', type=str, help='AI Model name')
    parser.add_argument('--no-fallback', action='store_true', help='Disable provider fallback')
    args = parser.parse_args()
    
    venv_python = "./venv/bin/python3"
    if not os.path.exists(venv_python):
        venv_python = sys.executable

    # Resolve Company Directory
    company_data = None
    for key, data in RENEWABLE_COMPANIES.items():
        if key.lower() == args.company.lower():
            company_data = data
            break
    
    download_dir = None
    marker_file = None
            
    if company_data:
        company_name = company_data['english_name']
        download_dir = os.path.join("downloads", company_name.replace(" ", "_"))
        marker_file = os.path.join(download_dir, ".last_download_success")
    else:
        print(f"Warning: Company '{args.company}' not found in config. Skip logic might be limited.")

    # 1. Download
    should_download = not args.skip_download
    
    if should_download and not args.force_download and marker_file and os.path.exists(marker_file):
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(marker_file))
            if datetime.now() - mtime < timedelta(days=7):
                print(f"\n[SKIP] Recent download found ({mtime.strftime('%Y-%m-%d %H:%M')}) < 7 days ago.")
                print("       Skipping download step. Use --force-download to override.")
                should_download = False
        except Exception as e:
            print(f"Warning: Error checking marker file: {e}")

    if should_download:
        cmd_download = [
            venv_python,
            "src/download.py",
            "--company", args.company,
            "--years", args.years,
            "--upload"
        ]
        if not run_step("Download & Upload", cmd_download):
            print("Stopping pipeline due to download failure.")
            sys.exit(1)
        
        # Update marker file on success
        if marker_file:
            try:
                os.makedirs(os.path.dirname(marker_file), exist_ok=True)
                with open(marker_file, 'w') as f:
                    f.write(str(datetime.now()))
            except Exception as e:
                print(f"Warning: Could not update marker file: {e}")

    # 2. Analyze
    if not args.skip_analyze:
        print(f"\n[2/2] Running Analysis for {args.company}...")
        cmd_analyze = [
            venv_python,
            "src/analyze.py",
            "--company", args.company,
            "--provider", args.provider
        ]
        
        if args.model:
            cmd_analyze.extend(["--model", args.model])
            
        if args.no_fallback:
            cmd_analyze.append("--no-fallback")
            
        if not run_step("AI Analysis", cmd_analyze):
            print("Analysis step failed.")
            sys.exit(1)

    print("\n" + "="*60)
    print(f"PIPELINE COMPLETED FOR {args.company}")
    print("="*60)

if __name__ == "__main__":
    main()
