#!/usr/bin/env python3
import os
import time
import subprocess
from datetime import datetime


def get_progress_stats(base_path):
    if not os.path.exists(base_path): return 0, 0
    
    total = 0
    processed = 0
    
    for root, dirs, files in os.walk(base_path):
        # Determine if this directory is a "processed" category
        is_processed_dir = os.path.basename(root) in ["Financials", "Others"]
        
        for file in files:
            if file.startswith(".") or file in ["Financial_Model.csv", "Investment_Memo.md"]: continue
            
            total += 1
            if is_processed_dir:
                processed += 1
                
    return processed, total

def get_process_status(company):
    try:
        # Check for run_pipeline or specific sub-scripts
        cmd = f"ps -ef | grep 'company {company}' | grep -v grep"
        output = subprocess.check_output(cmd, shell=True).decode()
        if "analyze.py" in output: return "ANALYZING 🧠"
        if "download.py" in output: return "DOWNLOADING ⬇️"
        if "run_pipeline.py" in output: return "RUNNING 🏃"
        return "STOPPED 🛑"
    except:
        return "STOPPED 🛑"

def get_last_modified(path):
    if not os.path.exists(path): return "Never"
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    return mtime.strftime("%H:%M:%S")

def clear():
    if os.environ.get('TERM'):
        os.system('cls' if os.name == 'nt' else 'clear')
    else:
        print("\n" * 2)

def main():
    companies = [
        {"name": "Sofwave", "dir": "output/Sofwave_Medical"},
        {"name": "Apollo", "dir": "output/Apollo_Power"}
    ]
    
    while True:
        clear()
        print(f"=== PIPELINE STATUS DASHBOARD ===", flush=True)
        print(f"Time: {datetime.now().strftime('%H:%M:%S')}", flush=True)
        print("="*60, flush=True)
        print(f"{'COMPANY':<15} | {'STATUS':<15} | {'PROGRESS':<12} | {'LAST MEMO':<10}", flush=True)
        print("-" * 60, flush=True)
        
        for c in companies:
            status = get_process_status(c["name"])
            processed, total = get_progress_stats(c["dir"])
            memo_path = os.path.join(c["dir"], "..", c["name"].replace("_", " ") if "Medical" in c["dir"] else "Apollo Power", "Investment_Memo.md")
            
            # Heuristic for memo path - straightforward check
            real_memo_path = None
            possible_dirs = [d for d in os.listdir("output") if c["name"].replace("_"," ") in d.replace("_"," ")]
            if possible_dirs:
                real_memo_path = os.path.join("output", possible_dirs[0], "Investment_Memo.md")
            
            last_memo = get_last_modified(real_memo_path) if real_memo_path else "N/A"
            
            progress_str = f"{processed} / {total}"
            print(f"{c['name']:<15} | {status:<15} | {progress_str:<12} | {last_memo:<10}", flush=True)
            
        print("="*60, flush=True)
        print("Press Ctrl+C to exit", flush=True)
        time.sleep(5)

if __name__ == "__main__":
    main()
