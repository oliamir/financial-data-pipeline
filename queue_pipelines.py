#!/usr/bin/env python3
import time
import subprocess
import os
import sys
from datetime import datetime

def is_apollo_running():
    try:
        # Check for analyze.py with Apollo arg
        cmd = "ps -ef | grep 'analyze.py' | grep 'Apollo' | grep -v grep"
        output = subprocess.check_output(cmd, shell=True).decode().strip()
        return bool(output)
    except subprocess.CalledProcessError:
        return False

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] === PIPELINE QUEUE MANAGER ===")
    print("Waiting for Apollo pipeline to finish...")
    
    # 1. Wait for Apollo
    while is_apollo_running():
        time.sleep(10)
        # Optional: Print a dot or heartbeat every minute?
        # print(".", end="", flush=True)
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Apollo finished (or not found). Starting Sofwave...")
    
    # 2. Start Sofwave
    # Command: run_pipeline.py --company Sofwave --provider ollama --model deepseek-r1:8b --no-fallback
    
    venv_python = "./venv/bin/python3"
    if not os.path.exists(venv_python):
        venv_python = sys.executable
        
    cmd = [
        venv_python, "run_pipeline.py",
        "--company", "Sofwave",
        "--provider", "ollama",
        "--model", "deepseek-r1:8b",
        "--no-fallback"
    ]
    
    log_file = open("pipeline_Sofwave.log", "a")
    log_file.write(f"\n\n=== STARTING QUEUED RUN: {datetime.now()} ===\n")
    
    try:
        subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True
        )
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Sofwave started with deepseek-r1:8b")
        print("Check 'pipeline_Sofwave.log' for output.")
        
    except Exception as e:
        print(f"Error starting Sofwave: {e}")

if __name__ == "__main__":
    main()
