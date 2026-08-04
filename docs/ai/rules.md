# Sterling Project Rules

This document is the standalone reference for Sterling's non-negotiable rules. It is
tool-agnostic: it should be legible to a human contributor, a reviewer, or any AI
coding tool working in this repository, without assuming any particular agent,
IDE, or CLI. It covers two distinct kinds of rules:

- **Part 1 — Trading & risk invariants**: behaviors the system must never violate,
  because violating them risks real money, corrupted risk state, or a backtest
  that lies about its own edge.
- **Part 2 — Engineering conventions**: how work gets done in this repo day to
  day — exploration strategy, tooling, style, and context discipline.

Invariants in Part 1 are backstopped by tests and code review; treat any change
that touches them as high-risk regardless of how small the diff looks.

---

## Part 1 — Trading & Risk Invariants

These rules exist because Sterling moves real risk state on every evaluation
cycle. A missed update, wrong ordering, or skipped record isn't a cosmetic bug —
it silently desynchronizes the system's model of its own risk from reality.

### 1.1 Evaluation ordering is load-bearing

`evaluate()` (and the broader order-execution pipeline it feeds) is not a bag of
independent checks — it is an ordered sequence where **each step is fail-closed**:
any step that errors rejects the action rather than letting it through.

Required order, front to back:

1. **`DrawdownCircuitBreaker.update()` runs FIRST**, before anything else in
   `evaluate()`. This is the portfolio-level drawdown gate
   (`app/engines/risk/circuit_breaker.py::DrawdownCircuitBreaker`, singleton
   `app.state.dd_circuit_breaker`). It tracks peak value, current drawdown, and
   emits a size multiplier / halt state — nothing downstream should be allowed
   to run against a portfolio that has already breached its drawdown limit.
2. **`CorrelationTracker.update()` runs on EVERY `evaluate()`** with 1H closes —
   not just when a trade is being considered, not just for the symbol in
   question. This is the sole mechanism that keeps the tracker's EWM return/
   correlation state current; skip it once and every downstream correlation
   penalty calculation is computed against stale data.
   (`app/engines/analytics/correlation.py::CorrelationTracker`, singleton
   `app.state.correlation_tracker`.)
3. Downstream of these two updates, the live order pipeline applies its own
   ordered, fail-closed guard chain (kill switch → daily-loss halt →
   idempotency → cooldown → portfolio bucket caps → microstructure veto →
   correlation penalty as a **size multiplier, not a hard veto** → Greeks
   budget, LIVE-mode only).

**Do not reorder these checks** to "simplify" a code path, and do not add a new
check by inserting it ahead of the drawdown breaker. If a change touches
`evaluate()`, re-verify the ordering explicitly as part of review — this is not
implied by tests passing, since a reordering can still pass unit tests that
mock individual steps.

> **Naming trap**: `DrawdownCircuitBreaker` (`dd_circuit_breaker`) and
> `CircuitBreaker` (`circuit_breaker`) are two **separate, non-aliased classes**
> — one is the portfolio drawdown gate, the other is a distinct execution-level
> circuit breaker. Conversation shorthand sometimes calls the drawdown breaker
> "the circuit breaker," but they are different singletons with different
> state. Do not merge, rename, or treat them as interchangeable.

### 1.2 Every position close must record a calibration sample

**`CalibrationService.record_trade()` must be called on every `paper_store`
position close, with no exceptions.** This is what feeds the system's adaptive
win-rate and IVR-band estimates
(`app/services/calibration.py::CalibrationService`, singleton
`app.state.calibration_service`). A position-close code path that returns,
raises, or short-circuits before calling `record_trade()` silently starves
calibration of data — the failure mode is invisible (no error, just quietly
wrong statistics) until win-rate figures no longer match reality.

Any new position-close path (a new exit mode, a new monitor loop, a new backtest
replay branch) must call `record_trade()` on the same terms as the existing
ones. When adding or reviewing such a path, confirm the call is reachable on
every exit branch — not just the "happy path" — including stop-outs, forced
exits, and reconciliation-driven closes.

Access `CalibrationService` through the app's standard dependency-injection
seam rather than importing or instantiating it directly in a new call site.
Constructing a second instance (even with the same `db_path`) risks two
in-memory views of calibration state drifting apart. If you find a call site
reading the service directly off shared application state instead of going
through the documented injection seam, treat that as a drift to flag and
reconcile — not a green light to add a third pattern.

### 1.3 Walk-forward optimization must never look ahead

When selecting thresholds or parameters via walk-forward optimization, **the
test window must never be used for threshold/parameter selection.** Selection
happens only on the training window; the test window exists purely to score a
choice already made.

This generalizes to a family of related "don't cheat with information the
system wouldn't have had live" rules that have already caused real bugs when
violated:

- No cross-timeframe intrabar lookahead (a higher timeframe's bar must be
  treated as unclosed until it actually closes).
- Fills must be modeled realistically (next-bar-open, with gap-throughs
  skipped) — not assumed to fill at a theoretical ideal price.
- Live/replay code must not evaluate against a still-forming ("live") bar as if
  it were closed.

Any new backtest, optimizer, or live-replay code should be checked against this
family before being trusted. A backtest or walk-forward result that violates
any of these is not just optimistic — it can invert the sign of the reported
edge.

### 1.4 Sensitivity sweep cadence

The sensitivity sweep runs **at startup and weekly thereafter**, with results
**cached for 7 days**. Do not add a code path that recomputes it more
frequently without a specific reason (it exists to be cheap to consult, not to
be recomputed per-request), and do not let a refactor silently drop the startup
run or the weekly re-run.

### 1.5 Protected singletons

These four singletons hold the risk/analytics state described above and must
never be duplicated, shadowed, or re-instantiated ad hoc:

| Singleton | Class | File | Role |
|---|---|---|---|
| `dd_circuit_breaker` | `DrawdownCircuitBreaker` | `app/engines/risk/circuit_breaker.py` | Portfolio drawdown gate; must update first in `evaluate()` |
| `circuit_breaker` | `CircuitBreaker` | (execution layer) | Distinct execution-level breaker — not an alias of the above |
| `correlation_tracker` | `CorrelationTracker` | `app/engines/analytics/correlation.py` | EWM correlation state; must update every `evaluate()` |
| `calibration_service` | `CalibrationService` | `app/services/calibration.py` | Adaptive win-rate/IVR calibration; must record every position close |

All four are constructed once at process startup and attached to shared
application state, not created per-request or per-module-import. If a change
introduces a second construction path for any of these, that is very likely a
bug, not a feature — confirm before assuming otherwise.

### 1.6 Two risk layers exist on purpose — know which one is authoritative

Sterling deliberately runs **two separate risk layers**, and this separation is
intentional, not duplication to be "cleaned up":

- **The live safety pipeline** (embedded in the order router plus a dedicated
  live-safety service) is authoritative today. It is the ordered, fail-closed
  guard chain described in §1.1 — kill switch, daily-loss halt, idempotency,
  cooldown, portfolio bucket caps, microstructure veto, correlation-penalty
  sizing, and (LIVE-only) the Greeks budget hard gate.
- **A registry-driven rule engine** is a standalone, explicitly **not yet
  authoritative** evaluator. It runs in shadow mode alongside the live
  pipeline, comparing its decisions against the authoritative outcome without
  being able to block or allow an order itself. Only after a rule engine
  demonstrates sustained agreement with the live pipeline in shadow mode should
  it ever be promoted to authoritative — and that promotion is an explicit,
  deliberate step, never an incidental side effect of an unrelated change.

Do not repoint the order router at the rule engine, and do not treat the rule
engine's decisions as authoritative in any user-facing surface, until that
promotion has actually happened.

### 1.7 Compliance and fail-safety baseline

- Every execution decision must be recorded in the audit trail.
- Every order rejection must carry a machine-readable reason code, not just a
  human-readable message — downstream alerting depends on the code, not on
  parsing prose.
- Order placement must be idempotent (time-bucketed, plus an optional
  client-supplied order id) so that a retry or accidental double-submit can
  never place a duplicate live order.
- New regulatory or position-limit rules belong in the rule engine described in
  §1.6 as named, independently testable rules — not as ad hoc inline checks
  scattered through request handlers.
- Going live requires: an explicit mode change to live trading, passing the
  full safety pipeline, and passing the Greeks-budget gate. Paper trading is
  the default; nothing should make live trading the default of a fresh
  environment.

### 1.8 Zero-regression discipline for anything touching these invariants

Because these invariants underpin real risk, any change that touches
`evaluate()`, the risk engines, calibration, or paper-store position-close
paths must be validated with the project's zero-regression workflow:

1. Capture the baseline failing-test set before changing anything.
2. Make additive changes where possible — new capability as new modules;
   avoid rewriting a file that already has proven, tested behavior unless the
   new behavior has test-proven parity with the old.
3. Re-run the full suite and diff the failure set against the baseline. Only a
   *new* failure (passing at baseline, failing now) counts as a regression —
   fix or revert it. A different total failure count, on its own, is not the
   signal to act on (see §2.6 on the test suite's known order-dependent
   flakiness).
4. Confirm the application still imports/starts cleanly and any golden smoke
   test still passes.

Shadow-before-authoritative (§1.6) and additive-first are the same underlying
principle applied to architecture: prove new behavior in parallel before it
gets to make real decisions.

---

## Part 2 — Engineering Conventions

These are the working conventions for changing Sterling's code — how to
explore it, what tools to reach for, and how to keep sessions and diffs small
enough to reason about.

### 2.1 Explore the graph before you grep the files

Sterling maintains a structural knowledge graph of its own codebase. Treat it
as the first tool for any question about *what the code does* or *what a
change would affect* — not a raw text search.

- **Exploring unfamiliar code** → semantic/structural search over the graph,
  not a keyword grep.
- **Understanding blast radius** → an impact-radius / affected-flows query
  over the graph, not manually chasing imports by hand.
- **Reviewing a change** → a graph-driven risk-scored diff view plus
  token-efficient source snippets, not reading whole files end to end.
- **Tracing relationships** (who calls this, who imports this, what tests
  cover this) → a graph relationship query, not scanning directories.
- **Architecture-level questions** → a graph architecture overview /
  community-structure view, not skimming folder names.

Fall back to plain text search (`rg`, `fd`, `ast-grep`) only when the graph
genuinely can't answer the question — for example, a literal string that isn't
a structural symbol, or a one-off file that isn't part of the graph's model
yet.

Two specific modules are worth calling out: **do not grep the analytics/risk
engine internals or the calibration service source directly** — these are
exactly the modules described in Part 1, and understanding them via the graph
(which shows callers, call sites, and test coverage) is both cheaper and less
error-prone than reading the raw file and guessing at who depends on it.

### 2.2 Separate concerns: code impact vs. architecture health vs. broader knowledge

Sterling distinguishes between three related-but-distinct kinds of "look at the
codebase" tooling. Pick the one that matches the question — don't run more than
one for the same question:

| Question | Tool |
|---|---|
| "What calls this, what would break, is this PR risky?" | Code-impact graph (daily coding) |
| "Are there cycles, layer violations, god modules, dead code, architecture drift?" | Architecture-health analyzer |
| "What does the code + docs together say about this concept, broadly?" | Knowledge graph over code and docs |

The architecture-health analyzer is specifically for structural quality
questions (circular dependencies, layering violations, overly-central "god"
modules, dead modules, cross-service coupling, spec/intent drift) — it is not
a substitute for the code-impact graph's callers/impact/test-coverage queries,
and vice versa.

### 2.3 Preferred CLI tools

Prefer the modern equivalent over the legacy tool when both are available:

- `rg` over `grep`
- `fd` over `find`
- `ast-grep` (structural code search) over ad hoc regex-based code search
- `jq` / `yq` for structured JSON/YAML inspection instead of eyeballing raw
  output
- `gh` for anything GitHub-shaped (PRs, issues, checks) instead of
  hand-crafted API calls
- A type-checker in `--noEmit`/check-only mode for a fast typecheck without a
  full build

None of this is about tool snobbery — it's that the modern tools are faster,
respect `.gitignore`, and produce output that's easier to pipe into further
filtering.

### 2.4 Code style: YAGNI, no premature abstraction

- Build the capability that's needed now, in the shape the current requirement
  actually has. Don't add configuration knobs, plugin points, or abstraction
  layers for a hypothetical future requirement that hasn't shown up yet.
- Prefer additive changes (new module, new function, new endpoint) over
  rewriting working, tested code in place — especially for anything touching
  the Part 1 invariants, where "just refactor it" carries real regression risk
  for no visible benefit.
- When a component's behavior is genuinely changing (not just being
  reorganized), prefer shadow-mode / parallel-run validation before flipping
  the switch, mirroring the rule engine's shadow-before-authoritative pattern
  in §1.6. This applies well beyond risk code — any behavior-changing rewrite
  benefits from the same discipline.
- A rule, check, or gate belongs in one clearly-named, independently testable
  place — not duplicated inline in multiple call sites "just this once."
- If a change can't be described as a small, reviewable diff, that's a signal
  to split it, not a signal to write a longer PR description.

### 2.5 Skill/process discipline

Treat structured process aids (debugging playbooks, planning templates,
review checklists, and similar) the same way you'd treat any other tool
selection:

- Pick the one or two that match the *type* of task at hand — a bug
  investigation calls for a different playbook than a new feature, which
  calls for a different one than an architecture pass. Don't stack many of
  them onto one task.
- For anything non-trivial, write the plan down and get it reviewed/approved
  before writing implementation code. Prefer starting large implementation
  work in a fresh session once a plan is approved, rather than continuing to
  grow an already-long exploratory session.
- Domain-specific playbooks (frontend-specific, infra-specific, publishing/
  content-specific, etc.) are opt-in for the domain they cover — don't reach
  for a content-publishing playbook on a backend risk-engine task, or vice
  versa.
- After using a process aid to plan or investigate, return to the graph-based
  exploration tools (§2.1) for the actual code exploration — the two are
  complementary, not substitutes for each other.

### 2.6 Testing and zero-regression baseline

- Run the backend test suite with warnings suppressed; without that, a run
  that should take well under a minute can balloon to many minutes because of
  third-party deprecation-warning volume.
- The suite has known order-dependent tests that pass in isolation but can
  fail in a full run due to shared module-level state that isn't fully reset
  between tests. **The meaningful signal is the diff of the failing-test set
  against a baseline (e.g., the main branch), never the raw failure count.**
  A changed failure count with no new failures in the diff is not a
  regression.
- At least one test in the suite is known to hang on a real socket and must be
  explicitly deselected for any unattended/CI run.
- The authoritative regression gate diffs the failing-test set of the change
  under review against the failing-test set of its merge base, and fails only
  on a genuinely new failure. It should hard-fail (not silently pass) if the
  test run didn't actually execute — a silent no-op must never look like
  success.
- Full verification (equivalent to "run everything that must be green before
  calling a change done") means both the backend test suite and a frontend
  type-check with no emitted output — a change isn't verified if only one of
  the two ran.
- A live-exchange integration's golden smoke test exists specifically so that
  a real integration's live behavior can never silently change; treat it as
  non-negotiable if it's part of the verification path for what you touched.

### 2.7 Security baseline (applies to any change touching secrets, input, or headers)

- Exchange/API credentials must never be returned in full in an API response —
  only a redacted hint (masked, with a short suffix) may be surfaced.
- Local secret files are git-ignored; only an example/template file is
  committed. Secrets must never be written to logs, including inside
  structured log fields.
- Every HTTP response should carry standard hardening headers (frame-options,
  content-type-options, referrer-policy, a locked-down content-security-policy
  appropriate for an API-only surface), and CORS should be an explicit
  allow-list, never a wildcard.
- All external API input should be validated through a schema/model layer —
  never accepted as a raw, unvalidated dict.

### 2.8 Configuration precedence

When more than one source could plausibly set a given value, precedence goes,
highest to lowest:

1. Environment variables / local env file → the process-wide settings
   singleton (unknown env keys should be ignored, not fatal).
2. A checked-in registry/metadata file (broker and market metadata) → loaded
   and cached by a dedicated service, not re-parsed ad hoc.
3. Stored, per-account configuration records (live credentials, which exchange
   is currently active) → managed exclusively through the accounts
   API/store, never hard-coded.

Paper trading and real public market data should both default on; going live
and using synthetic data are both things a deployment must opt into
explicitly, never the silent default of a fresh environment.

### 2.9 Observability conventions

- Structured (JSON) logging, correlation IDs, and in-process metrics are all
  additive and opt-in — none of them should change default runtime behavior,
  and the plain-text logging fallback should keep working even when they're
  enabled.
- Every inbound HTTP request should carry (or be assigned) a correlation ID
  that's echoed back in the response and threaded through that request's log
  lines; a non-HTTP background loop should wrap itself in an equivalent
  correlation scope so its logs can be tied together the same way.
- In-process metrics should be collected through one small, thread-safe
  registry rather than ad hoc counters scattered across modules, so that a
  future metrics-scraping endpoint has one place to read from.

### 2.10 Context and token discipline

- Reach for the right graph/tool for the question (§2.1–§2.2) instead of
  reading broadly "just to be safe."
- For non-trivial work: write a short plan, get it approved, and prefer a
  fresh session for the large implementation that follows, rather than
  letting one session grow indefinitely.
- Keep changes in small, focused branches/PRs. If a working session drifts
  away from its original topic, or context starts feeling overloaded, that's
  a signal to start a new session rather than push through.
- Never paste an entire repository tree or an entire large file into a
  conversation as context — use targeted graph queries and minimal, specific
  file reads instead.
- Prefer a small number of well-chosen process aids per task over stacking
  many at once (§2.5).
- Keep the number of always-on external tool integrations small; each one
  enabled has an ongoing cost, so disable what a given task doesn't need.
- Match effort to task: lightweight work (docs, summaries, research) doesn't
  need the same firepower as hard architecture or risk-invariant work — spend
  the expensive option deliberately, not as a default.
- Treat this document, and other focused files under `docs/`, as the cache for
  "what are the rules" — point at them rather than re-deriving or re-explaining
  the same standards at the start of every session.

---

## How to use this document

- If you are about to touch `evaluate()`, any risk engine, correlation
  tracking, calibration, or a paper-store position-close path: re-read
  **Part 1** in full before writing code, and again before claiming the
  change is done.
- If you are about to explore unfamiliar code, plan a feature, or open a PR:
  **Part 2** describes the expected working process.
- If something here appears to conflict with what the code actually does,
  treat that as a documentation-vs-practice drift worth resolving explicitly
  — surface it rather than silently picking one side.
