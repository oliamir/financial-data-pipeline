import os
import time
from typing import Optional, Dict, Any

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
            "ollama": True  # Always available if installed
        }
        
        # Override with passed key for legacy support
        if api_key and provider in ["google", "anthropic", "openai"]:
            self.keys[provider] = api_key

        self._configure_providers()

    def _configure_providers(self):
        # Google GenAI (new SDK)
        self.google_client = None
        if self.keys["google"]:
            try:
                from google import genai
                self.google_client = genai.Client(api_key=self.keys["google"])
            except Exception as e:
                print(f"Warning: Failed to configure Google GenAI: {e}")
        
        # Anthropic
        self.anthropic_client = None
        if self.keys["anthropic"]:
            try:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=self.keys["anthropic"])
            except ImportError:
                print("Warning: 'anthropic' package not installed.")

        # OpenAI
        self.openai_client = None
        if self.keys["openai"]:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.keys["openai"])
            except ImportError:
                print("Warning: 'openai' package not installed.")

    def upload_file(self, path: str) -> Dict[str, Any]:
        """Uploads/Prepares file for LLM processing."""
        result = {"path": path}
        
        # Upload to Google if available
        if self.google_client and self.keys["google"]:
            if self.primary_provider == "google":
                print(f"Uploading {os.path.basename(path)} to Gemini...")
            try:
                uploaded_file = self.google_client.files.upload(file=path)
                result["google_file"] = uploaded_file
                if self.primary_provider == "google":
                    print(f"Completed upload: {uploaded_file.uri}")
            except Exception as e:
                if self.primary_provider == "google":
                    print(f"  ⚠ Google upload failed: {e}")
        
        return result

    def prompt_with_file(self, file_ref: Dict[str, Any], prompt_text: str, model_name: str = None) -> str:
        """Sends a prompt with file, cycling through providers on failure."""
        
        rotation = []
        start_idx = self.PROVIDERS.index(self.active_provider) if self.active_provider in self.PROVIDERS else 0
        
        if self.enable_fallback:
            for i in range(len(self.PROVIDERS)):
                idx = (start_idx + i) % len(self.PROVIDERS)
                p = self.PROVIDERS[idx]
                rotation.append(p)
        else:
            rotation.append(self.active_provider)
            
        last_error = None
        
        for provider in rotation:
            if not self.keys.get(provider):
                continue
                
            current_model = self._get_model_for_provider(provider, model_name)
            
            try:
                if provider != self.active_provider:
                    print(f"  🔄 Switching to {provider} ({current_model})...")
                    
                result = self._execute_prompt(provider, file_ref, prompt_text, current_model)
                
                self.active_provider = provider 
                return result
                
            except Exception as e:
                print(f"  ⚠ Error with {provider}: {e}")
                last_error = e
        
        raise last_error or Exception("All providers failed or no keys available.")

    def _get_model_for_provider(self, provider, requested_model):
        defaults = {
            "google": "gemini-2.0-flash",
            "anthropic": "claude-3-5-sonnet-20241022",
            "openai": "gpt-4o",
            "ollama": "llama3.1"
        }
        
        if requested_model:
            if provider == "google" and "gemini" in requested_model: return requested_model
            if provider == "anthropic" and "claude" in requested_model: return requested_model
            if provider == "openai" and "gpt" in requested_model: return requested_model
            if provider == "ollama" and "llama" in requested_model: return requested_model
            
        return defaults[provider]

    def _execute_prompt(self, provider, file_ref, prompt_text, model_name):
        if provider == "google":
            if "google_file" not in file_ref and self.google_client:
                print(f"  (Fallback) Uploading to Gemini...")
                try:
                    uploaded_file = self.google_client.files.upload(file=file_ref["path"])
                    file_ref["google_file"] = uploaded_file
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
        if not file_obj:
            raise ValueError("Google file object missing")
        if not self.google_client:
            raise ValueError("Google client not initialized")
        
        max_retries = 5
        delay = 5
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"  Retrying in {delay}s (attempt {attempt+1}/{max_retries})...")
                    time.sleep(delay)
                
                response = self.google_client.models.generate_content(
                    model=model_name,
                    contents=[prompt_text, file_obj]
                )
                return response.text
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
                    if attempt < max_retries - 1:
                        print(f"  ⚠ Rate limit hit (Google). Waiting {delay}s...")
                        delay = min(delay * 2, 60)
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
                print("  ⚠ pdfplumber missing for Ollama PDF extraction.")
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
