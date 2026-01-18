import requests
import json

def get_company_id(name):
    # Try TASE Autocomplete API
    url = f"https://maya.tase.co.il/api/company/search?lang=en-US&term={name}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
        "Referer": "https://maya.tase.co.il/"
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Returns list of {value: "720", label: "Enlight Energy"}
            return data
        else:
            print(f"Error {response.status_code} for {name}")
            return None
    except Exception as e:
        print(f"Exception for {name}: {e}")
        return None

companies = [
    "Sofwave"
]

results = {}
for company in companies:
    print(f"Searching for {company}...")
    res = get_company_id(company)
    if res:
        print(f"  Found: {res}")
        results[company] = res
    else:
        print(f"  No result for {company}")

print("\n--- Consolidated List ---")
for k, v in results.items():
    print(f"{k}: {v}")
