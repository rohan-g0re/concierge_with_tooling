"""
Compass — FastAPI application entry point.

P0: health endpoint + CORS scaffold.
Later phases mount /chat, /action, /voice/token, /feedback, /debug routes.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings

settings = get_settings()

app = FastAPI(
    title="Compass Concierge API",
    description="Carnival / HAL conversational booking concierge backend",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    """Health check — returns {status: ok}."""
    return {"status": "ok"}
