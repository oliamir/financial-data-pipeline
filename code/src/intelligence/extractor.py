from .llm_client import LLMClient
import json
import os
import re

class FinancialExtractor:
    REQUIRED_KEYS = ["period", "income_statement", "balance_sheet", "cash_flow"]
    NUMERIC_FIELDS = {
        "income_statement": ["revenue", "gross_profit", "operating_income", "net_income", "earnings_per_share"],
        "balance_sheet": ["total_assets", "total_liabilities", "total_equity", "cash_and_equivalents"],
        "cash_flow": ["operating_cash_flow", "investing_cash_flow", "financing_cash_flow"]
    }

    # Keywords that indicate financial table pages (Hebrew + English)
    FINANCIAL_TABLE_KEYWORDS = [
        # Hebrew keywords for financial statements
        'תוסנכה', 'דספה', 'חוור', 'םיסכנ', 'תויובייחתה', 'ןוה',
        'םינמוזמ', 'יפסכה בצמה', 'ימירזת', 'ללוכה דספהה',
        # English keywords
        'revenue', 'income', 'loss', 'assets', 'liabilities', 'equity',
        'cash flow', 'consolidated', 'balance sheet', 'total assets',
        'financial position', 'comprehensive loss'
    ]

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def _extract_financial_pages(self, file_path: str, max_chars: int = 12000) -> str:
        """Extract only the pages containing financial tables from a PDF.
        
        Strategy: Find pages with many numbers AND financial keywords,
        prioritizing the consolidated financial statements section.
        """
        try:
            import pdfplumber
        except ImportError:
            # Fallback: read raw text
            with open(file_path, 'r', errors='ignore') as f:
                return f.read()[:max_chars]
        
        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)
            
            # Score each page for financial content
            scored_pages = []
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ''
                if len(text.strip()) < 50:
                    continue
                
                score = 0
                
                # Count numbers (financial tables have many)
                numbers = re.findall(r'[\d,]{3,}', text)
                score += min(len(numbers), 20)  # cap at 20
                
                # Check for financial keywords (case insensitive for English)
                text_lower = text.lower()
                for kw in self.FINANCIAL_TABLE_KEYWORDS:
                    if kw in text or kw in text_lower:
                        score += 5
                
                # Bonus for pages in the latter half (financial statements are usually there)
                if i > total_pages * 0.5:
                    score += 3
                
                # Bonus for pages with table-like structure (tab/space separated numbers)
                if len(re.findall(r'\d+\s+\d+', text)) > 3:
                    score += 8
                
                if score > 10:  # threshold
                    scored_pages.append((score, i, text))
            
            # Sort by score (descending) and take top pages
            scored_pages.sort(key=lambda x: -x[0])
            
            # Take pages by order of appearance (for coherence), limited by char budget
            selected_indices = sorted([p[1] for p in scored_pages[:15]])
            
            result = ""
            for idx in selected_indices:
                text = pdf.pages[idx].extract_text() or ''
                if len(result) + len(text) > max_chars:
                    break
                result += f"\n=== Page {idx+1} of {total_pages} ===\n{text}\n"
            
            if not result:
                # Fallback: just get the last 30% of pages (where financials usually are)
                start_page = int(total_pages * 0.6)
                for i in range(start_page, total_pages):
                    text = pdf.pages[i].extract_text() or ''
                    if len(result) + len(text) > max_chars:
                        break
                    result += f"\n=== Page {i+1} ===\n{text}\n"
            
            return result

    def extract_financials(self, file_path: str, model_name: str = "gemini-2.0-flash") -> dict:
        print(f"Extracting financials from {os.path.basename(file_path)}...")
        
        # Check if we're using Ollama (needs text extraction) or Google (can read PDFs natively)
        provider = self.llm.active_provider
        
        if provider == "google" and self.llm.google_client:
            # Google Gemini can read PDFs natively
            return self._extract_with_native_pdf(file_path, model_name)
        else:
            # Ollama/others need text extraction
            return self._extract_with_text(file_path, model_name)
    
    def _extract_with_native_pdf(self, file_path: str, model_name: str) -> dict:
        """Use Google Gemini's native PDF reading capability."""
        file_ref = self.llm.upload_file(file_path)
        response_text = self.llm.prompt_with_file(file_ref, self._get_prompt(), model_name=model_name)
        return self._parse_response(response_text)
    
    def _extract_with_text(self, file_path: str, model_name: str) -> dict:
        """Extract text from PDF and send to LLM (for Ollama/local models)."""
        print(f"  → Extracting financial pages from PDF...")
        text = self._extract_financial_pages(file_path, max_chars=10000)
        
        if not text.strip():
            return {"error": "Could not extract text from PDF"}
        
        char_count = len(text)
        print(f"  → Extracted {char_count} chars of financial content")
        
        prompt = f"""DOCUMENT CONTENT (financial report filed with Tel Aviv Stock Exchange):

{text}

{self._get_prompt()}"""
        
        # Use direct Ollama call with sufficient context
        try:
            import ollama
            response = ollama.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                options={
                    'num_ctx': 16384,  # Increase context window
                    'temperature': 0.1,  # Low temperature for precise extraction
                }
            )
            response_text = response['message']['content']
            return self._parse_response(response_text)
        except ImportError:
            # Fallback to LLM client
            file_ref = {"path": file_path}
            response_text = self.llm.prompt_with_file(file_ref, self._get_prompt(), model_name=model_name)
            return self._parse_response(response_text)

    def _get_prompt(self) -> str:
        return """You are an expert financial analyst specializing in Israeli public company filings.

This is a financial report filed with the Tel Aviv Stock Exchange (TASE). It may be in Hebrew, 
English, or both. Find the CONSOLIDATED FINANCIAL STATEMENTS and extract the key metrics.

IMPORTANT:
- Look for actual financial tables (income statement, balance sheet, cash flow statement)
- Numbers are typically in thousands (אלפי) of U.S. dollars or NIS
- Hebrew key terms: תוסנכה=Revenue, דספה/חוור=Loss/Profit, םיסכנ=Assets, תויובייחתה=Liabilities, 
  ןוה=Equity, םינמוזמ=Cash, ימירזת=Cash flows
- If a value is not found, use null
- Return ONLY valid JSON — no comments, no trailing commas

Return this EXACT JSON structure:
{
    "period": "Q1 2025",
    "currency": "USD" or "ILS",
    "units": "thousands",
    "income_statement": {
        "revenue": <number or null>,
        "gross_profit": <number or null>,
        "operating_income": <number or null>,
        "net_income": <number or null>,
        "earnings_per_share": <number or null>
    },
    "balance_sheet": {
        "total_assets": <number or null>,
        "total_liabilities": <number or null>,
        "total_equity": <number or null>,
        "cash_and_equivalents": <number or null>
    },
    "cash_flow": {
        "operating_cash_flow": <number or null>,
        "investing_cash_flow": <number or null>,
        "financing_cash_flow": <number or null>
    }
}

Return ONLY the JSON object."""

    def _fix_json_numbers(self, json_str: str) -> str:
        """Fix common LLM JSON issues: comma-separated numbers and accounting notation."""
        # Fix accounting notation: (1,234) → -1234
        json_str = re.sub(r'\((\d[\d,]*)\)', lambda m: '-' + m.group(1).replace(',', ''), json_str)
        
        # Fix comma-separated numbers in JSON values: "revenue": 43,536 → "revenue": 43536
        # Match numbers with commas that appear as JSON values (after : and optional whitespace)
        json_str = re.sub(r':\s*(-?\d{1,3}(?:,\d{3})+)(?=[,\s\n\r}])', 
                          lambda m: ': ' + m.group(1).replace(',', ''), json_str)
        
        return json_str

    def _parse_response(self, response_text: str) -> dict:
        """Parse and validate the LLM's JSON response."""
        try:
            json_str = response_text
            
            # Handle markdown code blocks
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]
            
            # Find JSON boundaries
            start = json_str.find('{')
            end = json_str.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = json_str[start:end]
            
            # Remove JavaScript-style comments
            json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
            
            # Fix common LLM number formatting issues
            json_str = self._fix_json_numbers(json_str)
            
            data = json.loads(json_str)
            data = self._validate_and_clean(data)
            return data
            
        except json.JSONDecodeError as e:
            print(f"  ⚠ JSON parse error: {e}")
            print(f"  Raw response (first 300 chars): {response_text[:300]}")
            return {"error": f"JSON parse error: {e}", "raw_response": response_text[:500]}
        except Exception as e:
            print(f"  ⚠ Extraction error: {e}")
            return {"error": str(e)}

    def _validate_and_clean(self, data: dict) -> dict:
        """Validate extracted data: ensure numeric fields are numbers or null."""
        for section, fields in self.NUMERIC_FIELDS.items():
            if section not in data:
                data[section] = {f: None for f in fields}
                continue
            
            for field in fields:
                value = data[section].get(field)
                if value is None:
                    continue
                
                if isinstance(value, str):
                    cleaned = value.replace(",", "").replace(" ", "").replace("%", "").strip()
                    try:
                        data[section][field] = float(cleaned)
                    except (ValueError, TypeError):
                        print(f"  ⚠ Non-numeric value for {section}.{field}: '{value}' → null")
                        data[section][field] = None
                elif not isinstance(value, (int, float)):
                    data[section][field] = None
        
        return data

    def is_extraction_valid(self, data: dict) -> bool:
        """Check if extraction produced at least some real financial data."""
        if "error" in data:
            return False
        
        count = 0
        for section, fields in self.NUMERIC_FIELDS.items():
            if section in data:
                for field in fields:
                    if data[section].get(field) is not None:
                        count += 1
        
        return count >= 3
