import json
import time
import requests
from pathlib import Path

UNIVERSE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "universe.json"

def enrich_companies():
    if not UNIVERSE_PATH.exists():
        print("universe.json not found.")
        return
        
    data = json.loads(UNIVERSE_PATH.read_text("utf-8"))
    print(f"Loaded {len(data)} companies for enrichment.")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "X-Maya-With": "B"
    }
    
    updated = 0
    
    for i, c in enumerate(data):
        # Only enrich if we don't already have ticker/hebrew name
        if c.get("ticker"):
            continue
            
        name = c["name"]
        try:
            res = requests.get(f"https://mayaapi.tase.co.il/api/company/search?q={name}", headers=headers, timeout=5)
            if res.status_code == 200:
                results = res.json()
                if results and isinstance(results, list):
                    # We usually want the first element as it's the exact match
                    match = results[0]
                    c["name_he"] = match.get("CompanyName", "")
                    c["ticker"] = match.get("Symbol", "")
                    updated += 1
                    print(f"[{i+1}/{len(data)}] Found {name}: {c['ticker']} | {c['name_he']}")
                else:
                    print(f"[{i+1}/{len(data)}] No results for {name}")
            else:
                print(f"[{i+1}/{len(data)}] HTTP {res.status_code} for {name}")
        except Exception as e:
            print(f"[{i+1}/{len(data)}] Error for {name}: {e}")
            
        time.sleep(0.5) # Be kind to the API
        
        if updated % 20 == 0 and updated > 0:
            UNIVERSE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
            
    print(f"\nFinished finding data for {updated} companies.")
    UNIVERSE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")

if __name__ == "__main__":
    enrich_companies()
