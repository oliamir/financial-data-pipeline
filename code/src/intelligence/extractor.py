from .llm_client import LLMClient
import json
import os

class FinancialExtractor:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def extract_financials(self, file_path: str, model_name: str = "gemini-3-flash-preview") -> dict:
        print(f"Extracting financials from {os.path.basename(file_path)}...")
        file_ref = self.llm.upload_file(file_path)
        
        prompt = """
        You are an expert financial analyst. Extract the consolidated financial statements from this PDF.
        Specifically, return a JSON object with the following structure:
        {
            "period": "Q3 2024", 
            "income_statement": {
                "revenue": <number>,
                "gross_profit": <number>,
                "operating_income": <number>,
                "net_income": <number>,
                "earnings_per_share": <number>
            },
            "balance_sheet": {
                "total_assets": <number>,
                "total_liabilities": <number>,
                "total_equity": <number>,
                "cash_and_equivalents": <number>
            },
            "cash_flow": {
                "operating_cash_flow": <number>,
                "investing_cash_flow": <number>,
                "financing_cash_flow": <number>
            }
        }
        
        If specific numbers are missing, use null. Ensure numbers are in THOUSANDS if the report uses thousands, but normalize to the actual value if possible or just state the unit. 
        PREFER: Normalize to absolute units (e.g. 1000000) if clear, otherwise keep as in report.
        """
        
        response_text = self.llm.prompt_with_file(file_ref, prompt, model_name=model_name)
        
        # Clean JSON
        try:
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            json_str = response_text[start:end]
            return json.loads(json_str)
        except Exception as e:
            print(f"Error parsing JSON from LLM: {e}")
            return {"error": response_text}
