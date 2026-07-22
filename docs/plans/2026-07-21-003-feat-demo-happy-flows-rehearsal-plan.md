---
title: "feat: Interview Demo — Three Happy-Flow Scripts + Live Playwright Rehearsal"
type: feat
status: active
date: 2026-07-21
origin: docs/plans/2026-07-21-002-feat-pinned-ui-dates-draft-context-plan.md
---

# feat: Interview Demo — Three Happy-Flow Scripts + Live Playwright Rehearsal

## Overview

Compass (Meridian Line cruise concierge) is feature-complete for the interview demo: live Gemini function-calling chat over SSE, dated 6-region catalog (31 cruises / 482 sailings), date filtering with deterministic near-miss sections, a 5-draft rail with rich identity (dates, nights, port, draft-held total, hover-delete), conversational draft switching with which-one disambiguation, pinned chrome, and checkout resume.

This plan does three things:

1. **Scripts three comprehensive happy flows** — realistic guest messages plus edge-case messages, each step with an expected result and a full verification checklist.
2. **Defines the cross-flow composability guarantee** — the presenter may start Flow A, jump to a Flow C step, and return; every step's precondition is expressed in terms of session state (drafts present, active draft, prior search), not flow position.
3. **Rehearses all three flows end-to-end in the real browser (Playwright, LIVE Gemini — user-selected)**, validating every step's checklist; any defect found is fixed immediately and the entire flow restarts from scratch. Repeat until each flow passes clean top-to-bottom. Includes a technical Q&A prep sheet for post-demo questions.

## Problem Frame

This demo will be shown live in an interview. A single broken step (empty card row, stale rail highlight, composer scrolled away, debug pill) costs more than any feature adds. The demo must survive improvisation: the presenter will mix steps across flows in an unplanned order. Therefore: three scripted flows that collectively cover every feature surface, verified step-by-step under the exact conditions of the demo (live Gemini, real browser), with a fix-and-full-restart discipline so no fix is ever trusted without re-running its whole flow.

## Requirements Trace

- D1. Three happy-flow scripts with realistic + edge-case guest messages, each step carrying expected result and verification checklist.
- D2. Flows are cross-composable: any step's preconditions are session-state-based; mixing steps across flows must not break.
- D3. Every step verified in live-Gemini Playwright rehearsal: UI change correct, results correct, autoscroll to newest message, composer always visible/typable, rail always visible with correct active highlight and totals, no console errors, no unknown-component debug pills.
- D4. Any defect found → fixed immediately (implementer per project CLAUDE.md hierarchy) → the COMPLETE flow restarts from step 1. A flow only passes when it runs clean end-to-end without intervention.
- D5. Technical Q&A prep: implementation talking points for post-demo technical questions.
- D6. Fixes are committed per verified defect batch; the demo-ready state is committed.

## Scope Boundaries

- No new features. Only defects surfaced during rehearsal are fixed — minimal, targeted changes.
- Voice is NOT part of the demo (OPENAI_API_KEY is a placeholder; graceful-degradation mode). Do not script voice steps.
- Checkout completes to the resume/deposit screen only — no payment simulation beyond what exists.
- Live-model phrasing variance is acceptable; verification asserts tool calls, components, and state — not exact assistant wording.
- No load/perf testing; single-session rehearsal only.

## Context & Research

- All feature surfaces built and unit/stub-verified this session (see origin plan; commits `2d88686`..`483567e`).
- `docs/solutions/` learnings apply: every tool needs mapper branches in both `backend/app/llm/gemini_client.py` and `backend/app/routes/action.py`; explicit system-prompt rules prevent Gemini prose-freeloading; snapshot lists exact draft ids. After any backend change, guarantee a fresh server before restarting a flow: the currently-running uvicorn may not be reloading — kill :8000 and relaunch is the safe path (README supports `--reload`, but never trust a stale process during rehearsal).
- Live env: `GEMINI_API_KEY` real in `backend/.env` (backend cwd must be `backend/`); model `gemini-flash-latest`; `LLM_MODE` unset → auto → live. Frontend `npm run dev` on :3000. Playwright browser viewport 1920×1080; clear stale HMR console noise before judging errors.
- Known open observations from the live spot-check (candidates to confirm/fix during rehearsal): (a) rail highlight briefly lagged backend `active_draft_id` after a live conversational switch; (b) incidental-mention reply fell back to generic greeting boilerplate instead of a contextual acknowledgment.

## Key Technical Decisions

- **Rehearse ALL LIVE (user-selected).** Every rehearsal message is a paid flash turn, including post-fix restarts. Accepted for maximum demo fidelity.
- **Verification asserts state, not prose.** Live Gemini phrasing varies run-to-run; checklists assert tool calls fired, components rendered, session state (drafts/active/totals) via `GET /session`, and layout invariants.
- **Fix-and-full-restart discipline (user requirement).** After any fix, the flow restarts at step 1 — never resume mid-flow. Backend fixes require killing :8000 and relaunching live before restart. To reconcile with all-live: a fix may be *validated* in stub mode as a development step (free), but that never counts as a rehearsal run — every counted rehearsal pass is live end-to-end.
- **Demo-ready bar (single pass is plausibility, not reliability).** A flow is demo-ready when it completes ONE full clean live pass AND its model-compliance risk steps (A7, B7, C4–C7) have each been observed clean in at least TWO live runs total (across restarts or a targeted re-run). Live sampling varies; the double-observation requirement covers the steps where the model itself is the enforcement mechanism.
- **Fix-cycle cap.** If a flow cannot produce a clean pass after 3 fix→restart cycles, STOP and report to the user with the defect analysis rather than looping.
- **Composability via state-based preconditions.** Each step lists preconditions like "≥2 drafts exist, one Alaska" rather than "after step 4", so improvised orderings still hold.

## Universal Per-Step Verification Checklist (applies to EVERY step of every flow)

1. **Autoscroll:** after the assistant turn completes, the newest message/component is in view (chat scrolled to bottom).
2. **Composer:** textarea visible in viewport, focusable, typable — regardless of prior scrolling.
3. **Rail:** fully visible; active draft has the gold ring; card data (dates line, nights, draft-held total, addons note) matches `GET /session`.
4. **Components:** expected component types rendered (no unknown-type debug pills, no empty card rows).
5. **Console:** no NEW console errors (ignore documented stale-HMR artifacts; verify against source before treating as real).
6. **Network:** the expected tool/action calls returned 200 (`/chat` SSE completed; `/action/*` 200).
7. **Session truth:** `GET /session` reflects the expected drafts count, active_draft_id, and totals after the step.

---

## The Three Happy Flows

### Flow A — "October in Alaska" (core funnel: date search → near-miss → date pick → draft → add-ons → pricing truth → checkout)

*Story: a guest who knows roughly when but not what. Shows date filtering, tool-owned near-miss labels, the sailing date-picker on tiles, draft birth with a date, draft-held vs base pricing, and checkout resume.*

| # | Guest message / action | Expected result | Extra checks beyond universal list |
|---|---|---|---|
| A1 | Click **Start New Chat** | Fresh session; empty transcript; rail empty | sessionStorage cleared; `GET /session` has 0 drafts |
| A2 | "Hi! I'm dreaming about seeing glaciers — do you have anything in Alaska this October?" | `search_cruises` fires with region=alaska, month=10; dated card tiles, ALL visible departures in October; a separate labeled section "Sailings within a week of your dates" may follow | Exact-match section first and unpolluted; each tile shows "Departs … · Returns …" + date `<select>`; label text verbatim from tool |
| A3 | On one tile, open the date `<select>`, choose a DIFFERENT October sailing (e.g. Oct 14), then click **Select** | Draft created anchored to the CHANGED sailing | `/action/create_draft` carries the chosen sailing_id; rail tile dates line == chosen sailing; `GET /session` departure_date == changed date |
| A4 | Click chip **Choose fare package** → pick the premium package tile | Fare tiles render; picking updates tracker + rail total rises | rail total > base; tracker shows step complete. Chip labels are live-model-generated: match by partial text / pick the fare-related chip; a differently-worded chip is variance, not a defect |
| A5 | "What's my total looking like so far?" | Assistant quotes the DRAFT-HELD total exactly (matches rail + `GET /session total_formatted`) — never the catalog base | PRICING RULE holds; addons note visible on rail if delta > 0 |
| A6 | "What will I actually see on this cruise — walk me through the itinerary" | `get_itinerary` fires; itinerary component renders for the active draft's cruise | no prose-only itinerary |
| A7 | Edge-case message: "hmm, would nights even be dark enough for northern lights in early October?" | Conversational reply (no tool required); NO spurious search/switch; session unchanged | drafts count and active unchanged |
| A8 | "Great — let's lock this in. How do I pay the deposit?" | Checkout affordance/link appears (Handoff component fires via `handoff_checkout` tool); clicking opens checkout with deposit/balance breakdown for the draft-held total | checkout totals == draft-held total. Pre-rehearsal check (R1): verify the system prompt forces `handoff_checkout` on pay/deposit/book intent; if live Gemini freeloads in prose here, that IS a defect (add/strengthen the forced-tool rule) |

### Flow B — "Back before Dec 28" (constraint shopper: duration+return-by → exact vs labeled alternatives → zero-match rescue → second draft → conversational switch → explicit compare)

*Story: a guest with hard constraints. Shows combined filters, never-replaced exact matches, the zero-match no-dead-end path, multi-draft creation, single-reference switching (no comparison table), and comparison only on explicit ask.*

| # | Guest message / action | Expected result | Extra checks |
|---|---|---|---|
| B1 | **Start New Chat** | Fresh session | 0 drafts |
| B2 | "I have exactly two weeks off and must be back before Dec 28 — what 14-day cruises fit?" | `search_cruises` nights 14/14 + return_by 2026-12-28; exact 14-night section first (every card returns ≤ Dec 28); labeled section below e.g. "Options outside your 14-night request" | exact section contains ONLY 14-night; labels verbatim; every card's return date ≤ Dec 28 in exact section |
| B3 | Select a 14-night tile (keep default sailing) | Draft 1 created with the tile's context-matched sailing | rail dates == tile dates |
| B4 | Edge-case: "do you have any 20-day expeditions?" | NO exact match exists → "no exact matches" message + `no_exact` sections with ≥1 non-empty alternative group (e.g. "Options outside your 20-night request") — NOT an empty state, NOT a silent happy-path list | exact-match section empty; ≥1 labeled alternatives section non-empty. Requires Gemini to emit BOTH `nights_min=20` and `nights_max=20` (schema uses nights_min/nights_max, no single `nights` param) — a region-only search here is a routing defect |
| B5 | "Ok the long ones don't fit. What about a short Bermuda getaway instead?" | Fresh search, bermuda_bahamas region, 5–7-night dated tiles | region mapping correct |
| B6 | Select a Bermuda tile | Draft 2 created | rail shows 2 drafts; new one active |
| B7 | "Actually, let's go back to the two-week one" | `set_active_draft` fires; active switches to Draft 1; NO comparison table; rail highlight moves + scrolls into view | single-reference switch; `GET /session` active == draft 1 |
| B8 | "Now compare my two drafts side by side" | Comparison table renders (explicit compare intent only) | comparison appears ONLY here |
| B9 | "Which one's cheaper per night? Give me your honest recommendation" | Conversational reply grounded in the two draft-held totals (numbers match rail); no invented prices | quoted figures ∈ {draft totals, catalog fares shown} |

### Flow C — "The Alaska juggler" (multi-draft identity: same-region drafts → which-one cards → attribute-specific switch → incidental-mention guard → hover-delete → no-draft fallback search)

*Story: a realistic returning guest with several Alaska drafts. Shows rich draft identity, disambiguation cards, duration/date-specific resolution, the incidental guard, draft deletion, and fresh-search fallback.*

| # | Guest message / action | Expected result | Extra checks |
|---|---|---|---|
| C1 | **Start New Chat** | Fresh session | 0 drafts |
| C2 | "Show me Alaska cruises" | Dated Alaska tiles (next-upcoming sailings) | flat card row (no date constraint → no sections) |
| C3 | Compound step with intermediate checkpoints: (a) Select a 7-night Alaska cruise (e.g. Glacier Discovery) → rail shows 1 draft, active; (b) select a 12-night Alaska cruise (e.g. Denali Explorer) → rail 2, new one active; (c) "show me Mexico cruises" → Mexico tiles; (d) select one → rail 3 | 3 drafts: 2 Alaska (7n, 12n) + 1 Mexico | verify rail count + active after EACH sub-action (a/b/d), not just at the end — pinpoints which selection breaks if one does |
| C4 | "Let's get back to the Alaska one" | AMBIGUOUS (two Alaska drafts) → which-one candidate cards render (name, dates, nights, US$ price; current badge on active if Alaska); active UNCHANGED until tap | draft_disambiguation component, 2 candidates, NOT a debug pill |
| C5 | Tap the 7-night candidate card | Switch to that draft; rail gold ring moves + scrolls into view | `/action/set_active_draft` 200; `GET /session` active == 7n draft |
| C6 | "Actually the 12-day one — I want to talk dining on that one" | Duration-specific reference → DIRECT switch to the 12-night Alaska draft (no which-one card) | weighted resolution: no disambiguation |
| C7 | Edge-case: "my friend went to the Caribbean last year and loved it" | NO switch, NO search — plain conversational reply; session untouched | no set_active_draft, no card_row |
| C8 | Hover the Mexico draft tile → click the "×" | Mexico draft removed; rail count 3→2; active draft unaffected (or correctly reassigned if it was active) | `/action/remove_draft` 200; `GET /session` 2 drafts |
| C9 | "What about Hawaii? Anything good there?" | No Hawaii draft exists → FRESH `search_cruises` for hawaii; FLAT dated card row (no date constraint → no sections, same rule as C2); tiles will show 10–15 nights because that's the Hawaii catalog, but nights is NOT an asserted filter | fallback path; drafts count unchanged |
| C10 | "Which of these Hawaii ones would you pick and why?" | Conversational recommendation over the visible Hawaii results (may re-present cards); prices quoted = catalog base (no draft exists for them); NO draft is created in this step (conversational only — post-step draft count unchanged) | PRICING RULE inverse: base fare quoted for draft-less cruises |

### Cross-Flow Composability Matrix (D2)

Preconditions per step family — mixing steps is safe when the precondition column holds:

| Step family | Precondition (session state) |
|---|---|
| Any search (A2, B2, B4, B5, C2, C9) | none |
| Tile Select / date-change Select (A3, B3, B6, C3) | search results visible; < 5 drafts |
| Add-on chip steps (A4) | ≥1 draft, active |
| Pricing question (A5, B9, C10) | for draft-held: ≥1 draft; for base: none |
| Itinerary (A6) | active draft exists |
| Single-ref switch (B7, C6) | a UNIQUELY resolvable draft matching the reference |
| Which-one (C4, C5) | ≥2 drafts matching the reference equally |
| Incidental guard (A7, C7) | any |
| Hover-delete (C8) | ≥1 draft |
| Compare (B8) | ≥2 drafts |
| Checkout (A8) | active draft exists |

Danger zones for improvisation (presenter notes): draft cap is 5 — deleting via "×" frees slots; "the Alaska one" with only ONE Alaska draft switches directly (no card) — need 2+ for the disambiguation moment; chips fire paid turns in live mode (fine in demo).

---

## Technical Q&A Prep Sheet (D5)

Talking points if the interviewer digs in:

1. **Architecture:** Next.js 14 App Router frontend; FastAPI backend; chat over SSE (`POST /chat` streams text + component descriptors); UI-initiated actions over `POST /action/{tool}` (free path, same tool registry). In-memory sessions + sessionStorage mirror — deliberate demo scope, swap-in Redis is isolated behind the session module.
2. **LLM orchestration:** Gemini `gemini-flash-latest` agentic function-calling loop (`backend/app/llm/gemini_client.py`). Single `TOOL_REGISTRY` (name → handler + JSON schema) drives BOTH the Gemini tool declarations and the `/action` bridge and voice relay — one source of truth, three transports.
3. **Why deterministic near-miss in the tool, not the model:** flash "freeloads" — answers in prose and skips tools unless forced. Relaxation ladder (±3 nights → nearest-nights fallback, ±7-day date shift, adjacent regions) computed in `search_cruises`; the model renders tool-owned section labels verbatim. System prompt carries forced-tool rules (DATE FILTER RULE, DRAFT SWITCH RULE, COMPARE DRAFTS RULE, PRICING RULE).
4. **Draft identity + switching:** every draft is born with a concrete sailing (chosen/confirmed at tile selection). Per-turn session snapshot injects one terse line per draft (id, label, region, port, dep/ret, nights, draft-held total) — the model resolves "the 7-day Alaska one" against real ids, never invents them. Ambiguity → `disambiguate_drafts` tool → tappable which-one cards carrying `draft_id`.
5. **Pricing truth:** catalog is source of truth for base fares (`fare_now` never mutates); each draft accumulates its own held total (base × party + add-ons). PRICING RULE: draft-held total for drafts, base for anything else, never invent.
6. **Component mapping discipline:** every tool result maps to a typed descriptor in TWO mirrored mappers (Gemini path + /action path) with parity tests; unknown types render a visible debug pill so gaps can't hide.
7. **Testing strategy:** `LLM_MODE=stub` — deterministic keyword orchestrator mirroring the live routing (same tools, same components) → 242 backend tests run free; live-path tests inject a FakeClient over the google-genai SDK; capped live spot-checks for model-behavior assertions.
8. **Dates:** seeded sailing series (deterministic script, `DEMO_ANCHOR=2026-07-01`, 482 sailings); year inference resolves "before Dec 28" to the next occurrence ≥ anchor.
9. **Cost discipline:** stub for development, live turns budgeted; chips/actions routed through the free `/action` path where possible.

---

## Implementation Units

- [ ] **Unit R1: Environment reset + demo runbook**

**Goal:** Clean, reproducible live demo environment; documented start procedure.

**Files:** Create: `docs/demo/demo-runbook.md` (start commands, flow scripts A/B/C in presenter form, danger-zone notes).

**Approach:** Kill stale servers; start backend LIVE (from `backend/`, no LLM_MODE, `.env` read from cwd, port 8000) + frontend :3000; browser 1920×1080; Start New Chat. Runbook contains the three flow tables + composability matrix in presenter-friendly form, PLUS:
- **Pre-rehearsal static checks:** system prompt contains a forced-tool rule covering pay/deposit/book intent → `handoff_checkout` (add one if missing — A8 depends on it); `search_cruises` schema declares `nights_min`/`nights_max` (no single `nights`); DRAFT SWITCH RULE's incidental-mention guard present.
- **Demo-day emergency fallback:** documented stub-mode start command (`LLM_MODE=stub`) as the contingency if Gemini is down/rate-limited at the interview — the whole demo runs deterministically in stub with identical UI; plus screenshots from the clean rehearsal passes as last-resort visuals.
- **Presenter micro-notes:** hover-delete "×" needs a deliberate hover-then-click (narrate it); feedback thumbs render under every reply — don't click accidentally; chips vanish while streaming and repopulate after; autoscroll follows streaming tokens — don't fight the scroll mid-stream, scroll back after the turn completes.

**Verification:** Both servers respond; a fresh session renders; runbook exists; all three static checks pass (or fixes landed).

- [ ] **Unit R2: Flow A live rehearsal (fix → full restart loop)**

**Goal:** Flow A passes A1–A8 clean end-to-end under live Gemini.

**Approach:** Per project CLAUDE.md: Fable verifier spawns a Sonnet general-purpose foreground worker executing every step via Playwright MCP, applying the universal checklist + per-step extra checks, returning screenshots + `GET /session` payloads per step. ANY failure → root-cause → fix via implementer (Sonnet, Opus on failure) → backend restart if backend touched → **restart Flow A from A1**. Repeat until clean. Commit fixes.

**Test scenarios:** the A1–A8 table IS the test set (each row: action → expected → checks).

**Verification:** One uninterrupted clean pass of A1–A8; evidence archived under `.claude/demo_rehearsal/flowA/`.

- [ ] **Unit R3: Flow B live rehearsal (fix → full restart loop)**

Same discipline as R2 for B1–B9 (including: backend fix → kill :8000 → fresh live uvicorn → restart from B1; fix-cycle cap of 3). Evidence under `.claude/demo_rehearsal/flowB/`.

- [ ] **Unit R4: Flow C live rehearsal (fix → full restart loop)**

Same discipline as R2 for C1–C10 (including backend-restart-before-flow-restart and the 3-cycle cap). Known-risk steps: C4/C5 (which-one + rail sync lag observed once live), C7 (generic-greeting quality miss observed once live — fix if it recurs: likely history/context handling in live path). Evidence under `.claude/demo_rehearsal/flowC/`.

- [ ] **Unit R5: Composability spot-check + final commit**

**Goal:** Prove improvisation safety (D2) and land the demo-ready state.

**Approach:** One REQUIRED mixed run (exact sequence, not a suggestion): B2 (14-day+return-by search) → select one exact tile → C3(b)-style second+third draft build (one more Alaska, one Mexico) → A5 pricing question → C4 "the Alaska one" which-one → tap candidate → B8 compare → C8 hover-delete Mexico → A8 checkout. This sequence deliberately crosses the hard composability edges (sectioned results → multi-draft → ambiguous ref → compare → delete → checkout). Same fix→full-restart discipline as R2 (restart the whole mixed sequence; 3-cycle cap). Then final commit of remaining fixes + runbook.

**Verification:** Mixed run passes end-to-end; working tree committed; backend suite fully green with test count ≥ the pre-rehearsal baseline (242 at time of writing — new defect fixes should ADD tests).

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| Live Gemini non-determinism (wrong tool, prose answer) | Assert state/tool/components, not wording; forced-tool prompt rules already in place; if a routing miss reproduces twice, treat as defect (prompt-rule fix) not flake |
| Paid-turn volume (3 flows + restarts, all live) | User accepted. Fixes may be validated in stub as a free DEV step (never counts as a rehearsal pass); every counted rehearsal run is live end-to-end; 3-cycle cap bounds the loop |
| Rail highlight lag after conversational switch (observed once) | C5/B7 explicitly assert post-switch rail state; fix in refresh sequencing if it reproduces |
| Backend has no --reload | Every backend fix: kill :8000 → fresh uvicorn from `backend/` → then restart flow |
| Draft cap collisions during improvisation | Composability matrix notes cap=5 + hover-delete recovery |
| Stale Playwright HMR console noise mistaken for defects | Clear browser cache first; verify errors against source (documented learning) |
| Gemini API outage/quota/429s on demo day | Runbook documents the stub-mode emergency start (`LLM_MODE=stub`, identical UI, deterministic) + rehearsal screenshots as last resort |
| Model-compliance steps flake between runs (A7/B7/C4–C7) | Demo-ready bar requires those steps clean in TWO live observations, not one; reproduced-twice misses become prompt-rule fixes |
| Pricing quote variance at A5/B9 (paraphrase vs invention) | Distinguish explicitly: any numeric figure quoted must ∈ {draft-held totals, displayed catalog fares} (defect if not); omitting the number entirely while pointing to the rail is variance — acceptable but note it |

**Rehearsal watchlist (pre-observed or code-reviewed UI quirks to adjudicate during Flow A):**
- Skeleton card row shimmers during ALL streaming turns with no components — including pure-conversational replies (A7/C7/B9). Decide at rehearsal: acceptable polish or fix (suppress skeleton once first text delta arrives with no tool call in flight).
- Streaming cursor may render inside the USER bubble instead of the assistant bubble (`frontend/components/chat/MessageStream.tsx` ~74–80) — verify visually; fix if real.
- Rail refresh window: rail may show stale totals/highlight for the `refreshDrafts()` round-trip after an action. Localhost demo ⇒ expect <300ms; PASS criterion: rail settles correct within ~1s of stream end; anything longer or requiring interaction = defect.
- Disambiguation card tap has optimistic border but no spinner — brief rail lag after tap is the same ≤1s tolerance.

## Sources & References

- Origin: `docs/plans/2026-07-21-002-feat-pinned-ui-dates-draft-context-plan.md` (all 9 units shipped this session)
- Requirements: `docs/brainstorms/2026-07-21-pinned-ui-dates-draft-context-requirements.md`
- Learnings: `docs/solutions/integration-issues/gemini-function-calling-chat-ui-integration-2026-07-21.md`
- Key code: `backend/app/llm/gemini_client.py`, `backend/app/llm/system_prompt.py`, `backend/app/llm/stub_orchestrator.py`, `backend/app/tools/search.py`, `backend/app/tools/draft.py`, `backend/app/routes/action.py`, `frontend/app/page.tsx`, `frontend/components/drafts/DraftRail.tsx`, `frontend/components/drafts/DraftDisambiguation.tsx`, `frontend/components/cards/CardRow.tsx`
