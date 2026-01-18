import requests
import json

def test_search_api():
    url = "https://maya.tase.co.il/api/v1/reports/search"
    
    # Payload guess based on company payload
    payload = {
        "PageNumber": 1,
        "CompanyId": 1074, # Apollo Power
        "DateFrom": "2021-01-01T00:00:00",
        "DateTo": "2023-12-31T23:59:59",
        "Limit": 50,
        "Sort": 2 # Date desc?
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "X-Maya-With": "allow",
        "Origin": "https://maya.tase.co.il",
        "Referer": "https://maya.tase.co.il/reports/search"
    }
    
    print(f"POST {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            reports = data.get('reports', [])
            print(f"Found {len(reports)} reports")
            if reports:
                print("First report:", reports[0].get('publishDate'), reports[0].get('title'))
        else:
            print("Response:", resp.text[:500])
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_search_api()
