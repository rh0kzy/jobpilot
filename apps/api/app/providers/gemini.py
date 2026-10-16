"""Google Gemini provider (REST, no SDK required)."""

import httpx

from app.providers.base import AIProvider


class GeminiProvider(AIProvider):
    name = "gemini"

    async def complete(self, prompt: str, system: str | None = None) -> str:
        if not self.api_key:
            raise RuntimeError("Gemini API key is missing")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        parts = [{"text": prompt}]
        body: dict = {"contents": [{"parts": parts}]}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]



