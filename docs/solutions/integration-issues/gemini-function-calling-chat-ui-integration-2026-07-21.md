---
title: Live Gemini function-calling integration — five defect classes when leaving stub mode
date: 2026-07-21
last_updated: 2026-07-22
category: integration-issues
module: llm-orchestrator
problem_type: integration_issue
component: assistant
symptoms:
  - "404 ClientError: models/gemini-2.0-flash is no longer available (model id retired by Google)"
  - "Tool executed successfully but SSE components event carried empty payloads (card_row cards: [], comparison never rendered)"
  - "Literal CHIPS: [\"...\"] control marker visible in streamed chat text"
  - "draft_not_found x4 / no_drafts errors from compare_drafts called with hallucinated draft ids"
  - "Comparison request answered in prose with components: [] instead of a rendered component"
  - "Dining reservation Confirm re-displayed the identical full dining panel with no receipt — mutation appeared to silently fail (third mapper-gap recurrence, 2026-07-22)"
root_cause: wrong_api
resolution_type: code_fix
severity: high
tags: [gemini, function-calling, sse-streaming, tool-mapping, model-retirement, snapshot-injection, stub-live-parity, chips-protocol, mapper-parity, mutation-receipt]
---

# Live Gemini function-calling integration — five defect classes when leaving stub mode

## Problem

Switching Compass from the stub LLM orchestrator to live Gemini function-calling exposed five distinct defect classes that were invisible during development, because the stub path never exercised the live SDK code branches. All five existed in production code before a single live API call was made.

## Symptoms

- `google.genai.errors.ClientError: 404 NOT_FOUND ... This model models/gemini-2.0-flash is no longer available` on the first live turn.
- `search_cruises` ran and returned 8 results, but the terminal SSE `components` event showed `"cards": []`. Same class: `compare_drafts` returned full rows/headers but the UI got `components: []`.
- Guests saw raw `CHIPS: ["View Denali Explorer", ...]` appended to streamed chat bubbles.
- "Compare my drafts" produced `draft_not_found` ×4 then `no_drafts` — the model invented draft ids — plus a spurious `create_draft` call.
- After the session snapshot was added, the model answered comparisons in accurate prose with no tool call and no component.

## What Didn't Work

- **Relying on stub-mode green tests.** The suite was 100% green before live integration, but stub tests bypassed `_map_tool_result_to_component` entirely — the live mapping layer was untested code that silently returned nothing for unmapped tools.
- **Assuming the model would call tools once the session snapshot gave it real state.** The opposite happened: the snapshot gave it enough data to freeload into prose and skip the `compare_drafts` call the UI needs.

## Solution

Fixes, all in `backend/app/llm/gemini_client.py` unless noted:

**1. Alias model id (retirement-proof):**

```python
# Before
model_name = "gemini-2.0-flash"      # retired by Google -> 404
# After
model_name = "gemini-flash-latest"   # alias tracks current stable Flash
```

**2. Tool-result key + missing component mappings** in `_map_tool_result_to_component`:

```python
# Before: result.get("cruises", [])  — key never exists; search returns "results"
cruises = result.get("results", [])

# compare_drafts and set_active_draft had NO branches -> tool ran, UI got nothing
if tool_name == "compare_drafts":
    return {"type": "comparison", "rows": result.get("rows", []),
            "headers": result.get("headers", []),
            "checkout_urls": result.get("checkout_urls", []), ...}
if tool_name == "set_active_draft":
    return {"type": "active_draft_set",
            # two-key fallback: tool may return either key name
            "draft_id": result.get("active_draft_id") or result.get("draft_id"),
            "label": result.get("label")}
```

**3. CHIPS tail-buffer** — withhold the last 200 characters (code points, not bytes — CHIPS markers are ASCII so the distinction is currently harmless) during streaming so the trailing `CHIPS: [...]` marker is parsed and stripped before it can be emitted; flush the remaining clean tail after `_parse_chips` runs.

**4. Per-turn session snapshot** — `_build_session_snapshot(session)` emits a compact bracketed user-role note prefixed `[session state — use these exact draft ids when calling tools; never invent ids: ...]` (party, active_draft_id, one line per draft: id, label, cruise, fare, stateroom, completed_steps) injected immediately before the user message. Cures hallucinated draft ids. (Distinct from the `[system note: ...]` prefix used for `system_event` history entries.)

**5. Forced tool call for UI-rendering intents** — `system_prompt.py` COMPARE DRAFTS RULE: comparison requests MUST call `compare_drafts`; prose-only comparisons forbidden; snapshot is for id reference, not a substitute.

**6. Defense in depth in the tool** — `backend/app/tools/compare.py` filters model-supplied ids to known session drafts; if fewer than 2 valid remain, falls back to all session drafts; polite `no_drafts` error otherwise.

**7a. (2026-07-22) Both-mappers rule formalized after third recurrence.** There are TWO parallel mapper sites, not one: `gemini_client._map_tool_result_to_component` (LLM function-calling path) **and** `backend/app/routes/action.py:_build_components` (UI-action bridge path). A tool or component added to one without the other silently produces nothing on the untested path. Recurrences: (1) `search_cruises` results-key mismatch in action.py, (2) `handoff_checkout` unmapped in gemini_client, (3) `reserve_dining`/`set_dining_time` receipts (commit 8425a28). Companion rule discovered in recurrence 3 — **mutation receipts, not panel re-emits**: the reserve_dining branch originally re-emitted the full `dining_tiles` panel "to refresh statuses"; visually identical to the pre-action state, it read as a silent failure. Every mutation tool response must emit a compact receipt component scoped to the delta (`dining_confirmation` {venue, night}, `dining_time_receipt` {time_label}), never re-emit the panel it was called from. Checklist for every new component type: branch in `_build_components`; matching branch in `_map_tool_result_to_component` (identical field shape); `/action`-only tools added to `_ACTION_ONLY_TOOLS` in gemini_client.py; renderer registered in `frontend/lib/componentRegistry.tsx`; mapper-parity pytest asserting both mappers emit same type + key fields; no-re-emit guard pytest asserting the source panel type is absent from `_build_components` output (reference implementation: `backend/tests/test_u2_dining.py`).

**7. Zero-cost live-path tests** — two independent mechanisms, both required: `set_client(FakeClient(...))` injects the fake API client (so `get_client()` never constructs a real one), and a `patch_genai_types` fixture patches the SDK types module. Harness gotcha for the latter: production code does `from google.genai import types`, which resolves `types` as an **attribute of the `google.genai` module object** — the fake must set `fake_genai.types = FakeTypes`. Setting `sys.modules["google.genai.types"]` too is good defensive practice (covers any future `import google.genai.types` form), but the attribute assignment is what the current import form actually exercises.

## Why This Works

- **Dual orchestrator paths drift silently.** Stub and live share `run_turn()` semantics but diverge at tool-result handling; without tests pushing real tool dicts through the live mapping, that layer is dead code until production.
- **Streaming emit-before-parse ordering.** The control marker always arrives at the tail; a tail holdback guarantees the parser consumes it before the client can see it.
- **LLMs skip tools when context makes prose possible.** Authoritative state injection must be paired with explicit "this intent requires a tool call" rules for anything the UI renders structurally.
- **Pinned model ids rot.** Vendors retire specific versions on their own schedule; `-latest` aliases survive rotations.
- **LLM tool args are untrusted input.** Validate, filter to known ids, fall back gracefully — same discipline as user input.

## Prevention

- Stub/live parity tests: one shared tool-result factory per tool, asserted through `_map_tool_result_to_component` — a mapping regression fails both suites.
- Always use alias model ids; optionally smoke-test `client.models.get(model_name)` at startup to fail fast.
- Tail-buffer any streamed control-marker protocol by at least the marker's max length.
- Every tool the model can call must appear in **both** tool→component mappers (`gemini_client._map_tool_result_to_component` AND `action.py:_build_components`), or explicitly be a no-component tool — treat an unmapped tool as a test failure. Enforce with mapper-parity + no-re-emit pytests (pattern: `backend/tests/test_u2_dining.py::test_mappers_parity_reserve_dining`).
- Mutation tool responses emit compact receipt components (the delta), never a re-emit of the panel that triggered them — identical-panel re-emits read as silent failure.
- Cost discipline while debugging: run backend with `LLM_MODE=stub` for free deterministic turns; reserve live turns for final verification (capped per run).

## Related Issues

- Governing plan: `docs/plans/2026-07-21-001-feat-compass-concierge-plan.md` (P5 Gemini loop, P12 comparison — this doc records the live-integration defects those phases surfaced).
- Auto memory (claude): project memory note `compass-live-gemini-setup` records the model alias, LLM_MODE stub trick, and backend `.env` cwd requirement.
- Third recurrence fix: commit 8425a28 (plan `docs/plans/2026-07-22-001-fix-demo-defects-plan.md` U2); parity + no-re-emit test suite `backend/tests/test_u2_dining.py`.
