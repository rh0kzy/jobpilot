from app.providers.openai_compatible import OpenAICompatibleProvider


class GroqProvider(OpenAICompatibleProvider):
    def __init__(self, model: str, api_key: str | None = None) -> None:
        super().__init__(
            name="groq",
            endpoint="https://api.groq.com/openai/v1/chat/completions",
            model=model,
            api_key=api_key,
        )
