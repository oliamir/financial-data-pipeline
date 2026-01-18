import requests
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "X-Maya-With": "1",
    "Referer": "https://maya.tase.co.il/"
}

company_id = "1082114" # Apollo Power

print(f"Testing API for Company {company_id}...\n")

# Attempt 1: GET /reports/company/{id}
url1 = f"https://maya.tase.co.il/api/v1/reports/company/{company_id}"
print(f"1. Trying GET {url1}")
try:
    r = requests.get(url1, headers=headers)
    if r.status_code == 200:
        data = r.json()
        print(f"   Success! Keys: {data.keys() if isinstance(data, dict) else 'List'}")
        if isinstance(data, dict) and 'reports' in data:
            print(f"   Refount count: {len(data['reports'])}")
            print(f"   First report: {data['reports'][0].get('title')}")
    else:
        print(f"   Failed: {r.status_code}")
except Exception as e:
    print(f"   Error: {e}")

# Attempt 2: POST /reports/companies (Known Payload Structure?)
url2 = "https://maya.tase.co.il/api/v1/reports/companies"
print(f"\n2. Trying POST {url2} (Guessing payload)")
payloads = [
    {"companyId": company_id, "pageNumber": 1},
    {"entityId": company_id, "pageNumber": 1},
    {"filter": {"companyId": company_id}, "pageNumber": 1},
    {"CompanyId": company_id}
]

for p in payloads:
    print(f"   Payload: {p}")
    try:
        r = requests.post(url2, json=p, headers=headers)
        if r.status_code == 200:
            data = r.json()
            is_list = isinstance(data, list)
            count = len(data) if is_list else len(data.get('reports', []))
            print(f"   -> Status 200. Items: {count}")
        else:
            print(f"   -> Status {r.status_code}")
    except Exception as e:
        print(f"   Error: {e}")
