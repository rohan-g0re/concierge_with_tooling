---
date: 2026-07-21
topic: pinned-ui-dates-draft-context
focus: pinned drafts panel + composer, cruise dates & 5+ destinations with date filtering + near-miss alternatives, AI-driven draft context switching with rich draft identity
---

# Ideation: Pinned Chat Chrome, Date-Aware Catalog, Conversational Draft Switching

## Codebase Context

- **Stack:** Next.js 14 App Router + Tailwind (`frontend/`), FastAPI (`backend/`), Gemini `gemini-flash-latest` chat via SSE, OpenAI Realtime voice. In-memory session state + sessionStorage mirror.
- **Layout:** `frontend/app/page.tsx` (~lines 591–653) — `DraftRail` (`frontend/components/drafts/DraftRail.tsx`, 240px aside) is a flex sibling of `<main>` with no `overflow-y-auto` on its card list; `Composer` (`frontend/components/chat/Composer.tsx`) relies on a fragile flex `min-h-0` chain, no `flex-none`/sticky.
- **Catalog:** `backend/app/catalog/data/cruises.json` — 24 cruises, 4 regions (Alaska 8, Mexico 6, Caribbean 6, Mediterranean 4). **No departure/return date fields** — date filtering structurally impossible today.
- **Orchestration:** `backend/app/llm/gemini_client.py` agentic loop with per-turn session snapshot (exact draft ids/labels/state). `set_active_draft` tool exists; `system_prompt.py` has no conversational context-switch rule (only COMPARE DRAFTS RULE). Action bridge `/action/{tool}` for UI-initiated tool calls.
- **Drafts** hold own state (fare package, stateroom, dining, land days, completed steps, total price) separate from catalog base price. `DraftInfo` snapshot today carries only `label`, `completed_steps`, `total_formatted`.
- **Past learnings** (`docs/solutions/`): every Gemini tool needs an explicit branch in `_map_tool_result_to_component`; system-prompt rules must be explicit or the model freeloads in prose; snapshot must list exact ids; `set_active_draft` mapping needs two-key fallback.

## Ranked Ideas

### 1. Pinned Chat Chrome — DraftRail + Composer
**Description:** DraftRail aside gets `flex-none` + `overflow-y-auto` on the card list (header/footer fixed); Composer wrapper gets `flex-none`/sticky bottom-0, decoupled from the fragile `min-h-0` chain in `page.tsx`.
**Rationale:** User asks #1 and #2. Confirmed layout defects; pure CSS.
**Downsides:** Verify P15 768px rail breakpoint still works.
**Confidence:** 95%
**Complexity:** Low
**Status:** Explored

### 2. Date Schema + Catalog Expansion to 6 Regions
**Description:** Add `departure_date`/`return_date` (or a `sail_dates` series) to every cruise; seed script generates realistic date series; expand 4→6 regions (~36 dated sailings). New regions: Hawaii, Bermuda/Bahamas, Norway (Northern Europe).
**Rationale:** Foundation — unlocks date filtering, near-miss alternatives, and rich draft identity. Current catalog too thin for near-miss to have material.
**Downsides:** Touches loader, search tool, card components; fixtures/tests need updates.
**Confidence:** 90%
**Complexity:** Medium
**Status:** Explored

### 3. Date-Filter Tool in Gemini Loop
**Description:** `date_filter` (or extended search tool): month, range, nights, "return before X". Explicit `_map_tool_result_to_component` branch; system-prompt rule so the model calls the tool rather than answering dates in prose.
**Rationale:** Delivers "all October sailings", "14-day returning before Dec 28". Depends on #2.
**Downsides:** Date-parsing edge cases (relative dates, year inference).
**Confidence:** 85%
**Complexity:** Medium
**Status:** Explored

### 4. Near-Miss Alternatives — Tool-Enforced, Never Replacing
**Description:** Exact matches first; clearly-labeled "close alternatives" appended (11-night when user said >10, ±7 days, next tier). Zero results → auto-relaxed re-search. Logic lives in the tool handler, not Gemini's discretion.
**Rationale:** User's explicit "give options, don't hide the 11-day" requirement; dead-end queries become discovery.
**Downsides:** Labeling must be unambiguous or it reads as ignoring the user's constraint.
**Confidence:** 85%
**Complexity:** Medium
**Status:** Explored

### 5. Rich Draft Identity + Price-Divergence Display
**Description:** Session snapshot per draft gains cruise name, dates, nights, draft-held total (e.g. 3300, not base 3000). Rail tile shows draft-held price + "includes $300 add-ons" divergence note. Catalog stays source-of-truth for base price.
**Rationale:** Prerequisite for switching among multiple same-region drafts (user's exact scenario).
**Downsides:** Snapshot grows per paid Gemini turn (cost caps exist).
**Confidence:** 90%
**Complexity:** Medium
**Status:** Explored

### 6. Conversational Draft Context Switching
**Description:** System-prompt rule: reference to an existing draft → `set_active_draft` (comparison table forbidden for single-draft references); 2+ candidate drafts → inline disambiguation card (name/dates/price, tap to resolve); no matching draft → fresh catalog search. UI: highlight ring + scroll-into-view on the switched rail card.
**Rationale:** User ask #4 end-to-end — "back to dinner options in Alaska" just switches context. Depends on #5.
**Downsides:** LLM judgment call — needs explicit rule + stub-mode tests (documented freeload pattern); disambiguation card is a new component + registry entry.
**Confidence:** 80%
**Complexity:** Medium-High
**Status:** Explored

Dependency chain: 1 standalone · 2 → 3 → 4 · 2+5 → 6.

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Click-draft synthetic assistant message | Fragile in function-calling history; visual feedback in idea #6 covers the need |
| 2 | Voice-mode draft switching | Already wired — Realtime relay → /action bridge handles set_active_draft |
| 3 | Persistent session store (Redis/SQLite) | Demo stage; zero user-visible payoff, off-focus |
| 4 | Tool→component registry refactor | Already declarative (`componentRegistry.tsx`) — idea wrong about repo |
| 5 | Itinerary/ports data + tool | `get_itinerary` already exists; off-focus scope creep |
| 6 | Urgency nudges (remaining_at_fare etc.) | No date fields yet to compute from; hallucination risk |
| 7 | Checkout availability re-check | No real inventory — theater |
| 8 | Catalog to 100+ sailings | Gold-plating; ~36 suffices for demo credibility |

## Session Log
- 2026-07-21: Initial ideation — 41 raw ideas from 5 framed agents, merged to 19 candidates + 2 synthesized bundles, 6 survived adversarial filtering. All 6 selected for brainstorm as one feature set.
