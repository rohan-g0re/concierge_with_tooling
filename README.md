# Compass — Conversational Booking Concierge

Meridian Line / HAL-style demo. Chat-first cruise concierge with action-level booking construction,
multi-draft session state, side-by-side comparison, checkout deep-link, and voice parity.

---

## Stack

| Layer      | Technology                                      |
|------------|-------------------------------------------------|
| Frontend   | Next.js 14 (App Router) · TypeScript · Tailwind |
| Backend    | FastAPI · Python 3.11 · uvicorn                 |
| Text LLM   | Gemini via `google-genai` SDK (v2.x GA)         |
| Voice      | OpenAI GPT Realtime (WebRTC)                    |
| State      | In-memory server dict + sessionStorage mirror   |

---

## Quick start

### Prerequisites

- Node.js 20+
- Python 3.11+

### 1. Environment variables

```bash
cp .env.example .env
# edit .env — fill in GEMINI_API_KEY and OPENAI_API_KEY
```

### 2. Backend (FastAPI)

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy env to backend dir (uvicorn reads it from CWD)
cp ../.env .env   # or set vars in shell

# Start the development server (port 8000)
uvicorn app.main:app --reload --port 8000
```

Backend health check:
```bash
curl http://localhost:8000/health
# → {"status":"ok"}
```

### 3. Frontend (Next.js)

```bash
cd frontend

npm install

# Start the development server (port 3000)
npm run dev
```

Open http://localhost:3000 — the Meridian Line top bar should render with Playfair Display and navy/gold brand tokens.

### 4. Production build check

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm run build
```

---

## Running tests

```bash
# Backend unit tests (from backend/ with venv active)
cd backend
pytest                   # all tests
pytest tests/test_health.py -v   # P0 health test
```

---

## Ports

| Service  | Default URL              |
|----------|--------------------------|
| Backend  | http://localhost:8000    |
| Frontend | http://localhost:3000    |
| API docs | http://localhost:8000/docs |

---

## Architecture overview

```
Next.js (App Router, TS, Tailwind)          FastAPI (Python 3.11)
┌─────────────────────────────┐   SSE/REST  ┌──────────────────────────────┐
│ Chat Shell /                │ ◄─────────► │ /chat  (Gemini orchestrator) │
│ /checkout/[draft_id]        │             │ /action/{tool} (tile bridge) │
│ /debug                      │             │ /voice/token                 │
│ Voice client (WebRTC) ──────┼─ ephemeral ─┤ Session store · Catalog svc  │
└─────────────────────────────┘    token    └──────────────────────────────┘
        ▲  audio (WebRTC)
        └───── OpenAI GPT Realtime ◄── tool relay ──┘
```

See `docs/plans/2026-07-21-001-feat-compass-concierge-plan.md` for the full phased implementation plan.
