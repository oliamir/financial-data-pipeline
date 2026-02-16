#!/usr/bin/env python3
"""
Test script for the financial extraction pipeline.
Tests extraction on a single known Sofwave PDF.

Usage:
  cd "My Drive/Apps/finance"
  ./venv/bin/python3 code/tests/test_extraction.py
"""

import sys
import os
import json
from pathlib import Path

# Add src to path
src_path = str(Path(__file__).parent.parent / "src")
sys.path.insert(0, src_path)

from dotenv import load_dotenv
load_dotenv()

from intelligence.llm_client import LLMClient
from intelligence.classifier import DocumentClassifier, DocumentType
from intelligence.extractor import FinancialExtractor

# Config
TEST_PDF = "output/Sofwave_Medical/2025/Annual_FINANCIAL/2025_Annual_FINANCIAL_TASE_Maya_1649271.pdf"

def test_llm_client_init():
    """Test that LLM client initializes without errors."""
    print("Test 1: LLM Client Initialization...")
    client = LLMClient(provider="google")
    assert client.google_client is not None, "Google client should be initialized"
    assert client.keys["google"] is not None, "GOOGLE_API_KEY should be set"
    print("  ✓ LLM Client initialized successfully")
    return client

def test_classifier(client):
    """Test classifier on known financial report."""
    print("\nTest 2: Document Classification...")
    classifier = DocumentClassifier(client)
    
    # This file has _FINANCIAL in the name so it should use the fast path
    doc_type = classifier.classify(TEST_PDF)
    assert doc_type == DocumentType.FINANCIAL_REPORT, f"Expected FINANCIAL_REPORT, got {doc_type.value}"
    print(f"  ✓ Classified as: {doc_type.value}")

def test_extraction(client):
    """Test financial extraction on known financial report."""
    print("\nTest 3: Financial Data Extraction...")
    extractor = FinancialExtractor(client)
    
    result = extractor.extract_financials(TEST_PDF, model_name="gemini-2.0-flash")
    
    # Check for errors
    if "error" in result:
        print(f"  ✗ Extraction failed: {result['error'][:200]}")
        return False
    
    # Print the extracted data
    print(f"\n  Extracted data:")
    print(f"  Period: {result.get('period', 'N/A')}")
    print(f"  Currency: {result.get('currency', 'N/A')}")
    print(f"  Units: {result.get('units', 'N/A')}")
    
    for section in ["income_statement", "balance_sheet", "cash_flow"]:
        if section in result and isinstance(result[section], dict):
            print(f"\n  {section.upper().replace('_', ' ')}:")
            for key, val in result[section].items():
                indicator = "✓" if val is not None else "○"
                val_str = f"{val:,.0f}" if isinstance(val, (int, float)) and val is not None else str(val)
                print(f"    {indicator} {key}: {val_str}")
    
    # Validate structure
    is_valid = extractor.is_extraction_valid(result)
    
    count = 0
    for section in ["income_statement", "balance_sheet", "cash_flow"]:
        if section in result and isinstance(result[section], dict):
            for val in result[section].values():
                if val is not None:
                    count += 1
    
    print(f"\n  Total data points: {count}")
    print(f"  Valid extraction: {'✓' if is_valid else '✗'}")
    
    if is_valid:
        print("  ✓ Extraction test PASSED")
    else:
        print("  ✗ Extraction test FAILED (insufficient data points)")
    
    return is_valid

def test_json_validation():
    """Test JSON validation logic standalone."""
    print("\nTest 4: JSON Validation Logic...")
    client = LLMClient(provider="google")
    extractor = FinancialExtractor(client)
    
    # Test with valid data
    valid_data = {
        "period": "2025 Annual",
        "income_statement": {"revenue": 100000, "gross_profit": 50000, "operating_income": -20000, "net_income": -25000, "earnings_per_share": -1.5},
        "balance_sheet": {"total_assets": 300000, "total_liabilities": 100000, "total_equity": 200000, "cash_and_equivalents": 150000},
        "cash_flow": {"operating_cash_flow": -15000, "investing_cash_flow": -5000, "financing_cash_flow": 80000}
    }
    assert extractor.is_extraction_valid(valid_data), "Valid data should pass"
    
    # Test with garbage data
    garbage = {"error": "could not extract"}
    assert not extractor.is_extraction_valid(garbage), "Garbage should fail"
    
    # Test with mixed string/number data (common LLM issue)
    mixed = {
        "income_statement": {"revenue": "100,000", "gross_profit": None, "operating_income": None, "net_income": None, "earnings_per_share": None},
        "balance_sheet": {"total_assets": "unknown", "total_liabilities": None, "total_equity": None, "cash_and_equivalents": None},
        "cash_flow": {"operating_cash_flow": None, "investing_cash_flow": None, "financing_cash_flow": None}
    }
    cleaned = extractor._validate_and_clean(mixed)
    assert cleaned["income_statement"]["revenue"] == 100000.0, f"Should parse '100,000' to 100000.0, got {cleaned['income_statement']['revenue']}"
    assert cleaned["balance_sheet"]["total_assets"] is None, "Should set 'unknown' to None"
    
    print("  ✓ JSON validation tests PASSED")

if __name__ == "__main__":
    print("=" * 60)
    print("FINANCIAL EXTRACTION PIPELINE TEST")
    print("=" * 60)
    
    if not os.path.exists(TEST_PDF):
        print(f"\n⚠ Test PDF not found: {TEST_PDF}")
        print("Make sure you run this from the finance project root directory.")
        sys.exit(1)
    
    try:
        # Test 1: Init
        client = test_llm_client_init()
        
        # Test 2: Classifier (no API call needed for _FINANCIAL files)
        test_classifier(client)
        
        # Test 3: JSON Validation (no API needed)
        test_json_validation()
        
        # Test 4: Full extraction (requires API)
        print("\n" + "-" * 60)
        print("Note: The extraction test requires an active Gemini API key.")
        print("If rate-limited, wait and retry.")
        print("-" * 60)
        
        result = test_extraction(client)
        
        print("\n" + "=" * 60)
        if result:
            print("ALL TESTS PASSED ✓")
        else:
            print("EXTRACTION TEST FAILED — check rate limits or API key")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\nInterrupted.")
    except Exception as e:
        print(f"\n✗ Test error: {e}")
        import traceback
        traceback.print_exc()
