#!/usr/bin/env python3
import os
import time
import subprocess
from datetime import datetime

def get_file_count(path):
    try:
        if not os.path.exists(path): return 0
        return int(subprocess.check_output(f"find '{path}' -type f | wc -l", shell=True))
    except:
        return 0

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
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    companies = [
        {"name": "Sofwave", "dir": "downloads/Sofwave_Medical"},
        {"name": "Apollo", "dir": "downloads/Apollo_Power"}
    ]
    
    while True:
        clear()
        print(f"=== PIPELINE STATUS DASHBOARD ===")
        print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
        print("="*60)
        print(f"{'COMPANY':<15} | {'STATUS':<15} | {'FILES':<8} | {'LAST MEMO':<10}")
        print("-" * 60)
        
        for c in companies:
            status = get_process_status(c["name"])
            files = get_file_count(c["dir"])
            memo_path = os.path.join(c["dir"], "..", c["name"].replace("_", " ") if "Medical" in c["dir"] else "Apollo Power", "Investment_Memo.md")
            # Heuristic for memo path - straightforward check
            real_memo_path = None
            # Find probable memo path
            possible_dirs = [d for d in os.listdir("downloads") if c["name"].replace("_"," ") in d.replace("_"," ")]
            if possible_dirs:
                real_memo_path = os.path.join("downloads", possible_dirs[0], "Investment_Memo.md")
            
            last_memo = get_last_modified(real_memo_path) if real_memo_path else "N/A"
            
            print(f"{c['name']:<15} | {status:<15} | {files:<8} | {last_memo:<10}")
            
        print("="*60)
        print("Press Ctrl+C to exit")
        time.sleep(5)

if __name__ == "__main__":
    main()
