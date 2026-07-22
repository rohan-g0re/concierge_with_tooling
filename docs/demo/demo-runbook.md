# Demo Runbook — Carnival Concierge

Presenter-facing. Keep this open alongside the browser.

---

## 1. START PROCEDURE

### Kill existing processes

```powershell
Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000,3000,3001 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique) -Force -ErrorAction SilentlyContinue
```

### Backend (LIVE mode)

From `backend/` directory:

```powershell
uvicorn app.main:app --port 8000
```

- Do NOT set `LLM_MODE` — `.env` in `backend/` already has the Gemini key.
- Verify: `GET http://localhost:8000/health` returns 200.

### Frontend

From `frontend/` directory:

```powershell
npm run dev
```

- Verify: `http://localhost:3000` returns 200.

### Browser

Open at 1920x1080.

---

## 2. EMERGENCY FALLBACK

If Gemini is down or returns 429 on demo day:

```powershell
$env:LLM_MODE="stub"; uvicorn app.main:app --port 8000
```

- Stub mode: identical UI, deterministic responses, no Gemini dependency.
- Last resort: use screenshots from rehearsal passes.

---

## 3. FLOW SCRIPTS

### Flow A — "October in Alaska" (A1–A8)

| Step | Guest Message / Action | Expected Result | Danger |
|------|------------------------|-----------------|--------|
| A1 | Click "New Chat" | Fresh session, 0 drafts in rail, composer visible | — |
| A2 | "Show me Alaska cruises in October" | `search_cruises` fires; dated Alaska tiles appear with exact + near-miss sections | Chips vanish during streaming — do not click mid-stream |
| A3 | Change date via `<select>` on a tile | Draft created with chosen sailing; rail shows gold ring, total populates | — |
| A4 | Click chip → fare package choice | Rail total rises to reflect fare; component shows package options | — |
| A5 | "How much will this trip cost me?" | Must quote draft-held total exactly (from rail/session), not catalog base fare | Numbers must match draft snapshot |
| A6 | "Show me the itinerary" | `get_itinerary` fires; itinerary component renders beneath assistant bubble | — |
| A7 | "Will we see the northern lights?" | Conversational reply only; no spurious tool calls; no new components | Model must not invent facts |
| A8 | "Book it" / "Lock it in" | `handoff_checkout` fires; checkout screen shows deposit/balance breakdown | This is the checkout rule trigger — verify tool fires |

### Flow B — "Back before Dec 28" (B1–B9)

| Step | Guest Message / Action | Expected Result | Danger |
|------|------------------------|-----------------|--------|
| B1 | Click "New Chat" | Fresh session, 0 drafts | — |
| B2 | "Find me a 14-night cruise back before December 28" | `search_cruises` fires with `nights_min=14`, `nights_max=14`, `return_by=2025-12-28`; exact section first, labeled alternatives below | Exact section must appear first |
| B3 | Select a 14-night tile | Draft 1 created; rail shows gold ring | — |
| B4 | "What about a 20-night option?" | `search_cruises` fires with `nights_min=20`, `nights_max=20`; no exact match → labeled alternatives (not empty state) | Must NOT show empty state |
| B5 | "Show me something in Bermuda" | `search_cruises` fires; Bermuda results appear | — |
| B6 | Select a Bermuda tile | Draft 2 created; rail shows two drafts | — |
| B7 | "Back to the two-week one" | `set_active_draft` fires for Draft 1; NO compare table shown | Single-reference must not trigger compare |
| B8 | "Compare them side by side" | `compare_drafts` fires; comparison table renders | Only fires on explicit compare request |
| B9 | "Which is cheaper per night?" | Numbers quoted must match draft-held totals, not catalog fares | Verify arithmetic matches session snapshot |

### Flow C — "The Alaska Juggler" (C1–C10)

| Step | Guest Message / Action | Expected Result | Danger |
|------|------------------------|-----------------|--------|
| C1 | Click "New Chat" | Fresh session, 0 drafts | — |
| C2 | "Show me Alaska cruises" | `search_cruises` fires; flat card row (no date constraint, no sections) | — |
| C3 | Build 3 drafts: select 7n Alaska → rail 1; select 12n Alaska → rail 2; search Mexico, select Mexico tile → rail 3 | Rail shows 3 drafts after each sub-step | Verify rail updates after each draft creation |
| C4 | "Tell me more about the Alaska one" | `disambiguate_drafts` fires; which-one disambiguation cards shown; active draft unchanged | Two Alaska drafts → must disambiguate |
| C5 | Tap the 7-night disambiguation card | `set_active_draft` fires for 7n draft; rail gold ring moves | — |
| C6 | "What dining does the 12-day one have?" | `set_active_draft` fires for 12n draft (duration-specific, no ambiguity); `list_dining` fires | Must NOT show which-one cards |
| C7 | "My friend loved the Caribbean last year" | Conversational reply only; NO `set_active_draft`, NO `search_cruises`; active draft unchanged | Incidental mention — must not trigger switch or search |
| C8 | Hover over Mexico draft tile in rail; click delete | Rail 3 → 2; Mexico draft gone; confirmation of removal | Hover-delete requires deliberate hover — do not rush |
| C9 | "Any Hawaii cruises?" | `search_cruises` fires with region=hawaii; flat dated row; draft count stays at 2 | Draft count must not change |
| C10 | "Book me the best one" | Conversational reply; base fares quoted (no active draft with these words); no new draft created; no checkout triggered | No checkout tool call — "best one" is ambiguous, not a confirmed booking |

---

## 4. COMPOSABILITY MATRIX & DANGER ZONES

### Cross-flow preconditions

| Step family | Session state required |
|-------------|------------------------|
| A5 pricing question | Active draft with fare set |
| B7 single-reference switch | 2+ drafts, one matches uniquely |
| C4 disambiguation | 2+ drafts matching same region |
| B8 compare | 2+ drafts exist |
| A8 checkout | 1+ draft, guest confirms booking |
| C8 hover-delete | 1+ draft in rail |

### Danger zones

- Draft cap is 5 — do not create more than 5 drafts in a session.
- Disambiguation requires 2+ drafts matching the reference — if only 1 draft exists, direct switch happens.
- Chips fire paid Gemini turns — do not click chips when demoing cost control.
- Autoscroll: do not fight the scroll mid-stream; wait for streaming to finish before scrolling.
- Hover-delete on rail tile needs deliberate hover to reveal the delete button — do not rush past it.
- Feedback thumbs appear under completed assistant replies — do not misclick them thinking they are chips.

### Presenter micro-notes

- Chips vanish during streaming (rendered after the stream ends) — this is expected; do not comment on it.
- Streaming cursor appears in the assistant bubble — if it appears in the user bubble instead, that is a bug to note.
- Rail highlight (gold ring) may lag up to ~1s after a draft switch — pause briefly before pointing to it.
- SkeletonCardRow shimmer appears on conversational turns before components arrive — expected behavior.
- After each tool call, verify the network tab shows HTTP 200 on `/chat` and `/session`.

---

## 5. TECHNICAL Q&A PREP

| Question | Answer |
|----------|--------|
| Architecture? | Next.js 14 (App Router) frontend + FastAPI backend, Server-Sent Events for streaming, ephemeral session state in memory |
| LLM orchestration? | Gemini function-calling loop in `gemini_client.py`; model calls tools, results injected back, loop until final text |
| How does near-miss search work? | Pure tool logic in `search.py`, not the model — deterministic bucketing into exact/near-miss sections |
| How do you prevent draft confusion? | Each draft has a UUID; session snapshot injected into every prompt; `set_active_draft` makes switches explicit |
| Pricing truth? | Draft-held total lives in session state, always quoted from there — model cannot invent it (PRICING RULE in system prompt) |
| Component rendering? | Tool results return typed component descriptors; frontend renders them via a registry map — model never writes HTML |
| Testing strategy? | Stub mode (`LLM_MODE=stub`) gives deterministic responses; 242 backend tests cover tool schemas, routing, session logic |
| Date seeding? | 482 sailings seeded with `DEMO_ANCHOR` date so October/December queries always return results |
| Cost discipline? | Paid turns only when needed; stub mode for regression; system prompt has token-efficient rules |
