from enum import Enum
from .llm_client import LLMClient
import os

class DocumentType(Enum):
    FINANCIAL_REPORT = "Financial Report"
    PRESENTATION = "Presentation"
    IMMEDIATE_REPORT = "Immediate Report"
    LEGAL_DOCUMENT = "Legal Document"
    OTHER = "Other"

class DocumentClassifier:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def classify(self, file_path: str, model_name: str = "gemini-3-flash-preview") -> DocumentType:
        print(f"Classifying {os.path.basename(file_path)}...")
        
        # Simple heuristic check first
        fname = os.path.basename(file_path).lower()
        if "presentation" in fname or " מצגת" in fname:
            return DocumentType.PRESENTATION
            
        file_ref = self.llm.upload_file(file_path)
        
        prompt = """
        Analyze this document and classify it into one of the following categories:
        1. FINANCIAL_REPORT (Quarterly/Annual financial statements, balance sheets, results)
        2. PRESENTATION (Investor presentation, deck, slides)
        3. IMMEDIATE_REPORT (Material event, meeting results, appointment of officers)
        4. LEGAL_DOCUMENT (Voting deed, bylaws, official certificates)
        5. OTHER
        
        Return ONLY the category name.
        """
        
        response = self.llm.prompt_with_file(file_ref, prompt, model_name=model_name)
        text = response.strip().upper().replace(" ", "_")
        
        # Map response to Enum
        if "FINANCIAL" in text: return DocumentType.FINANCIAL_REPORT
        if "PRESENTATION" in text: return DocumentType.PRESENTATION
        if "IMMEDIATE" in text: return DocumentType.IMMEDIATE_REPORT
        if "LEGAL" in text: return DocumentType.LEGAL_DOCUMENT
        
        return DocumentType.OTHER
