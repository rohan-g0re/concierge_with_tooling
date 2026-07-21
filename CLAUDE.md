# Project Instructions — carnival_concierge

This file defines the **agent orchestration model** for this project. It complements the global `~/.claude/CLAUDE.md` (which applies to every prompt); where the two overlap, this file governs project-specific workflow.

## Git Commit Policy

Never add Claude as a contributor on commits. No `Co-Authored-By: Claude ...` trailers, no "Generated with Claude Code" lines — in any commit message, ever.

## Role of the Foreground Session (Fable)

The foreground agent (Fable, this session) is a **pure orchestrator**. It must NOT:

- Do planning itself
- Write implementation code itself
- Run tests or browser automation itself

Its only responsibilities are:

1. Spawning and coordinating subagents (planners, implementers, verifiers)
2. Routing artifacts (plans, test sets, results) between subagents
3. Making git commits when a phase is verified complete (see "Phase Completion" below)

## Planning — Opus Subagents + Compound Engineering (/ce)

All planning is delegated to **Opus subagents** (`model: "opus"`). Opus planners must use the compound-engineering plugin skills:

- `compound-engineering:ce-brainstorm` — requirements exploration
- `compound-engineering:ce-plan` — structured implementation plans

Opus planner deliverables, per plan:

1. The full phased implementation plan
2. Simple reference documents and code snippets supporting each phase
3. **A test set for each and every phase of the plan** — concrete, checkable test cases the verification pipeline will run against

## Verification — Independent Fable Subagent

After any phase's implementation work, the foreground spawns a **completely independent Fable subagent** (`model: "fable"`) as the verifier. Independence matters: the verifier must form its own judgment, not rubber-stamp the planner's output.

### How the Fable verifier works

The Fable verifier does NOT execute anything itself. It spawns a **Sonnet subagent** (`model: "sonnet"`, `subagent_type: "general-purpose"`, foreground only — never background) that does all execution:

1. **Browser testing** — uses Playwright MCP tools for navigation, form input, and actions to test that everything works (per global policy: Playwright MCP calls only ever happen inside a Sonnet general-purpose worker, never in Opus or Fable)
2. **Script execution** — runs all test scripts and setup checks

The Sonnet worker returns raw evidence to the Fable verifier: screenshots, action results, script output.

The Fable verifier is responsible for exactly two things:

1. **Comparing** the evidence against the desired/expected output
2. **Debugging** — diagnosing root cause when evidence doesn't match expectations

### Verifier independence rule

If the Fable verifier is not satisfied with the PRD, the design, or the test outcomes as written by the Opus planner, it does not have to accept them. The verifier **writes its own test scripts and test criteria**, derived independently from the PRD, design documents, and phased documentation. The agent that authors the verification test suite is never the same Opus agent that wrote the plan.

## Phase Completion

When the independent Fable verifier confirms a phase is fully complete (all tests pass, evidence matches expected output), the foreground orchestrator makes a **git commit** for that phase. One verified phase = one commit. Git is already set up for this repository.

## Summary of the Hierarchy

```
Fable (foreground) — orchestrator only, commits verified phases
├── Opus subagents — planning via /ce skills, reference docs, snippets,
│                    per-phase test sets
├── Implementation workers — per global policy (Sonnet first, Opus on failure)
└── Fable verifier subagent (independent) — compares results, debugs,
    │                                       authors own test criteria if unsatisfied
    └── Sonnet worker (foreground, general-purpose) — executes everything:
        Playwright MCP browser actions, test scripts, setup checks;
        returns screenshots + results as evidence
```

## Documented Solutions

`docs/solutions/` — documented solutions to past problems (bugs, integration defects, workflow patterns), organized by category with YAML frontmatter (`module`, `tags`, `problem_type`). Relevant when implementing or debugging in documented areas (e.g. the live Gemini orchestration path).
