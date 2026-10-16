from app.providers.openai_compatible import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    def __init__(self, model: str, api_key: str | None = None) -> None:
        super().__init__(
            name="openai",
            endpoint="https://api.openai.com/v1/chat/completions",
            model=model,
            api_key=api_key,
        )
