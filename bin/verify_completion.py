#!/usr/bin/env python3
import os
import sys

# Company definitions
COMPANIES = ["Sofwave", "Apollo"]

def check_company(company_key):
    # Mapping simplistic key to folder name suffix
    full_name = f"{company_key}_Medical" if company_key == "Sofwave" else f"{company_key}_Power"
    base_dir = f"downloads/{full_name}"
    
    memo = os.path.join(base_dir, "Investment_Memo.md")
    model = os.path.join(base_dir, "Financial_Model.csv")
    
    print(f"--- {company_key} ---")
    
    # Check Memo
    if os.path.exists(memo):
        size = os.path.getsize(memo)
        status = "✅ PASS" if size > 100 else "⚠️ EMPTY"
        print(f"Investment Memo: {status} ({size} bytes)")
    else:
        print(f"Investment Memo: ❌ MISSING")
        
    # Check Model
    if os.path.exists(model):
        size = os.path.getsize(model)
        status = "✅ PASS" if size > 100 else "⚠️ EMPTY"
        print(f"Financial Model: {status} ({size} bytes)")
    else:
        print(f"Financial Model: ❌ MISSING")
    print("")

def main():
    print("=== PIPELINE COMPLETION VERIFICATION ===\n")
    for c in COMPANIES:
        check_company(c)

if __name__ == "__main__":
    main()
