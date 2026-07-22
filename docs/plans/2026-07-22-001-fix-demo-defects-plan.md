---
date: 2026-07-22
topic: Fix five Compass demo defects (tile layout, dining time, multi-night reserve, checkout resume, real images)
status: active
---

# Fix Demo Defects — Phased Plan

## Problem Frame

Five verified UI/flow defects block a clean demo: (1) cruise result cards stack vertically instead of in one horizontal row when the search returns sectioned results; (2) the "Set a preferred time" button on main-dining tiles is inert; (3) dining reservation is single-night-per-confirm and silently re-emits the identical panel, so multi-night booking and confirmation feedback are missing; (4) the checkout resume page only renders *completed* steps, so a guest cannot finish an unfinished booking; (5) every card/tile shows a striped placeholder instead of a real photo. Fixes bias toward the smallest diff that makes each flow work. Sequencing: U2 (bugs 2+3) and U4 (bug 5) both touch `DiningTiles.tsx` + `action.py`, so U4 runs **after** U2; U1, U2, U3 are mutually parallelizable.

Institutional learning #1: any new tool/component needs branches in **both** mappers — `gemini_client._map_tool_result_to_component` **and** `action._build_components` — or the UI silently gets nothing.

---

## Phase U1 — Single horizontal card row (Bug 1)

### Changes
- `frontend/components/cards/CardRow.tsx`: in the sections branch (`if (sections && sections.length > 0)`, ~L396-465), stop mapping one `SectionScroller` per section. Instead flatten: build one ordered card array = concat of all non-empty sections' cards, exact-match section first (section with `label === null` or the first section — treat `label == null` as exact). For each card originating from a **labelled** (non-exact) section, set a per-card badge carrying that section label **only if the card has no existing `badge`** (cards render `card.badge` at ~L125-143). Render the flattened array through the existing single horizontal scroller markup already used by the flat branch (`display:flex; overflowX:auto`, ~L499-516) — reuse `SectionScroller` for the whole flattened list, or inline the same flex container.
- Keep the empty-state guard (`totalCards === 0` → `EmptyState`) and the filters summary `<p>` unchanged.
- Remove/skip the per-section label kicker + hairline block (now redundant); section identity survives as the per-card badge.
- No backend change (sections descriptor shape from `_build_components`/`_map_tool_result_to_component` is unchanged).

### Test Set
1. **pytest** `backend/tests/test_action_search.py::test_search_sections_shape_unchanged` (or extend existing search test): assert a sectioned `search_cruises` result still yields a `card_row` descriptor whose `sections` is a list of `{label, cards}` (confirms we did not alter the contract U1 relies on).
2. **Playwright** (stub mode): search a query that returns an exact match + a near-miss section (e.g. an 11-night request with only 10/12-night alternatives). Expect: all result cards on **one horizontal line** (single scroll container, no stacked rows) — assert only one `div` with `overflow-x:auto` in the results region and its immediate card children count == total cards.
3. **Playwright**: assert the first card is the exact match and each non-exact card shows a badge with its section label text (e.g. "Options outside your 11-night request" collapsed to a badge) in the gold badge style.
4. **Playwright**: a search returning a single flat (non-sectioned) list still renders one horizontal row (flat branch regression).

### Files
- `frontend/components/cards/CardRow.tsx`
- `backend/tests/test_action_search.py` (assertion add only)

---

## Phase U2 — Dining preferred-time + multi-night reserve (Bugs 2 + 3)

*(Shares `DiningTiles.tsx` + `action.py` + `dining.py` — one implementer.)*

### Changes — Bug 2 (Set preferred time)
- `backend/app/tools/dining.py`: add `set_dining_time(session, args)` with args `{draft_id, venue_id, time}`. Find draft (reuse `_find_draft`); store on draft dining state a preference (simplest: `draft.dining_time = {venue_id: time}` — add attribute lazily via `getattr`/`setattr` if model lacks it, or store as a `"pref:<venue_id>:<time>"` marker; pick the attribute approach and state it). Return `{draft_id, venue_id, time, receipt: f"Preferred time set to {time}"}`. No capacity/step mutation.
- `backend/app/tools/__init__.py`: register `set_dining_time` in `TOOL_REGISTRY` with schema (required: `draft_id, venue_id, time`). **Decision: /action-only** — do NOT add to Gemini tool declarations config (`_make_config` tool list); the model never needs to set a time itself for MVP. State this in the plan comment.
- `backend/app/routes/action.py`: add a `set_dining_time` branch in `_build_components` returning `{"type":"dining_time_receipt","venue_id":..., "time":...}` (learning #1). Add an entry in `_make_event_text` ("user set preferred dining time ...").
- `backend/app/llm/gemini_client.py::_map_tool_result_to_component`: add matching `set_dining_time` branch returning the same `dining_time_receipt` descriptor (learning #1 — both mappers).
- `frontend/components/dining/DiningTiles.tsx` (~L216-231): give the "Set a preferred time" button an `onClick` toggling an inline picker (local state `openTimePicker: string|null`) with three options — Early 5:30 PM / Main 7:30 PM / Late 9:00 PM. Selecting one POSTs `/action/set_dining_time` `{session_id, args:{draft_id, venue_id, time}}` (mirror the existing `handleConfirm` fetch shape at ~L74-92). On success set local `preferredTime[venue_id]` and render "Preferred time: 7:30 PM" on the tile. Call `handlers?.onReserveDining?.(data)` to refresh the rail (reuses existing refresh path).

### Changes — Bug 3 (multi-night select + confirmation)
- `frontend/components/dining/DiningTiles.tsx`: change `selectedNight` state from `Record<string, number|null>` (L34) to `Record<string, number[]>`. `handleNightSelect` toggles a night in/out of the array (skip `sold_out`/`reserved`). Confirm button enabled when array non-empty. `handleConfirm` sends **one POST per selected night sequentially** to `/action/reserve_dining` (backend `reserve_dining` **unchanged — zero backend tool change**, smaller total diff than adding a list param + rewiring capacity/step logic). After all succeed, mark those nights reserved locally and disable them; close popover. On any per-night error, show that night's error and keep the rest.
- `backend/app/routes/action.py`: in `_build_components`, replace the `reserve_dining` branch's `_append_dining_tiles(...)` re-emit (~L267-270) with a compact `{"type":"dining_confirmation","venue_name":..., "nights":[...], "draft_id":...}` descriptor. Derive `venue_name` from catalog via `draft.cruise_id`; `nights` = the single reserved night from `result` (frontend accumulates across sequential calls, so per-call one night is fine — confirmation chip shows "Reserved Night N at <venue>"). Add the matching `reserve_dining` → `dining_confirmation` branch in `gemini_client._map_tool_result_to_component` too (learning #1).
- `frontend/lib/componentRegistry.tsx`: register `dining_confirmation` and `dining_time_receipt` renderers (small inline gold confirmation chips, mirroring the `ActiveDraftSet` chip pattern at ~L162-174). Add both keys to `REGISTRY` (~L289-302).

### Test Set
1. **pytest** `backend/tests/test_dining.py::test_set_dining_time_stores_preference` — call `set_dining_time` with a valid draft; assert return has `time`/`receipt` and the preference is readable on the draft; no `completed_steps` mutation.
2. **pytest** `backend/tests/test_dining.py::test_set_dining_time_bad_draft` — unknown `draft_id` → `{"error": ...}`.
3. **pytest** `backend/tests/test_action_dining.py::test_reserve_dining_emits_confirmation` — POST `/action/reserve_dining` and assert `components` contains a `dining_confirmation` (type present) and **no** `dining_tiles` re-emit.
4. **pytest** `backend/tests/test_tool_registry.py::test_set_dining_time_registered` — `"set_dining_time" in TOOL_REGISTRY` and its schema requires `draft_id, venue_id, time`.
5. **pytest** `backend/tests/test_mappers_parity.py::test_set_dining_time_both_mappers` — both `_build_components("set_dining_time",...)` and `_map_tool_result_to_component("set_dining_time",...)` yield a `dining_time_receipt` descriptor (guards learning #1).
6. **Playwright** (stub): on a main-dining tile click "Set a preferred time" → picker with 3 options appears → click "Main 7:30 PM" → tile shows "Preferred time: 7:30 PM".
7. **Playwright** (stub): on a specialty venue click "Reserve a night" → select Night 1 **and** Night 4 (both highlighted) → one "Confirm" → a `dining_confirmation` chip appears and Nights 1 & 4 are marked reserved/disabled; panel does not re-open identically.

### Files
- `backend/app/tools/dining.py`
- `backend/app/tools/__init__.py`
- `backend/app/routes/action.py`
- `backend/app/llm/gemini_client.py`
- `frontend/components/dining/DiningTiles.tsx`
- `frontend/lib/componentRegistry.tsx`
- `backend/tests/` (new/extended: test_dining, test_action_dining, test_tool_registry, test_mappers_parity)

---

## Phase U3 — Checkout resume: render & finish remaining steps (Bug 4)

### Changes
- `frontend/app/checkout/[draft_id]/page.tsx`: after the "Completed Steps" block (~L374), add a **"Remaining Steps"** section for every step in `[1..5]` **not** in `draft.completed_steps` (skip when `confirmed`). For steps 2/3/4 (in `EDITABLE_STEPS`) reuse `loadStepOptions` + `renderComponent(desc, key, editHandlers)` (identical machinery to the edit panels). For step 5 (Review) render a static review summary panel (label, fare, total, deposit/balance) — no fetch. Reuse `toggleEdit`/`editingStep` or add a parallel `openStep` state; keep it minimal by reusing `editingStep` + `editComponents` (a step is "open" whether completed-edit or remaining).
- CTA gating (replace ungated block ~L401-422): compute `nextIncomplete = checkoutEntry(draft.completed_steps)`. If `nextIncomplete <= 4`, render a **"Next: <STEP_LABELS[nextIncomplete]>"** button that opens/scrolls that step's form (calls `toggleEdit(nextIncomplete)` and scrolls to it). If steps `{1,2,3,4}` are all in `completed_steps` (treat as review-ready even though step 5 is never marked complete by the backend — `draft.py _ALL_STEPS={1..5}`), show the Review summary + the existing **"Reserve"** button (`onClick={() => setConfirmed(true)}`, mock is fine).
- `frontend/components/compare/ComparisonView.tsx` (~L77, `handleContinue`): change `window.location.href = url;` to `window.open(url, "_blank");` (keep it **after** the `await handlers?.onSetActiveDraft?.(...)`), so comparison "Continue with this" opens checkout in a new tab.

### Test Set
1. **pytest** `backend/tests/test_checkout_steps.py::test_step_options_for_incomplete` — `get_step_options`/`getStepOptions` backend path returns non-empty `components` for steps 2,3,4 of a partial draft (confirms the machinery U3 reuses returns data for *incomplete* steps, not just completed ones).
2. **Playwright** (stub): open `/checkout/<draft_id>` for a draft completed through step 3 only. Expect a "Remaining Steps" section listing Step 4 (Add-ons) and Step 5 (Review). Assert the CTA reads "Next: Add-ons" (not bare "Reserve").
3. **Playwright**: click "Next: Add-ons" → the step-4 form (dining/land builder) renders inline and is interactable; completing it makes the CTA advance toward Review.
4. **Playwright**: open a checkout for a draft with steps 1-4 complete → Review summary panel + "Reserve · <total>" button shown → click Reserve → confirmation panel ("Reserved, and gladly so." + booking ref) renders.
5. **Playwright**: in ComparisonView, click "Continue with this" → checkout opens in a **new tab** (assert a second tab/page opened) and the active draft was set first.

### Files
- `frontend/app/checkout/[draft_id]/page.tsx`
- `frontend/components/compare/ComparisonView.tsx`
- `backend/tests/test_checkout_steps.py` (assertion add)

---

## Phase U4 — Wire real images + asset manifest check (Bug 5)

*(Runs AFTER U2 — touches `DiningTiles.tsx`.)* Plain local `<img>` under `frontend/public/images/`; missing files must degrade to the **existing striped placeholder**, never a broken-image icon. Asset download is a separate parallel task; this phase covers wiring + fallback only.

### Changes
- `frontend/components/cards/CardRow.tsx`: the image `<img src={card.photo}>` (~L102-115) currently uses `/ports/*.svg`. Change to `src={`/images/cruises/${card.cruise_id}.jpg`}`; keep the existing `imgFailed` `onError` → striped-gradient fallback (already the container background). (This lands in the same file as U1 — sequence U4's CardRow edit after U1 or coordinate one implementer for CardRow.)
- `frontend/components/stateroom/StateroomPicker.tsx` (~L82-102): replace the striped placeholder `<div>` with an `<img>` keyed by `slug(cat.category)` → `/images/staterooms/{inside|ocean_view|verandah|suite}.jpg`, with an `onError` state that falls back to the current striped div. Add a tiny local `slug()` (lowercase, spaces→`_`).
- `frontend/components/dining/DiningTiles.tsx` (~L151-172): replace the striped photo `<div>` with `<img src={`/images/dining/${venue.venue_id}.jpg`}>` (ids: saffron, main_dining, lido) + `onError` fallback to the striped div.
- `frontend/components/land/LandTourBuilder.tsx` *(optional, include only if trivial)*: small `<img src={`/images/land/${opt.id}.jpg`}>` per option (ids: coastal_d1, domed_rail_d2, motorcoach_d2, denali_lodge_2n, fairbanks_tour_d4, skagway_summit_d3) with striped fallback.
- **Asset manifest check** (test-only, no runtime code): enumerate expected files under `frontend/public/images/` — cruises: 31 ids (24 known + `med_greek_isles, med_italy_france, med_western, med_adriatic, hawaii_nonstop, hawaii_neighbor_islands, hawaii_maui_big_island`); staterooms: 4; dining: 3; land: 6. Missing files are allowed at runtime (fallback), but the manifest check reports which are absent so the parallel asset task knows what's left.

### Test Set
1. **pytest** `backend/tests/test_image_manifest.py::test_cruise_ids_match_catalog` — the 31 cruise ids referenced for images equal the set of `cruise_id` in `cruises.json` (catches drift; does not require files to exist).
2. **pytest/script** `backend/tests/test_image_manifest.py::test_report_missing_images` — walk `frontend/public/images/` and **print/report** (do not hard-fail) any expected file absent, so the asset task has a checklist. Assert only that the directories exist.
3. **Playwright** (stub): on a search result, each cruise card shows a real `<img>` whose `src` matches `/images/cruises/<cruise_id>.jpg` (assert `src` attribute), and cards for ids with a present file render a loaded image (naturalWidth>0).
4. **Playwright**: force a missing image (a card whose id has no file) → the tile shows the striped gradient placeholder, **not** a broken-image icon (assert the `<img>` is hidden via `imgFailed`/`onError` and the striped background is visible).
5. **Playwright**: stateroom picker + dining tiles each render an `<img>` for known ids (inside/ocean_view/verandah/suite; saffron/main_dining/lido) and fall back to stripes for unknown.

### Files
- `frontend/components/cards/CardRow.tsx`
- `frontend/components/stateroom/StateroomPicker.tsx`
- `frontend/components/dining/DiningTiles.tsx`
- `frontend/components/land/LandTourBuilder.tsx` (optional)
- `backend/tests/test_image_manifest.py` (new)

---

## Verification & Commit Protocol

- **One verified phase = one commit.** Order: U1, U2, U3 may proceed in parallel; **U4 after U2** (shared `DiningTiles.tsx`), and U4's `CardRow.tsx` edit coordinated with U1.
- All Playwright browser checks run in **stub mode** to keep Gemini cost zero: set `LLM_MODE=stub` in the backend env before launching so no paid model turn is triggered by any tile-tap or search during verification.
- The independent Fable verifier spawns a Sonnet general-purpose worker to run pytest (`LLM_MODE=stub`) and drive Playwright; the verifier compares evidence (screenshots + pytest output) against each phase's Test Set and only signs off when every case passes. On sign-off, the orchestrator commits that phase (no Claude attribution per project policy).
- Learning-#1 guard: U2's `test_mappers_parity` must pass before U2 is committed — both mappers must carry the `set_dining_time`/`dining_confirmation` branches.
