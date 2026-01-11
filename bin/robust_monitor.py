#!/usr/bin/env python3
import time
import subprocess
import os
import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    filename='logs/monitor_restarts.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Queue Configuration: [Company, Provider, Model, NoFallback]
# Priority 1: Sofwave (DeepSeek)
# Priority 2: Apollo (Llama)
QUEUE = [
    {"company": "Sofwave", "provider": "ollama", "model": "deepseek-r1:8b", "no_fallback": True},
    {"company": "Apollo", "provider": "ollama", "model": "llama3.1", "no_fallback": False}
]

def get_running_process():
    """Returns dict of currently running analyze.py process info or None"""
    try:
        cmd = "ps -ef | grep 'analyze.py' | grep -v grep"
        output = subprocess.check_output(cmd, shell=True).decode().strip()
        if not output:
            return None
            
        process_lines = output.split('\n')
        # Just grab the first one
        line = process_lines[0]
        pid = line.split()[1]
        
        company = "Unknown"
        if "--company Sofwave" in line: company = "Sofwave"
        elif "--company Apollo" in line: company = "Apollo"
        
        return {"pid": pid, "company": company, "line": line}
    except subprocess.CalledProcessError:
        return None

def is_job_complete(company):
    """Checks if job is complete by verify_completion logic (simplified)"""
    # Simply check if Investment_Memo.md and Financial_Model.csv exist and are non-empty
    base_dir = f"downloads/{company}_Medical" if company == "Sofwave" else f"downloads/{company}_Power"
    
    memo_path = os.path.join(base_dir, "Investment_Memo.md")
    model_path = os.path.join(base_dir, "Financial_Model.csv")
    
    # Heuristic: If Financial Model exists, we assume it's mostly done or far enough
    # If not, we assume it needs to run.
    if os.path.exists(model_path) and os.path.getsize(model_path) > 100:
        return True
    
    return False

def get_last_log_update(company):
    log_file = f"logs/pipeline_{company}.log"
    if not os.path.exists(log_file):
        return 0
    return os.path.getmtime(log_file)

def start_job(job_config):
    venv_python = "./venv/bin/python3"
    if not os.path.exists(venv_python):
        venv_python = sys.executable
        
    cmd = [
        venv_python, "bin/run_pipeline.py",
        "--company", job_config["company"],
        "--provider", job_config["provider"],
        "--model", job_config["model"]
    ]
    if job_config["no_fallback"]:
        cmd.append("--no-fallback")
        
    log_path = f"logs/pipeline_{job_config['company']}.log"
    log_file = open(log_path, "a")
    log_file.write(f"\n\n=== MONITOR RESTART: {datetime.now()} ===\n")
    
    print(f"Starting {job_config['company']} ({job_config['model']})...")
    logging.info(f"Starting job: {job_config['company']}")
    
    subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=log_file,
        start_new_session=True
    )

def kill_process(pid):
    try:
        os.kill(int(pid), 9)
        logging.info(f"Killed process {pid}")
    except:
        pass

def main():
    print("=== ROBUST SEQUENTIAL MONITOR STARTING ===")
    print(f"Queue: {[j['company'] for j in QUEUE]}")
    
    while True:
        try:
            current_proc = get_running_process()
            
            # 1. If process is running
            if current_proc:
                company = current_proc["company"]
                # Check for stall
                last_update = get_last_log_update(company)
                time_since_update = time.time() - last_update
                
                # Check priority conflict?
                # If Apollo is running but Sofwave is incomplete, we should kill Apollo (Sequence Enforcement)
                # QUEUE[0] is highest priority.
                
                top_priority_job = QUEUE[0]
                if top_priority_job["company"] != company and not is_job_complete(top_priority_job["company"]):
                     print(f"Priority Conflict! {company} is running, but {top_priority_job['company']} is waiting.")
                     logging.info(f"Killing {company} to prioritize {top_priority_job['company']}")
                     kill_process(current_proc["pid"])
                     time.sleep(2)
                     continue # Next loop will start priority job

                # Stall check (10 mins = 600s)
                if time_since_update > 600:
                    print(f"STALL DETECTED: {company} (Last update {int(time_since_update)}s ago)")
                    logging.warning(f"Stall detected for {company}. Restarting...")
                    kill_process(current_proc["pid"])
                    time.sleep(2)
                    continue
                
                # If healthy and correct priority -> Wait
                # print(f"Monitoring {company}... (Healthy)")
                
            # 2. If NO process is running
            else:
                # Find Next Job
                job_to_run = None
                for job in QUEUE:
                    if not is_job_complete(job["company"]):
                        job_to_run = job
                        break
                
                if job_to_run:
                    print(f"Queue Processing: Starting {job_to_run['company']}")
                    start_job(job_to_run)
                else:
                    print("All jobs complete! Sleeping...")
            
            time.sleep(30) # Check every 30s
            
        except Exception as e:
            print(f"Monitor Loop Error: {e}")
            logging.error(f"Loop error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
