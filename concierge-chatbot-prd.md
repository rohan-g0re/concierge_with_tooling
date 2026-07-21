# PRD — "Compass" Conversational Booking Concierge (HAL-style demo)

Version 1.0 · Owner: Rohan Gore · Purpose: interview demo for HAL/Seabourn AI Innovation Analyst role.
Build contract: this PRD + the companion Claude Design output are the two inputs to Claude Code. Stack is fixed: **Next.js (frontend) + FastAPI (backend) + Gemini (LLM, function calling) + OpenAI GPT Realtime (voice)**. Anything not specified here is implementer's choice, but nothing specified here may be silently changed.

---

## 1. Product summary

A chat-first cruise concierge that goes beyond "list cruises + Book Now links" (the Nora/Anna pattern) to **action-level booking construction inside the conversation**: guests search in natural language, then *build* their booking — fare package, stateroom, dining, excursions, land-tour days — through interactive tiles in the chat, across **multiple parallel itinerary drafts** (e.g., an Alaska draft and a Mexico draft in one session), compare drafts side-by-side, and exit to a checkout page that **resumes exactly at the first incomplete step**. Voice parity via GPT Realtime.

**The one-line differentiator:** competitors' bots *answer*; this one *assembles*. Every reply that can be an action is an action, not text.

## 2. Goals / Non-goals

**Goals**
G1. Demonstrate action-level conversational booking (measurable: every customization reachable via tile interaction, zero copy-paste steps).
G2. Demonstrate durable multi-draft session state (switch topics mid-flow without losing work).
G3. Demonstrate comparison + deep-link checkout resume.
G4. Demonstrate voice parity (same tools, same state, spoken).
G5. Look unmistakably premium/HAL-branded (handled by companion design).

**Non-goals**
N1. Real payments, auth, or real HAL inventory (synthetic catalog; checkout stops at a mock "Reserve" confirmation).
N2. Multi-session persistence (session-scoped state only; refresh survives via sessionStorage, browser close does not).
N3. Support/FAQ breadth (Anna's job). Off-catalog questions get one graceful answer + redirect to booking context.
N4. Real dynamic pricing (static synthetic fares + truthful scarcity fields; see §7.9).

## 3. Personas

P1 **The Planner** (primary): 55+, researching a bucket-list Alaska trip, medium tech comfort, hates re-entering information.
P2 **The Comparer:** evaluates 2–3 options across regions before committing; wants side-by-side truth, not sales pressure.
P3 **The Travel Advisor:** books on behalf of clients; values speed, precision, and a shareable summary.

## 4. Use cases (UC) — each is also a demo-day test case

Format: trigger → expected behavior → acceptance criterion (AC).

**UC-01 Natural-language search.** "Show me Alaska cruises" → assistant returns ≤5 result cards (popularity-ranked from catalog `popularity_score`), with a text preamble ≤3 sentences. AC: cards render inside chat; each card shows duration, name, embark port, ship, strike-through + current fare, Book Now-equivalent (here: "Select"), "See itinerary."
**UC-02 Conversational refinement.** "Only 10+ days" → previous result set re-filtered in place (new message, ≤5 cards, possibly fewer). AC: filter composes with prior constraints; assistant states the active filter set in one line.
**UC-03 Compound query.** "Alaska, 6–8 days, from Seattle, under $4,000" → single-shot multi-constraint parse. AC: all four constraints extracted to the tool call (visible in a collapsible "reasoning" dev panel); results satisfy all constraints.
**UC-04 Itinerary detail.** Tap "See itinerary" or ask "what do we see before Glacier Bay?" → day-by-day panel; question answered from that itinerary's data only. AC: day list matches catalog; answer cites day numbers.
**UC-05 Select → draft creation.** Tap "Select" on a card → a **Draft** is created ("Alaska · Nieuw Amsterdam · Jul 12"), pinned in a draft rail; booking-step tracker appears (see §6). AC: draft persists across subsequent topic changes.
**UC-06 Action-level customization — fare.** Assistant proactively offers Step-3 tile: Standard vs. Have It All (with included-amenity list and price delta). Tap to choose. AC: choice is stored to draft; tracker marks step complete; no free-text needed.
**UC-07 Action-level customization — stateroom.** Tile grid of categories (Inside/Ocean View/Verandah/Suite) with per-category fare deltas; then a location picker (deck fore/mid/aft simplified). AC: selection updates draft total price live.
**UC-08 Action-level customization — dining & cuisine.** "What are the dining options?" → not prose: a tile set of venues (Main Dining, Pinnacle Grill, Tamarind, Canaletto…) each with cuisine tag, price, and **Reserve night** action (night picker constrained to sailing length, capacity-aware: sold-out nights disabled). AC: reserved nights appear in draft; a full venue/night cannot be double-booked.
**UC-09 Land-tour builder (cruisetours).** For Alaska cruisetour products: "build my land days" → per-day tile chooser (Denali lodge nights, domed-rail Talkeetna→Denali, Fairbanks add-on) with conflict checking (no overlapping days). AC: invalid combinations are unselectable, with reason on hover.
**UC-10 Mid-stream topic switch.** While customizing Alaska: "actually show me Mexico cruises" → new search runs; Alaska draft remains pinned with progress intact. AC: zero data loss; draft rail shows both.
**UC-11 Second draft customization.** Select a Mexico cruise, customize partially. AC: two drafts, independent step trackers.
**UC-12 Side-by-side comparison.** "Compare my Alaska and Mexico options" → comparison view: two columns, aligned rows (dates, nights, total price as customized, fare package, stateroom, dining reservations, land days, cancellation terms). AC: values reflect *customized* drafts, not base products; max 3 drafts compared (hard limit, stated politely if exceeded).
**UC-13 Checkout deep-link + resume.** "I'll take the Alaska one" → hand-off card with **Continue to checkout** → dedicated checkout page rendering the draft; if steps 1–3 of 5 are complete, page opens **at step 4** with 1–3 shown as editable summary rows. AC: completed data pre-filled; URL encodes draft id; back-to-chat link preserves session.
**UC-14 Follow-up suggestion chips.** After every assistant turn: 2–3 "You can also try" chips, contextual to state (e.g., after stateroom step: "Compare Verandah vs Suite," "What's Club Orange?"). AC: chips are tappable, populate as user message.
**UC-15 Voice session (GPT Realtime).** Mic toggle → spoken "find me a two-week Alaska cruisetour" → same tool calls, cards render on screen while assistant speaks a ≤2-sentence summary. Barge-in supported. AC: voice and text share one session/draft state; transcript appears in chat.
**UC-16 Voice → action continuity.** Spoken: "reserve Pinnacle Grill on the second formal night" → dining tool call with night resolution; tile confirmation renders; assistant confirms verbally. AC: draft updated identically to tap path.
**UC-17 Scarcity honesty.** Where catalog marks a category/venue low (`remaining ≤ threshold`), tiles show "3 left at this fare" — sourced only from catalog fields. AC: no urgency copy without a backing data field (auditable).
**UC-18 Graceful off-scope.** "What's the wifi password onboard?" → one-line answer-or-deflect + return to context. AC: no hallucinated policy claims; response ends with a contextual next action.
**UC-19 Session recovery.** Page refresh → chat history, drafts, and step state restored. AC: sessionStorage hydration; new tab = new session.
**UC-20 Feedback.** Thumbs up/down per assistant message, logged with message id + state snapshot. AC: POST fires; no UI dead-ends.

## 5. Screens & components (derived from UCs — this is the design-prompt inventory)

S1 **Chat Shell** — message stream, composer, mic toggle, "Start new chat," draft rail (right side, collapsible), dev/reasoning panel (collapsed by default).
S2 **Result Card Row** — up to 5 horizontally scrollable cruise cards (image, duration badge, name, embark, ship, strike-through fare → current fare, "Best Value"-style badge slot, Select + See Itinerary actions).
S3 **Itinerary Panel** — slide-over: day-by-day timeline, port thumbnails, map strip, "Ask about this itinerary" affordance.
S4 **Step Tracker** — 5-step horizontal tracker per draft (Sailing ✓ → Fare → Stateroom → Add-ons → Review), current step highlighted.
S5 **Fare Package Tiles** — two large comparative tiles (Standard / Have It All) with included-amenities checklist and delta price.
S6 **Stateroom Picker** — category tile grid with fares; second row: location segment control; live draft-total readout.
S7 **Dining & Experience Tiles** — venue cards with cuisine tags + Reserve-night popover (night grid, disabled sold-out nights, "3 left" chips).
S8 **Land-Tour Builder** — day-slot builder for cruisetours with conflict-disabled options.
S9 **Draft Rail / Draft Chips** — pinned drafts with mini progress rings; tap to switch active draft context.
S10 **Comparison View** — 2–3 column aligned-row comparison, per-column "Continue to checkout."
S11 **Checkout Page** (separate route) — step-resume layout: completed steps as compact editable rows, active step expanded, order summary sidebar, mock Reserve CTA.
S12 **Voice Overlay** — waveform/listening state, live transcript line, barge-in hint, end-voice control.
S13 **Suggestion Chips** — "You can also try" row, 2–3 chips.
S14 **Handoff/Confirmation Card** — end-of-flow card summarizing draft + checkout link (and mock confirmation state).

## 6. Booking-step model (mirrors HAL's real flow, simplified to 5)

Step 1 Sailing (product selected) → Step 2 Fare package (Standard | Have It All) → Step 3 Stateroom (category + location) → Step 4 Add-ons (dining reservations, excursions, land-tour days, Club Orange toggle) → Step 5 Review/guest details (mock).
`draft.completed_steps ⊆ {1..5}`; checkout entry = `min(missing step)`. Add-ons is completable-empty (explicit "skip add-ons" action marks it complete). This model is the single source of truth for tracker UI, resume logic, and comparison rows.

## 7. Functional requirements (numbered; Claude Code treats each as a ticket)

**7.1 Session & state.** One server-side session object (FastAPI, in-memory dict keyed by session id; sessionStorage mirror client-side). Shape:
```json
{ "session_id": "...", "messages": [...],
  "constraints": { "region": null, "nights_min": null, "nights_max": null,
                    "embark_port": null, "budget_max": null, "party": 2 },
  "drafts": [ { "draft_id": "d1", "cruise_id": "AK-1412", "label": "Alaska · 12d",
                 "fare_package": "have_it_all", "stateroom": {"category":"verandah","location":"mid"},
                 "dining": [{"venue_id":"pinnacle","night":5}],
                 "land_days": ["denali_2n"], "addons": {"club_orange": false},
                 "completed_steps": [1,2,3], "total_price": 6842 } ],
  "active_draft": "d1" }
```
**7.2 LLM orchestration (Gemini).** Single Gemini chat with function calling. Tools (all return structured JSON the frontend renders as components — the model never renders UI itself):
- `search_cruises(constraints) → cruise_card[] (≤5, popularity-ranked)`
- `get_itinerary(cruise_id) → day[]`
- `create_draft(cruise_id)` / `set_fare(draft_id, package)` / `set_stateroom(draft_id, category, location)`
- `list_dining(cruise_id) → venue[] (with per-night availability)` / `reserve_dining(draft_id, venue_id, night)`
- `list_land_options(cruise_id)` / `set_land_days(draft_id, option_ids)` (server validates conflicts)
- `compare_drafts(draft_ids[]) → aligned comparison table object`
- `handoff_checkout(draft_id) → {url}`
System prompt requirements: concise preambles (≤3 sentences before cards), always propose the next booking step after any action, never invent catalog facts (answers about products must follow a tool call), always end with suggestion-chip candidates (model emits 2–3 as structured field on every turn).
**7.3 Response contract (backend → frontend).** Every assistant turn is SSE-streamed: `{text_delta}` events + terminal `{components: [card_row | tiles | tracker_update | comparison | handoff], chips: [..]}`. Frontend renders components beneath the text bubble. No component data ever travels as markdown-in-text.
**7.4 Tile actions are tool calls too.** Every tap (Select, fare tile, night reservation…) POSTs the same tool the model would call, then appends a compact system-visible event to the conversation ("user selected Verandah, mid-ship") so the model's next turn is state-aware. One action path, two entry points (tap | language | voice) — this is the architectural heart of the demo; do not fork logic per input mode.
**7.5 Multi-draft rules.** Draft cap 3 (graceful refusal beyond). Topic-switch never mutates existing drafts. `active_draft` follows last user focus (explicit tap, or model inference from language: "on the Mexico one…").
**7.6 Comparison.** Server-computed aligned rows (never model-freeform): dates, nights, ship, fare package, stateroom, dining count, land days, per-person + total price, deposit/cancellation (synthetic terms), scarcity flags. Differences auto-highlighted.
**7.7 Checkout resume.** `/checkout/[draft_id]` route, server-rendered from session; opens at first incomplete step; each completed step row has Edit (returns to inline editing on the page, not back to chat). "Return to concierge" preserves everything.
**7.8 Voice (GPT Realtime).** WebRTC client ↔ OpenAI Realtime; backend mints ephemeral session tokens (`POST /voice/token`). Realtime session is configured with the *same tool schemas*; tool calls are relayed to the same FastAPI handlers; text transcript of both sides is appended into the Gemini-visible history so modality switches are seamless. Spoken responses ≤2 sentences when cards are on screen ("I've put three options on your screen — the 12-day Nieuw Amsterdam sailing fits best; want me to walk through it?"). Barge-in on; echo of UI state (tracker/tiles) rendered normally.
**7.9 Scarcity honesty rule (hard).** Any urgency string must interpolate a catalog field (`remaining_at_fare`, `historically_sells_out_weeks`, `holiday_overlap`). Copy templates live server-side; the model may *choose* to surface, never author, scarcity claims. (This mirrors the dynamic-pricing doc's "reasons, not predictions" principle and is an interview talking point.)
**7.10 Guardrails.** Off-catalog/competitor/policy questions → single-line bounded answer + redirect (UC-18). No PII collected beyond first name. Prompt-injection: tool results and catalog text are data, never instructions; system prompt asserts this and the demo script includes one injection attempt to show it failing safely.
**7.11 Catalog (synthetic).** ~24 cruises across Alaska (incl. 4 cruisetours), Mexico, Caribbean, Mediterranean; JSON files loaded at boot; every card image from a local `/public/ports/*` set (no hotlinking). Fields must include everything §5–§7 renders, incl. `popularity_score`, per-venue per-night `capacity_remaining`, scarcity fields, strike-through vs. current fare.
**7.12 Observability (demo-grade).** Every tool call + latency logged; thumbs feedback logged with state snapshot; a `/debug` route lists session state live (useful during the interview if asked "what's it doing under the hood").

## 8. Architecture

```
Next.js (App Router, TS, Tailwind)                     FastAPI (Python 3.11)
┌───────────────────────────────┐    SSE / REST     ┌──────────────────────────────┐
│ Chat UI · tiles · drafts rail │ ◄───────────────► │ /chat (Gemini orchestrator)  │
│ Checkout route · /debug       │                   │ /action/* (tile→tool bridge) │
│ Voice client (WebRTC) ────────┼──── ephemeral ────┤ /voice/token                 │
└───────────────────────────────┘      token        │ Session store · Catalog svc  │
        ▲  audio (WebRTC)                           │ Comparison/conflict engines  │
        └───────────── OpenAI GPT Realtime ◄──tool relay──┘        (Gemini API)
```
Key decisions (justify-if-asked): Gemini for the text orchestrator (cheap, fast function calling; provider-agnostic proxy pattern keeps it swappable — mirrors your Voice Agent proxy design); Realtime only for the audio loop; all business logic server-side in plain Python (testable without any LLM); component-driven responses instead of markdown parsing (deterministic rendering, no regex fragility).

## 9. Non-functional requirements

Latency: first text token <1.5s p50; card row <3.5s p50 (parallelize tool + preamble). Streaming always on. Empty/error states designed for every component (no blank panes on tool failure — retry affordance + apology line). Desktop-first 1280px, gracefully down to 768px. Accessibility: full keyboard nav on tiles, aria-labels, visible focus. All statefully-rendered money values formatted server-side (single source of rounding truth).

## 10. Acceptance demo script (the 5-minute path)

1) UC-03 compound Alaska search → 2) UC-04 itinerary question → 3) UC-05–08 select + fare + stateroom + one dining reservation (tiles only, no typing) → 4) UC-10–11 "show me Mexico" + quick partial customization → 5) UC-12 compare → 6) UC-13 checkout resume at step 4 → 7) UC-15 one voice exchange ("swap dining to the last sea night") → 8) point at /debug once. Rehearse to ≤4:30.

## 11. Build order for Claude Code

M1 catalog + session + tools (pure Python, unit-tested) → M2 /chat SSE with Gemini + text-only → M3 component contract + cards/tiles in Next.js → M4 drafts/tracker/comparison → M5 checkout route → M6 voice → M7 polish per design file, demo-script hardening. Do not start M6 before M4 passes UC-10–12.
