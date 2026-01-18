#!/usr/bin/env python3
import os
import re
from datetime import datetime

# Log files
LOGS = {
    "Llama (Apollo)": "pipeline_Apollo.log",
    "DeepSeek (Sofwave)": "pipeline_Sofwave.log"
}

def analyze_log(name, path):
    if not os.path.exists(path):
        return {"name": name, "status": "No Log", "speed": 0, "processed": 0}
        
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        
    # Count "Processing: ..." lines
    processed_count = content.count("Processing: ")
    
    # Estimate time
    # Find timestamps (if available) - Standard logger format helps, but capturing stdout might not have standard timestamps
    # We'll use file creation vs modification time as a rough proxy for "Runtime" so far
    try:
        stats = os.stat(path)
        duration_hrs = (stats.st_mtime - stats.st_birthtime) / 3600.0
        if duration_hrs < 0.01: duration_hrs = 0.01
    except:
        duration_hrs = 1.0 # Fallback
        
    speed = processed_count / duration_hrs
    
    return {
        "name": name,
        "processed": processed_count,
        "duration_hrs": duration_hrs,
        "speed": round(speed, 1)
    }

def main():
    print("=== MODEL PERFORMANCE BENCHMARK ===\n")
    print(f"{'MODEL':<20} | {'DOCS':<6} | {'TIME(h)':<8} | {'SPEED (docs/hr)':<15}")
    print("-" * 60)
    
    results = []
    for name, path in LOGS.items():
        res = analyze_log(name, path)
        results.append(res)
        print(f"{res['name']:<20} | {res['processed']:<6} | {res['duration_hrs']:.2f}     | {res['speed']:<15}")
        
    print("-" * 60)
    
    # Recommendation
    winner = max(results, key=lambda x: x['speed'])
    print(f"\n🏆 Fastest Model: {winner['name']}")
    print(f"Recommendation: Use {winner['name']} for large-scale processing if accuracy is comparable.")

if __name__ == "__main__":
    main()
