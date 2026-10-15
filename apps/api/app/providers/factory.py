"""Resolve a provider instance from settings + saved local config."""

from app.core import settings as runtime_settings
from app.core.settings_store import load_saved
from app.providers.base import AIProvider
from app.providers.gemini import GeminiProvider
from app.providers.groq import GroqProvider
from app.providers.mistral import MistralProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider


class AIKeyMissingError(Exception):
    pass


def get_provider() -> AIProvider:
    settings = runtime_settings.get_settings()
    saved = load_saved()
    provider_name = (saved.ai_provider or settings.ai_provider).lower()
    model = saved.ai_model or settings.ai_model
    api_key = runtime_settings.resolve_ai_key(settings, saved.ai_provider, saved.ai_api_key)

    if provider_name == "gemini":
        if not api_key:
            raise AIKeyMissingError("Gemini API key is not configured")
        return GeminiProvider(model=model, api_key=api_key)
    if provider_name == "mistral":
        if not api_key:
            raise AIKeyMissingError("Mistral API key is not configured")
        return MistralProvider(model=model, api_key=api_key)
    if provider_name == "groq":
        if not api_key:
            raise AIKeyMissingError("Groq API key is not configured")
        return GroqProvider(model=model, api_key=api_key)
    if provider_name == "openai":
        if not api_key:
            raise AIKeyMissingError("OpenAI API key is not configured")
        return OpenAIProvider(model=model, api_key=api_key)
    if provider_name == "ollama":
        return OllamaProvider(model=model, base_url=settings.ollama_base_url)
    raise ValueError(f"Unknown AI provider: {provider_name}")
