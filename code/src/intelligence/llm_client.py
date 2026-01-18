import os
import google.generativeai as genai
from typing import Optional, Dict, Any
import time

class LLMClient:
    PROVIDERS = ["google", "anthropic", "openai", "ollama"]

    def __init__(self, api_key: Optional[str] = None, provider: str = "google", enable_fallback: bool = True):
        self.primary_provider = provider if provider in self.PROVIDERS else "google"
        self.active_provider = self.primary_provider
        self.enable_fallback = enable_fallback
        
        # Load keys from env
        self.keys = {
            "google": os.getenv("GOOGLE_API_KEY"),
            "anthropic": os.getenv("ANTHROPIC_API_KEY"),
            "openai": os.getenv("OPENAI_API_KEY"),
            "ollama": True # Always available if installed
        }
        
        # Override with passed key for legacy support - only applies to requested provider
        if api_key and provider in ["google", "anthropic", "openai"]:
            self.keys[provider] = api_key

        self._configure_providers()

    def _configure_providers(self):
        # Google
        if self.keys["google"]:
            try:
                genai.configure(api_key=self.keys["google"])
            except Exception as e:
                print(f"Warning: Failed to configure Google GenAI: {e}")
        
        # Anthropic
        if self.keys["anthropic"]:
            try:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=self.keys["anthropic"])
            except ImportError:
                print("Warning: 'anthropic' package not installed.")
                self.anthropic_client = None

        # OpenAI
        if self.keys["openai"]:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.keys["openai"])
            except ImportError:
                print("Warning: 'openai' package not installed.")
                self.openai_client = None

        # Ollama (No specific init needed for library, just check if running?)
        # We assume it's running if selected.

    def upload_file(self, path: str) -> Dict[str, Any]:
        """
        Uploads/Prepares file for logic.
        """
        result = {"path": path}
        
        # Upload to Google if key available
        if self.keys["google"]:
            if self.primary_provider == "google":
                print(f"Uploading {os.path.basename(path)} to Gemini...")
            try:
                sample_file = genai.upload_file(path=path)
                result["google_file"] = sample_file
                if self.primary_provider == "google":
                    print(f"Completed upload: {sample_file.uri}")
            except Exception as e:
                # Only warn if Google is primary
                if self.primary_provider == "google":
                    print(f"  ⚠ Google upload failed: {e}")
        
        return result

    def prompt_with_file(self, file_ref: Dict[str, Any], prompt_text: str, model_name: str = None) -> str:
        """Sends a prompt with file, cycling through providers on failure."""
        
        # Order of attempts: Active -> (Others in rotation)
        # Create rotation starting from active provider
        rotation = []
        start_idx = self.PROVIDERS.index(self.active_provider) if self.active_provider in self.PROVIDERS else 0
        
        # Build list: [active, next, next]
        if self.enable_fallback:
            for i in range(len(self.PROVIDERS)):
                idx = (start_idx + i) % len(self.PROVIDERS)
                p = self.PROVIDERS[idx]
                rotation.append(p)
        else:
            rotation.append(self.active_provider)
            
        last_error = None
        
        for provider in rotation:
            # Check availability
            if not self.keys.get(provider):
                continue
                
            # Determine appropriate model for this provider
            current_model = self._get_model_for_provider(provider, model_name)
            
            try:
                if provider != self.active_provider:
                    print(f"  🔄 Switching to {provider} ({current_model})...")
                    
                result = self._execute_prompt(provider, file_ref, prompt_text, current_model)
                
                # If successful and was a fallback, update active provider
                self.active_provider = provider 
                return result
                
            except Exception as e:
                print(f"  ⚠ Error with {provider}: {e}")
                last_error = e
                # Continue to next provider
        
        # If we get here, all failed
        raise last_error or Exception("All providers failed or no keys available.")

    def _get_model_for_provider(self, provider, requested_model):
        defaults = {
            "google": "gemini-2.0-flash",
            "anthropic": "claude-3-5-sonnet-20241022",
            "openai": "gpt-4o",
            "ollama": "llama3.1"
        }
        
        # Heuristics
        if requested_model:
            if provider == "google" and "gemini" in requested_model: return requested_model
            if provider == "anthropic" and "claude" in requested_model: return requested_model
            if provider == "openai" and "gpt" in requested_model: return requested_model
            if provider == "ollama" and "llama" in requested_model: return requested_model
            
        return defaults[provider]

    def _execute_prompt(self, provider, file_ref, prompt_text, model_name):
        if provider == "google":
            if "google_file" not in file_ref and self.keys["google"]:
                # Late upload
                print(f"  (Fallback) Uploading to Gemini...")
                try:
                    sample_file = genai.upload_file(path=file_ref["path"])
                    file_ref["google_file"] = sample_file
                except Exception as e:
                    raise Exception(f"Google upload failed during fallback: {e}")
                
            return self._call_google(file_ref.get("google_file"), prompt_text, model_name)
            
        elif provider == "anthropic":
            return self._call_anthropic(file_ref["path"], prompt_text, model_name)
            
        elif provider == "openai":
            return self._call_openai(file_ref["path"], prompt_text, model_name)
            
        elif provider == "ollama":
            return self._call_ollama(file_ref["path"], prompt_text, model_name)

    def _call_google(self, file_obj, prompt_text: str, model_name: str):
        if not file_obj: raise ValueError("Google file object missing")
        
        model = genai.GenerativeModel(model_name=model_name)
        max_retries = 3
        delay = 10
        
        for attempt in range(max_retries):
            try:
                if attempt > 0: time.sleep(delay)
                response = model.generate_content([prompt_text, file_obj])
                return response.text
            except Exception as e:
                # Start handling rate limits
                if "429" in str(e) or "Quota exceeded" in str(e):
                    if attempt < max_retries - 1:
                        print(f"  ⚠ Rate limit hit (Google). Retrying in {delay}s...")
                        delay *= 1.5 
                        continue
                raise e

    def _call_anthropic(self, file_path, prompt_text: str, model_name: str):
        import base64
        import mimetypes
        media_type, _ = mimetypes.guess_type(file_path)
        if not media_type: media_type = "application/pdf"
        
        with open(file_path, "rb") as f:
            file_data = base64.b64encode(f.read()).decode("utf-8")
            
        message = self.anthropic_client.messages.create(
            model=model_name,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "document", "source": {"type": "base64", "media_type": media_type, "data": file_data}},
                        {"type": "text", "text": prompt_text}
                    ]
                }
            ]
        )
        return message.content[0].text

    def _call_openai(self, file_path, prompt_text: str, model_name: str):
        import mimetypes
        media_type, _ = mimetypes.guess_type(file_path)
        
        content = []
        
        if media_type == "application/pdf":
            # Extract text
            try:
                import pdfplumber
                text_content = ""
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text_content += page.extract_text() + "\n"
                content.append({"type": "text", "text": f"DOCUMENT CONTENT:\n{text_content}\n\nINSTRUCTIONS:\n{prompt_text}"})
            except ImportError:
                 raise ImportError("pdfplumber needed for OpenAI text extraction fallback")
        else:
             content.append({"type": "text", "text": prompt_text})

        completion = self.openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": content}
            ]
        )
        return completion.choices[0].message.content

    def _call_ollama(self, file_path, prompt_text: str, model_name: str):
        import ollama
        
        # Ollama currently doesn't support 'application/pdf' blobs directly in Python SDK cleanly for all models,
        # usually simpler to send text. Llama3 is text-based (Llava is vision).
        # We should extract text for Llama3.
        
        import mimetypes
        media_type, _ = mimetypes.guess_type(file_path)
        
        final_prompt = prompt_text
        
        if media_type == "application/pdf":
             try:
                import pdfplumber
                text_content = ""
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text_content += page.extract_text() + "\n"
                
                final_prompt = f"DOCUMENT CONTENT:\n{text_content}\n\nINSTRUCTIONS:\n{prompt_text}"
             except ImportError:
                 # Try basic text read if it's not binary? No, PDF is binary.
                 # Warn and fail?
                 # Try naive read?
                 # Let's ensure pdfplumber is there or fail.
                 print("  ⚠ pdfplumber missing for Ollama PDF extraction. Trying to read as text...")
                 try:
                     with open(file_path, "r", errors='ignore') as f:
                         text_content = f.read()
                     final_prompt = f"DOCUMENT CONTENT:\n{text_content}\n\nINSTRUCTIONS:\n{prompt_text}"
                 except:
                     raise Exception("Could not extract text from file for Ollama.")

        response = ollama.chat(model=model_name, messages=[
          {
            'role': 'user',
            'content': final_prompt,
          },
        ])
        return response['message']['content']
