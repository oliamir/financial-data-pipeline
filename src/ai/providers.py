import os
import yaml
import time
from abc import ABC, abstractmethod
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class BaseProvider(ABC):
    @abstractmethod
    def prompt_with_document(self, doc_path: str, prompt: str) -> str:
        """Send a prompt with a document and return the response text."""
        pass

    @abstractmethod
    def prompt_text(self, prompt: str) -> str:
        """Send a text-only prompt and return the response text."""
        pass


class GeminiProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash",
                 max_retries: int = 3, rate_limit_delay: int = 10):
        import google.generativeai as genai
        self.genai = genai
        genai.configure(api_key=api_key)
        self.model_name = model
        self.max_retries = max_retries
        self.rate_limit_delay = rate_limit_delay

    def prompt_with_document(self, doc_path: str, prompt: str) -> str:
        print(f"  [Gemini] Uploading {os.path.basename(doc_path)}...")
        uploaded = self.genai.upload_file(path=doc_path)
        print(f"  [Gemini] Uploaded: {uploaded.uri}")

        model = self.genai.GenerativeModel(model_name=self.model_name)
        delay = self.rate_limit_delay

        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    time.sleep(delay)
                response = model.generate_content([prompt, uploaded])
                return response.text
            except Exception as e:
                if "429" in str(e) or "Quota exceeded" in str(e):
                    if attempt < self.max_retries - 1:
                        print(f"  [Gemini] Rate limit hit. Retrying in {delay}s...")
                        delay *= 1.5
                        continue
                raise

    def prompt_text(self, prompt: str) -> str:
        model = self.genai.GenerativeModel(model_name=self.model_name)
        response = model.generate_content(prompt)
        return response.text


class OllamaProvider(BaseProvider):
    def __init__(self, host: str = "http://localhost:11434", model: str = "qwen2.5:7b"):
        self.host = host
        self.model = model
        try:
            from ollama import Client
            self.client = Client(host=host)
        except ImportError:
            print("Warning: 'ollama' package not installed. OllamaProvider unavailable.")
            self.client = None

    def _extract_pdf_text(self, doc_path: str) -> str:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(doc_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n".join(text_parts)

    def prompt_with_document(self, doc_path: str, prompt: str) -> str:
        if not self.client:
            raise RuntimeError("Ollama client not available")

        import mimetypes
        media_type, _ = mimetypes.guess_type(doc_path)

        if media_type == "application/pdf":
            text_content = self._extract_pdf_text(doc_path)
            full_prompt = f"DOCUMENT CONTENT:\n{text_content}\n\nINSTRUCTIONS:\n{prompt}"
        else:
            with open(doc_path, "r", errors="ignore") as f:
                text_content = f.read()
            full_prompt = f"DOCUMENT CONTENT:\n{text_content}\n\nINSTRUCTIONS:\n{prompt}"

        response = self.client.chat(model=self.model, messages=[
            {"role": "user", "content": full_prompt}
        ])
        return response["message"]["content"]

    def prompt_text(self, prompt: str) -> str:
        if not self.client:
            raise RuntimeError("Ollama client not available")
        response = self.client.chat(model=self.model, messages=[
            {"role": "user", "content": prompt}
        ])
        return response["message"]["content"]


class ProviderRegistry:
    """Manages AI provider instances."""

    def __init__(self, config_path: str = None):
        if config_path is None:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(project_root, "config", "providers.yaml")

        self.providers: dict[str, BaseProvider] = {}
        self._load(config_path)

    def _load(self, config_path: str):
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)

        for name, cfg in data.get("providers", {}).items():
            if cfg.get("enabled") is False:
                continue

            provider_type = cfg["type"]

            if provider_type == "google":
                api_key = os.getenv(cfg.get("api_key_env", "GOOGLE_API_KEY"))
                if api_key:
                    self.providers[name] = GeminiProvider(
                        api_key=api_key,
                        model=cfg.get("model", "gemini-2.0-flash"),
                        max_retries=cfg.get("max_retries", 3),
                        rate_limit_delay=cfg.get("rate_limit_delay", 10),
                    )
                    print(f"  [Providers] Gemini configured ({cfg.get('model')})")
                else:
                    print(f"  [Providers] Gemini skipped (no API key)")

            elif provider_type == "ollama":
                host = os.getenv(
                    cfg.get("host_env", "OLLAMA_HOST"),
                    cfg.get("host_default", "http://localhost:11434"),
                )
                try:
                    self.providers[name] = OllamaProvider(
                        host=host,
                        model=cfg.get("model", "qwen2.5:7b"),
                    )
                    print(f"  [Providers] Ollama configured ({cfg.get('model')} @ {host})")
                except Exception as e:
                    print(f"  [Providers] Ollama skipped ({e})")

    def get(self, name: str) -> BaseProvider:
        if name not in self.providers:
            raise KeyError(f"Provider '{name}' not available. Available: {list(self.providers.keys())}")
        return self.providers[name]

    def has(self, name: str) -> bool:
        return name in self.providers

    def available(self) -> list[str]:
        return list(self.providers.keys())
