import requests
import json

def test_api():
    url = "https://maya.tase.co.il/api/v1/reports/companies"
    
    # Try with dates
    payload = {
        "pageNumber": 1,
        "companyId": 1074,
        "limit": 50,
        "dateFrom": "2021-01-01T00:00:00",
        "dateTo": "2023-01-01T00:00:00"
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "X-Maya-With": "allow" # Sometimes needed custom header? Let's try minimal first.
    }
    
    print(f"POST {url}")
    print(f"Payload: {json.dumps(payload)}")
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            reports = data.get('reports', [])
            print(f"Found {len(reports)} reports")
            if reports:
                print("First report date:", reports[0].get('publishDate'))
                print("Last report date:", reports[-1].get('publishDate'))
        else:
            print("Response:", resp.text)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api()
