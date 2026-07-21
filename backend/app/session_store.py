"""
Compass — Thread-safe in-memory session store.
"""
from __future__ import annotations

import threading
import uuid
from typing import Optional

from .models import Session, Constraints


_lock = threading.Lock()
_sessions: dict[str, Session] = {}


def get_or_create(session_id: str) -> Session:
    """Return existing session or create a new one."""
    with _lock:
        if session_id not in _sessions:
            _sessions[session_id] = Session(session_id=session_id)
        return _sessions[session_id]


def update(session: Session) -> None:
    """Persist (overwrite) a session object."""
    with _lock:
        _sessions[session.session_id] = session
