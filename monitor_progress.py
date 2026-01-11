#!/usr/bin/env python3
import os
import time
import subprocess
import sys
from datetime import datetime

# Configuration
COMPANIES = [
    {"name": "Sofwave", "dir": "downloads/Sofwave_Medical"},
    {"name": "Apollo", "dir": "downloads/Apollo_Power"}
]

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_process_info(company_name):
    """Returns (is_running, model_name)"""
    try:
        # ps -ef | grep 'analyze.py' | grep '{company}'
        # We need to be careful to match the company argument passed to analyze.py
        cmd = f"ps -ef | grep 'analyze.py' | grep -i '{company_name}' | grep -v grep"
        try:
            output = subprocess.check_output(cmd, shell=True).decode().strip()
        except subprocess.CalledProcessError:
            output = ""
            
        if not output:
            return False, "-"
            
        # Parse model from command line args
        # Example: ... python3 src/analyze.py --company Sofwave --model gemini-2.0-flash ...
        model = "Unknown"
        lines = output.split('\n')
        # Use simple heuristic: regex or split
        # We'll just look at the first matching line
        
        args = lines[0].split()
        if "--model" in args:
            idx = args.index("--model")
            if idx + 1 < len(args):
                model = args[idx+1]
        
        return True, model
    except Exception as e:
        return False, "-"

def count_files(directory):
    if not os.path.exists(directory):
        return 0, 0
        
    total = 0
    processed = 0
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            # Skip metadata/hidden
            if file.startswith(".") or file in ["Financial_Model.csv", "Investment_Memo.md"]:
                continue
            
            total += 1
            
            # processed logic: if file is in 'Financials' or 'Others' subfolder
            # The structure is downloads/Company/2023_Q4/Financials/file.pdf
            
            parts = root.split(os.sep)
            if "Financials" in parts or "Others" in parts:
                processed += 1
                
    return total, processed

def main():
    try:
        while True:
            clear_screen()
            print(f"=== FINANCE PIPELINE TRACKER ===")
            print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 80)
            print(f"{'COMPANY':<15} | {'STATUS':<12} | {'MODEL':<25} | {'TOTAL':<8} | {'PROCESSED':<10}")
            print("-" * 80)
            
            for c in COMPANIES:
                is_running, model = get_process_info(c["name"])
                status = "🟢 RUNNING" if is_running else "🔴 STOPPED"
                total, processed = count_files(c["dir"])
                
                print(f"{c['name']:<15} | {status:<12} | {model:<25} | {total:<8} | {processed:<10}")
                
            print("=" * 80)
            print("Press Ctrl+C to exit.")
            
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nExiting Tracker.")
        sys.exit(0)

if __name__ == "__main__":
    main()
