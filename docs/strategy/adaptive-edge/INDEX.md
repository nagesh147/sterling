# Sterling Adaptive Edge — Canonical Strategy Folder

This directory is the permanent source of truth for the Adaptive Edge strategy.

## Rule

When implementing, reviewing, testing, backtesting, documenting, or changing Adaptive Edge, read this directory first. Do not reconstruct the strategy from chat history, memory, unrelated engine docs, or another strategy.

## Canonical artifact map

| Artifact | Purpose | Status |
|---|---|---|
| `SPEC.md` | End-to-end strategy architecture and hard boundaries | Active |
| `FORMULAS.md` | Formula registry; every mathematical rule gets an ID | Active |
| `DESIGN.md` | Component and dependency design | Active |
| `EXECUTION.md` | Entry, order, fill, position and exit semantics | Active |
| `RISK.md` | Risk authorization, sizing and protection semantics | Active |
| `BACKTEST.md` | Backtest/live parity and validation methodology | Active |
| `UI.md` | Dedicated Adaptive Edge terminal UI specification | Active |
| `TRACEABILITY.md` | Requirement -> formula -> code -> test matrix | Active |
| `RECOVERY.md` | Recovered decisions and unresolved definitions | Active |
| `ARTIFACT_RESOLUTION.md` | Evidence, attack, resolution and implementation gate | Active |
| `CHANGELOG.md` | Strategy-semantic changes only | Active |

## Non-negotiable source hierarchy

```text
1. This folder's frozen artifacts
2. Strategy tests/contracts
3. Strategy implementation
4. Shared platform contracts
5. Historical reports / exploratory studies
6. Chat history
```

A lower-level source cannot silently override a higher-level strategy definition.

## Semantic isolation

Adaptive Edge is a distinct strategy. It must not inherit formulas from:

- SuperTrend
- Value Flow Navigator
- Sterling crypto scalper
- old derivatives routing-gate studies
- unrelated directional engines

Shared infrastructure is allowed; shared strategy semantics are not.

## Current implementation gate

Known-safe formulas are implemented/anchored. Strategy-specific formulas whose exact definition has not been recovered are explicitly marked `RESOLVED-BLOCKED` in `FORMULAS.md` and must not be guessed.

Adaptive Edge remains non-executable while a required upstream strategy-specific formula is `RESOLVED-BLOCKED`.
