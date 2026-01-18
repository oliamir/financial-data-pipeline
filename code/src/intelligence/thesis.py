from .llm_client import LLMClient
import os

class ThesisGenerator:
    def __init__(self, llm_client: LLMClient, system_prompt: str = None):
        self.llm = llm_client
        self.system_prompt = system_prompt

    def update_thesis(self, current_thesis: str, new_report_path: str, model_name: str = "gemini-3-flash-preview") -> str:
        print(f"Updating thesis with insights from {os.path.basename(new_report_path)}...")
        file_ref = self.llm.upload_file(new_report_path)
        
        base_persona = self.system_prompt if self.system_prompt else """
        You are a Senior Investment Officer. You maintain a living "Investment Memo" for this company.
        """

        prompt = f"""
        {base_persona}
        
        Current Thesis / Memo Status:
        {current_thesis if current_thesis else "(No previous thesis exists. Start a new one.)"}
        
        Task:
        Read the attached new report. 
        Update the Investment Memo to reflect the new information.
        - If the new report contradicts previous assumptions, correct them.
        - If it validates them, strengthen the language.
        - Add a section "Latest Updates ({os.path.basename(new_report_path)})" summarizing key takeaways from this specific file.
        - Maintain the structure: Executive Summary, Investment Thesis, Key Risks, Financials, Latest Updates.
        
        Return the FULL updated Markdown text.
        """
        
        return self.llm.prompt_with_file(file_ref, prompt, model_name=model_name)
