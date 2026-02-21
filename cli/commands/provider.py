"""CLI provider commands -- check AI provider health and list models."""

from rich.console import Console
from rich.table import Table

console = Console()


def run_provider_status() -> None:
    """Show status of all configured AI providers."""
    from src.ai.providers import ProviderRegistry

    registry = ProviderRegistry()
    table = Table(title="AI Provider Status")
    table.add_column("Provider", style="cyan")
    table.add_column("Status")
    table.add_column("Model")
    table.add_column("Details")

    for name, provider in registry.providers.items():
        try:
            healthy = _check_health(provider)
            status = "[green]Online[/green]" if healthy else "[red]Offline[/red]"
            model = _get_model_name(provider)
            models_list = _list_models(provider)
            table.add_row(name, status, model, models_list)
        except Exception as e:
            table.add_row(name, "[red]Error[/red]", "N/A", str(e))

    console.print(table)

    if not registry.providers:
        console.print(
            "[yellow]No providers configured. "
            "Check config/providers.yaml and environment variables.[/yellow]"
        )


def _check_health(provider: object) -> bool:
    """Attempt a lightweight health check on a provider.

    Args:
        provider: A BaseProvider instance.

    Returns:
        True if the provider responds, False otherwise.
    """
    if hasattr(provider, "health_check"):
        return provider.health_check()

    # For GeminiProvider: check that genai module is configured
    if hasattr(provider, "genai"):
        try:
            # Listing models is a lightweight way to verify the API key works
            _ = list(provider.genai.list_models())
            return True
        except Exception:
            return False

    # For OllamaProvider: check client connectivity
    if hasattr(provider, "client") and provider.client is not None:
        try:
            provider.client.list()
            return True
        except Exception:
            return False

    return False


def _get_model_name(provider: object) -> str:
    """Extract the model name from a provider instance.

    Args:
        provider: A BaseProvider instance.

    Returns:
        Model name string or 'N/A'.
    """
    if hasattr(provider, "model_name"):
        return provider.model_name
    if hasattr(provider, "model"):
        return provider.model
    return "N/A"


def _list_models(provider: object) -> str:
    """List available models for a provider.

    Args:
        provider: A BaseProvider instance.

    Returns:
        Comma-separated model names or 'N/A'.
    """
    if hasattr(provider, "list_models"):
        try:
            models = provider.list_models()
            return ", ".join(models) if models else "N/A"
        except Exception:
            return "N/A"

    # For Ollama, try listing installed models
    if hasattr(provider, "client") and provider.client is not None:
        try:
            response = provider.client.list()
            models = response.get("models", [])
            names = [m.get("name", "?") for m in models[:5]]
            if len(models) > 5:
                names.append(f"...+{len(models) - 5} more")
            return ", ".join(names) if names else "N/A"
        except Exception:
            return "N/A"

    return "N/A"
