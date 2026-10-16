from app.providers.openai_compatible import OpenAICompatibleProvider


class OllamaProvider(OpenAICompatibleProvider):
    def __init__(self, model: str, base_url: str = "http://localhost:11434") -> None:
        super().__init__(
            name="ollama",
            endpoint=f"{base_url.rstrip('/')}/v1/chat/completions",
            model=model,
        )
