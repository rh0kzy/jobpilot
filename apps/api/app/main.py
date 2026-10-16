from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.settings import router as settings_router
from app.core import settings as runtime_settings
from app.providers.factory import AIKeyMissingError

settings = runtime_settings.get_settings()

app = FastAPI(title="JobPilot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(settings_router)


@app.exception_handler(AIKeyMissingError)
async def ai_key_missing_handler(request: Request, exc: AIKeyMissingError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"code": "ai_key_missing", "message": str(exc)})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "jobpilot-api"}