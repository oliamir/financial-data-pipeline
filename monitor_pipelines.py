#!/usr/bin/env python3
"""
Pipeline Monitor
Checks every 30 minutes if the pipelines for Sofwave and Apollo are running.
If not, restarts them.
"""

import time
import subprocess
import os
import sys
from datetime import datetime

CHECK_INTERVAL = 30 * 60  # 30 minutes
COMPANIES = ["Sofwave", "Apollo"]

def is_pipeline_running(company):
    """Check if run_pipeline.py is running for the specific company."""
    try:
        # Search for process matching the company argument
        # We exclude the grep process itself and this monitor script
        cmd = f"ps -ef | grep 'run_pipeline.py' | grep '{company}' | grep -v grep"
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0
    except Exception as e:
        print(f"Error checking process status: {e}")
        return False

def restart_pipeline(company):
    """Start the pipeline for the company in the background."""
    print(f"[{datetime.now()}] Restarting pipeline for {company}...")
    
    # Path to venv python
    python_exe = "./venv/bin/python3"
    if not os.path.exists(python_exe):
        python_exe = sys.executable
        
    cmd = [python_exe, "run_pipeline.py", "--company", company]
    
    # We use Popen to start it detached/background
    try:
        log_file = open(f"pipeline_{company}.log", "a")
        subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True 
        )
        print(f"[{datetime.now()}] ✓ Started {company} pipeline")
    except Exception as e:
        print(f"[{datetime.now()}] ⚠ Failed to start {company}: {e}")

def main():
    print(f"[{datetime.now()}] Starting Pipeline Monitor")
    print(f"Monitoring companies: {', '.join(COMPANIES)}")
    print(f"Check interval: {CHECK_INTERVAL} seconds")
    
    while True:
        print(f"\n[{datetime.now()}] Performing status check...")
        
        for company in COMPANIES:
            if is_pipeline_running(company):
                print(f"  ✓ {company}: Running")
            else:
                print(f"  ⚠ {company}: Not running. Restarting...")
                restart_pipeline(company)
        
        print(f"Sleeping for {CHECK_INTERVAL/60} minutes...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
