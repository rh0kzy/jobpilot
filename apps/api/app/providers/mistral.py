from app.providers.openai_compatible import OpenAICompatibleProvider


class MistralProvider(OpenAICompatibleProvider):
    def __init__(self, model: str, api_key: str | None = None) -> None:
        super().__init__(
            name="mistral",
            endpoint="https://api.mistral.ai/v1/chat/completions",
            model=model,
            api_key=api_key,
        )
