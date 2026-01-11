#!/usr/bin/env python3
import os
import subprocess
from datetime import datetime
from dotenv import load_dotenv

# Load env to check keys
load_dotenv()

def get_file_count(path):
    try:
        if not os.path.exists(path): return 0
        return int(subprocess.check_output(f"find '{path}' -type f | wc -l", shell=True))
    except:
        return 0

def get_process_status(company):
    try:
        cmd = f"ps -ef | grep 'company {company}' | grep -v grep | grep -v check_status"
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
    return mtime.strftime("%Y-%m-%d %H:%M:%S")

def main():
    companies = [
        {"name": "Sofwave", "dir": "downloads/Sofwave_Medical"},
        {"name": "Apollo", "dir": "downloads/Apollo_Power"}
    ]
    
    # Check keys
    has_google = bool(os.getenv("GOOGLE_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    
    # Check Ollama
    try:
        import requests
        resp = requests.get("http://localhost:11434")
        has_ollama = resp.status_code == 200
    except:
        has_ollama = False
    
    print(f"\n=== PIPELINE STATUS SNAPSHOT ===")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"Keys: Google: {'✅' if has_google else '❌'} | Anthropic: {'✅' if has_anthropic else '❌'} | OpenAI: {'✅' if has_openai else '❌'} | Ollama: {'✅' if has_ollama else '❌'}")
    if not any([has_anthropic, has_openai, has_ollama]):
        print("⚠️  WARNING: No fallback provider found. Pipeline may stall on Google 429.")
    print("="*80)
    print(f"{'COMPANY':<15} | {'STATUS':<15} | {'FILES':<8} | {'LAST MEMO':<20}")
    print("-" * 80)
    
    for c in companies:
        status = get_process_status(c["name"])
        files = get_file_count(c["dir"])
        
        real_name = "Sofwave Medical" if "Sofwave" in c["name"] else "Apollo Power"
        memo_path = os.path.join("downloads", real_name, "Investment_Memo.md")
        
        last_memo = get_last_modified(memo_path)
        
        print(f"{c['name']:<15} | {status:<15} | {files:<8} | {last_memo:<20}")
        
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
