import app.providers.openai_compatible as compat


class Resp:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": "pong"}}]}


class Client:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, *a, **k):
        return Resp()


async def test_mistral_complete(monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: Client())
    from app.providers.mistral import MistralProvider

    provider = MistralProvider(model="mistral-small", api_key="secret")
    assert await provider.complete("hi") == "pong"


async def test_provider_interface(monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: Client())
    provider = compat.OpenAICompatibleProvider(
        name="x", endpoint="http://example", model="m", api_key="k"
    )
    assert await provider.complete("hi") == "pong"