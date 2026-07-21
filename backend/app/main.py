"""
Compass — FastAPI application entry point.

P0: health endpoint + CORS scaffold.
Later phases mount /chat, /action, /voice/token, /feedback, /debug routes.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routes.chat import router as chat_router
from .routes.action import router as action_router
from .routes.session import router as session_router

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


app.include_router(chat_router)
app.include_router(action_router)
app.include_router(session_router)


@app.get("/health")
async def health() -> dict:
    """Health check — returns {status: ok}."""
    return {"status": "ok"}
