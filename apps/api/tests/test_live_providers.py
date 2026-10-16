import os

import pytest

pytestmark = pytest.mark.live


def _live_enabled() -> bool:
    return os.getenv("JOBPILOT_LIVE_TESTS") == "1"


@pytest.mark.skipif(not _live_enabled() or not os.getenv("GEMINI_API_KEY"), reason="live Gemini not enabled")
async def test_gemini_live():
    from app.providers.gemini import GeminiProvider

    p = GeminiProvider(model=os.getenv("AI_MODEL", "gemini-3.1-flash-lite"), api_key=os.getenv("GEMINI_API_KEY"))
    assert "PONG" in (await p.complete("Reply with exactly PONG")).upper()


@pytest.mark.skipif(not _live_enabled() or not os.getenv("MISTRAL_API_KEY"), reason="live Mistral not enabled")
async def test_mistral_live():
    from app.providers.mistral import MistralProvider

    p = MistralProvider(model=os.getenv("AI_MODEL", "codestral-2508"), api_key=os.getenv("MISTRAL_API_KEY"))
    assert "PONG" in (await p.complete("Reply with exactly PONG")).upper()