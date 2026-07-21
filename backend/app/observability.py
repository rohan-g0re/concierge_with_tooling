"""
Compass — Observability: structured logging + in-memory ring buffer.

Logs every tool call {tool, latency_ms} and first-token timing.
Ring buffer is accessible via get_log() for /debug endpoint.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

logger = logging.getLogger("compass.observability")

# In-memory ring buffer: keeps last 1000 events
_MAX_BUFFER = 1000
_log_buffer: deque[dict[str, Any]] = deque(maxlen=_MAX_BUFFER)

# Session start time for relative timestamps
_start_time = time.monotonic()


def _ts() -> float:
    """Relative timestamp in seconds since module load."""
    return round(time.monotonic() - _start_time, 3)


def record_tool_call(tool: str, latency_ms: int) -> None:
    """Log a tool invocation with its latency."""
    event = {
        "event": "tool_call",
        "tool": tool,
        "latency_ms": latency_ms,
        "ts": _ts(),
    }
    _log_buffer.append(event)
    logger.info("tool_call tool=%s latency_ms=%d", tool, latency_ms)


def record_first_token(start: float) -> None:
    """Log the time-to-first-token for a streaming response.

    Args:
        start: ``time.monotonic()`` timestamp captured at the beginning of the
               request turn.  ``elapsed_ms`` is the wall-clock milliseconds
               between that moment and the arrival of the first streamed token.
    """
    elapsed_ms = int((time.monotonic() - start) * 1000)
    event = {
        "event": "first_token",
        "elapsed_ms": elapsed_ms,
        "ts": _ts(),
    }
    _log_buffer.append(event)
    logger.info("first_token elapsed_ms=%d", elapsed_ms)


def get_log() -> list[dict[str, Any]]:
    """Return all buffered observability events (newest last)."""
    return list(_log_buffer)


def clear_log() -> None:
    """Clear the ring buffer (useful for testing)."""
    _log_buffer.clear()
