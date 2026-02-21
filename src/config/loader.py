"""YAML configuration loader with Pydantic validation."""

import yaml
from pathlib import Path
from typing import List, Dict, Any

from ..models.company import Company

def _find_project_root() -> Path:
    """Walk up from this file to find project root (contains pyproject.toml)."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "pyproject.toml").is_file():
            return current
        current = current.parent
    raise FileNotFoundError("Could not find project root (no pyproject.toml found)")

def _load_yaml(filename: str) -> dict:
    """Load a YAML file from config/ directory."""
    root = _find_project_root()
    path = root / "config" / filename
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r") as f:
        return yaml.safe_load(f)

def load_companies() -> Dict[str, Company]:
    """Load and validate all companies from companies.yaml."""
    data = _load_yaml("companies.yaml")
    companies = {}
    for entry in data.get("companies", []):
        company = Company.model_validate(entry)
        companies[company.slug] = company
    return companies

def load_providers_config() -> Dict[str, Any]:
    """Load raw provider configuration."""
    return _load_yaml("providers.yaml")

def load_settings() -> dict:
    """Load settings.yaml."""
    return _load_yaml("settings.yaml")
