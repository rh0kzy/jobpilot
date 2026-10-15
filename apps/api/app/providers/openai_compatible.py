"""OpenAI-compatible providers: Mistral, Groq, OpenAI, Ollama."""

from app.providers.base import AIProvider


class OpenAICompatibleProvider(AIProvider):
    def __init__(self, name, endpoint, model, api_key=None, base_url=None):
        super().__init__(model=model, api_key=api_key, base_url=base_url)
        self.name = name
        self.endpoint = endpoint
        self.base_url = base_url

    async def complete(self, prompt: str, system: str | None = None) -> str:
        import httpx

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        url = self.base_url or self.endpoint
        body = {"model": self.model, "messages": messages}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
