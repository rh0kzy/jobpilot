"""AI provider interface and shared helpers."""

from abc import ABC, abstractmethod


class AIProvider(ABC):
    name: str

    def __init__(self, model: str, api_key: str | None = None, base_url: str | None = None) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    async def complete(self, prompt: str, system: str | None = None) -> str:
        ...

    async def health_check(self) -> bool:
        try:
            await self.complete("ping")
            return True
        except Exception:  # noqa: BLE001
            return False
