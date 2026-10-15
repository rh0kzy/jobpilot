"""Runtime settings: environment defaults overridden by saved local settings."""


from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ai_provider: str = Field(default="gemini", alias="AI_PROVIDER")
    ai_model: str = Field(default="gemini-2.0-flash", alias="AI_MODEL")
    mistral_api_key: str | None = Field(default=None, alias="MISTRAL_API_KEY")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")

    search_provider: str = Field(default="tavily", alias="SEARCH_PROVIDER")
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    brave_search_api_key: str | None = Field(default=None, alias="BRAVE_SEARCH_API_KEY")
    searxng_base_url: str | None = Field(default=None, alias="SEARXNG_BASE_URL")

    settings_writable: bool = Field(default=True, alias="SETTINGS_WRITABLE")
    web_origin: str = Field(default="http://localhost:3000", alias="WEB_ORIGIN")
    allowed_hosts: str = Field(default="localhost,127.0.0.1", alias="JOBPILOT_ALLOWED_HOSTS")
    local_settings_token: str | None = Field(default=None, alias="JOBPILOT_SETTINGS_TOKEN")
    cache_dir: str = Field(default="./.cache", alias="CACHE_DIR")
    cache_refresh_hours: int = Field(default=24, alias="CACHE_REFRESH_INTERVAL_HOURS")
    request_timeout: int = Field(default=30, alias="REQUEST_TIMEOUT_SECONDS")

    model_config = {"env_file": ".env", "extra": "ignore"}


def get_settings() -> Settings:
    return Settings()


def resolve_ai_key(settings: Settings, saved_provider: str | None, saved_key: str | None) -> str | None:
    if saved_key:
        return saved_key
    provider = saved_provider or settings.ai_provider
    mapping = {
        "mistral": settings.mistral_api_key,
        "gemini": settings.gemini_api_key,
        "groq": settings.groq_api_key,
        "openai": settings.openai_api_key,
    }
    return mapping.get(provider.lower())


def resolve_search_key(settings: Settings, saved_provider: str | None, saved_key: str | None) -> str | None:
    if saved_key:
        return saved_key
    provider = saved_provider or settings.search_provider
    if provider.lower() == "tavily":
        return settings.tavily_api_key
    if provider.lower() == "brave":
        return settings.brave_search_api_key
    return None
