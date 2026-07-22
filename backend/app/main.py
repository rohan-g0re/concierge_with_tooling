"""
Compass — FastAPI application entry point.

P0: health endpoint + CORS scaffold.
Later phases mount /chat, /action, /voice/token, /feedback, /debug routes.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routes.chat import router as chat_router
from .routes.action import router as action_router
from .routes.session import router as session_router
from .routes.voice import router as voice_router
from .routes.feedback import router as feedback_router
from .routes.debug import router as debug_router

logger = logging.getLogger(__name__)

settings = get_settings()

# Log effective LLM mode once at startup so silent fallback is always visible.
_mode = settings.llm_mode
if _mode == "gemini" or (_mode == "auto" and settings.gemini_api_key):
    print("LLM mode: live (gemini)", flush=True)
else:
    print("LLM mode: stub", flush=True)

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
app.include_router(voice_router)
app.include_router(feedback_router)
app.include_router(debug_router)


@app.get("/health")
async def health() -> dict:
    """Health check — returns {status: ok}."""
    return {"status": "ok"}
