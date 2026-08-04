# Platform Reference Docs (PRD / Architecture / Rules / Phases / Design / Memory)

**Date:** 2026-08-04
**Branch:** `kitev2-develop`
**Status:** Approved design → implementation

## Problem

Sterling has no single, durable, human-readable reference describing the
platform as a whole. What exists today is scattered:

- `CLAUDE.md` — AI-agent instructions (skill routing, tool priority) mixed
  with real invariants (§C), written for Claude Code specifically, not for a
  human onboarding to the project.
- `ARCHITECTURE.md` (repo root) — a general architecture doc, now stale in
  places relative to the v3/v4 engine work and Kite integration.
- `docs/` — ~30 point-in-time reports (backtests, migrations, audits) with no
  single narrative thread.
- An extensive AI-agent memory log (outside the repo, in the Claude Code
  memory system) capturing decisions, dead ends, and lessons — not visible to
  anyone reading the repo itself.

There is no single place answering "what is Sterling, why does it work this
way, what must never break, what happened and when, and why."

## Goal

Produce six durable reference documents describing **Sterling as it exists
today** (not a plan for new work): `prd.md`, `architecture.md`, `rules.md`,
`phases.md`, `design.md`, `memory.md`.

## Scope decisions (from brainstorming)

- **Coverage:** the whole Sterling platform, not a single feature.
- **Location:** `docs/ai/` (joins `CONTEXT.md`, `WORKFLOWS.md`), filenames
  lowercase as requested.
- **Root `ARCHITECTURE.md`:** retired. Still-accurate content folds into
  `docs/ai/architecture.md`; the root file is then deleted.
- **`CLAUDE.md`:** left untouched. It keeps its Claude-Code-specific skill
  routing tables; `rules.md` is the general, tool-agnostic version of its
  substantive content (invariants + conventions), not a replacement for it.
- **`rules.md`** covers both halves: trading/risk invariants (circuit breaker
  ordering, correlation tracker updates, calibration recording, no-lookahead,
  the singleton list) and engineering conventions (graph-first tool priority,
  skill routing, CLI/style prefs).
- **`design.md`** covers both halves: technical design rationale (why
  walk-forward validation, why singleton services, why the strangler-fig
  modular architecture, why Kelly sizing) and UI/UX design (frontend design
  language, Kite tab/terminal/chart conventions, the Mac motion layer).
- **`phases.md` vs `memory.md` split:** `phases.md` is the structured,
  factual timeline (what shipped, when) with no rationale. `memory.md` is the
  narrative counterpart — why decisions were made, dead ends and rejected
  approaches, lessons learned — plus how the app's own runtime state/memory
  mechanisms work (CalibrationService, chart-state KV blobs, session caches,
  paper-trade tracking). Decision was delegated to the assistant; this split
  was chosen over "phases.md = future only" because a phases doc that omits
  the past would be an incomplete reference for "Sterling as it exists."

## Content plan per file

### 1. `prd.md`
What Sterling is and for whom: a solo-operator algorithmic trading platform
(paper + live) spanning crypto derivatives (Delta) and Indian equity/
derivatives (Kite/Zerodha). Core value proposition, current feature set
(engines, brokers, dashboards), explicit non-goals, success criteria.

### 2. `architecture.md`
System architecture: backend engine layers (v3 analytics/risk engines,
calibration/circuit-breaker/correlation singletons), broker adapters
(Kite/Delta/Zerodha), frontend structure, data flow between them, tech stack.
Absorbs and supersedes the current root `ARCHITECTURE.md`.

### 3. `rules.md`
Trading/risk invariants (from `CLAUDE.md` §C) and engineering conventions
(from `CLAUDE.md` §A/B/D), rewritten as a standalone platform reference.

### 4. `phases.md`
Chronological, factual timeline: major shipped phases (early strategy
iterations → v2 → v3 → v4, Kite integration, regime-book rework, derivatives
selector, etc.) with what shipped and when. A closing "known open items"
section lists only pending work already recorded elsewhere (e.g. "Phase 5
SQLAlchemy — PENDING" from the modular-architecture-hardening history) — it
must not invent a speculative future roadmap. No rationale — that lives in
`memory.md`.

### 5. `design.md`
Two sections: technical design rationale (why walk-forward validation, why
singleton services, why the strangler-fig modular architecture, why Kelly
sizing) and UI/UX design (frontend design language, Kite tab/terminal/chart
conventions, the Mac motion layer).

### 6. `memory.md`
Narrative decision log: why decisions were made, dead ends and rejected
approaches (funding-sleeve cut, momentum-overfit lesson, breadth
tested-negative, etc.), lessons learned — distilled from the existing
AI-agent project memory — plus how the app's own runtime state/memory works
(CalibrationService, chart-state KV blobs, session caches, paper-trade
tracking).

## Sourcing approach

Synthesize from what already exists rather than re-deriving from scratch:

- `CLAUDE.md`, root `ARCHITECTURE.md`, `README.md`, `STRATEGIES.md`,
  `RISK_MANAGEMENT.md`, `BROKERS.md`, `MARKETS.md` for current-state facts.
- The assistant's existing project memory log (dozens of dated entries
  already covering Kite, regime-book, v2/v3/v4, derivatives selector, scalping
  fixes, etc.) as the primary source for `memory.md` and `phases.md`.
- `docs/` reports for detail/verification where a memory entry references one.
- Code-review-graph / graphify for anything that needs verifying against
  current code (e.g. confirming a singleton or service still exists as
  described) rather than a fresh full-codebase read.

## Deliverables

1. `docs/ai/prd.md`
2. `docs/ai/architecture.md` (root `ARCHITECTURE.md` deleted after folding in)
3. `docs/ai/rules.md`
4. `docs/ai/phases.md`
5. `docs/ai/design.md`
6. `docs/ai/memory.md`

## Out of scope (YAGNI)

- No changes to `CLAUDE.md` itself.
- No new code, no new engines, no new UI — documentation only.
- No per-feature spec docs (those continue to live in
  `docs/superpowers/specs/` as before) — these six files are the
  project-level layer above them, not a replacement.
