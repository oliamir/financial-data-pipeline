"""Application settings with environment variable support."""

from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings

class PipelineSettings(BaseSettings):
    data_dir: str = "data/companies"
    downloads_dir: str = "downloads"
    output_dir: str = "output"
    max_concurrent_companies: int = 3
    default_years_back: int = 1

class ScrapingSettings(BaseSettings):
    tase_timeout_seconds: int = 120
    tase_max_pages: int = 8
    page_load_timeout: int = 30000
    headless: bool = True

class WebSettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8050
    debug: bool = False

class Settings(BaseSettings):
    """Top-level application settings."""
    model_config = {"env_prefix": "FINANCE_"}

    # API Keys (from .env)
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    ollama_host: str = Field(default="http://localhost:11434", alias="OLLAMA_HOST")

    # Sub-settings
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    scraping: ScrapingSettings = Field(default_factory=ScrapingSettings)
    web: WebSettings = Field(default_factory=WebSettings)

    # Project root (computed)
    project_root: Optional[str] = None

    def resolve_data_dir(self) -> Path:
        root = Path(self.project_root) if self.project_root else Path.cwd()
        return root / self.pipeline.data_dir

_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Get or create singleton settings instance."""
    global _settings
    if _settings is None:
        from dotenv import load_dotenv
        load_dotenv()
        _settings = Settings()
    return _settings
