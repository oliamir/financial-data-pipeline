import os
import google.generativeai as genai
from typing import Optional

class LLMClient:
    def __init__(self, api_key: Optional[str] = None, provider: str = "google"):
        self.provider = provider
        self.api_key = api_key or (os.getenv("GOOGLE_API_KEY") if provider == "google" else os.getenv("ANTHROPIC_API_KEY"))
        
        if not self.api_key:
            print(f"Warning: API Key for {provider} not found.")
        else:
            if provider == "google":
                genai.configure(api_key=self.api_key)
            elif provider == "anthropic":
                # Lazy import
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=self.api_key)

    def upload_file(self, path: str):
        """Uploads a file to Gemini for processing. (No-op or different for Claude)"""
        if self.provider == "google":
            print(f"Uploading {path} to Gemini...")
            sample_file = genai.upload_file(path=path)
            print(f"Completed upload: {sample_file.uri}")
            return sample_file
        return path # For Anthropic we send local path/content directly in prompt

    def prompt_with_file(self, file_obj, prompt_text: str, model_name: str = "gemini-3-flash-preview"):
        """Sends a prompt with an attached file."""
        if self.provider == "google":
            return self._call_google(file_obj, prompt_text, model_name)
        elif self.provider == "anthropic":
            return self._call_anthropic(file_obj, prompt_text, model_name)

    def _call_google(self, file_obj, prompt_text: str, model_name: str):
        import time
        model = genai.GenerativeModel(model_name=model_name)
        max_retries = 5
        delay = 30
        
        for attempt in range(max_retries):
            try:
                if attempt > 0: time.sleep(delay)
                response = model.generate_content([prompt_text, file_obj])
                return response.text
            except Exception as e:
                if "429" in str(e) or "Quota exceeded" in str(e):
                    if attempt < max_retries - 1:
                        print(f"  ⚠ Rate limit hit (Google). Retrying in {delay}s...")
                        delay *= 1.5 
                        continue
                raise e

    def _call_anthropic(self, file_path, prompt_text: str, model_name: str):
        import base64
        import mimetypes
        
        # If file_obj is a Gemini file object vs a path, we might have an issue.
        # Ensure simple contract: file_obj is a path for Anthropic flow?
        # In main/analyze, we pass file_path to upload_file, which returns object for Google, 
        # but returns path for Anthropic (due to my change above).
        
        if not isinstance(file_path, str):
            # Fallback if somehow a Gemini object got passed?
            raise ValueError("Anthropic requires a file path, not a Gemini object.")

        media_type, _ = mimetypes.guess_type(file_path)
        if not media_type: media_type = "application/pdf" # Default
        
        with open(file_path, "rb") as f:
            file_data = base64.b64encode(f.read()).decode("utf-8")
            
        message = self.anthropic_client.messages.create(
            model=model_name,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": file_data
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt_text
                        }
                    ]
                }
            ]
        )
        return message.content[0].text
