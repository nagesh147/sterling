# Adaptive Edge — Dedicated UI

## Principle

Adaptive Edge must not reuse the SuperTrend / Value Flow Navigator signal table as its strategy surface.

The existing shared signal table is an evidence/list surface for two engines. Adaptive Edge needs a decision surface that exposes the full causal chain:

```text
Opportunity -> Edge -> Economics -> Mode -> Risk -> Position -> Protection
```

## Placement

Use the same terminal location currently occupied by the shared signal table, but render an Adaptive Edge-specific panel when Adaptive Edge is selected.

Do not mix Adaptive Edge rows into the SuperTrend/Navigator table.

## Primary layout

```text
+--------------------------------------------------------------------------+
| ADAPTIVE EDGE   [AUTO/PAPER/LIVE] [SCAN] [SETTINGS]                     |
+--------------------------------------------------------------------------+
| MARKET / STATE | EDGE | ECONOMICS | MODE | RISK | POSITION | PROTECTION |
+--------------------------------------------------------------------------+
| NIFTY ...                                                              |
| state          | score | gross     | mode | auth | qty      | giveback  |
| features       | conf  | costs     | age  | used | entry    | peak PnL  |
|                |       | net       |      | max  | LTP      | stop      |
+--------------------------------------------------------------------------+
```

## Row requirements

Every candidate row must expose:

- instrument
- observation time
- feature quality/staleness
- edge score/prediction
- expected gross value
- estimated execution cost
- expected net value
- economic eligibility
- dynamic mode
- risk authorization state
- authorized risk
- current P&L
- peak P&L
- profit giveback
- protection state
- decision/rejection reason
- formula IDs used by the decision

## Decision detail drawer

Clicking a row opens a causal audit drawer, not the existing SignalDetailPane semantics:

```text
OBSERVATION
  timestamp
  source freshness

FEATURES
  feature -> value -> source timestamp

EDGE
  formula ID/version
  inputs
  output

ECONOMICS
  gross value
  cost components
  net value
  eligibility

MODE
  previous mode -> current mode
  transition reason

RISK
  authorization ID
  authorized risk
  consumed risk

EXECUTION
  intent
  order
  fill(s)

PROTECTION
  peak P&L
  current P&L
  giveback
  active protection rule

DECISION
  ENTER / HOLD / EXIT / REJECT
```

## UI invariants

The UI is read-only with respect to strategy mathematics.

It must never calculate an edge score, risk authorization, or profit-protection threshold locally. It displays backend-authoritative values and formula IDs.

A missing value is shown as `—`, never inferred.

## Controls

Allowed controls:

- scan/run
- paper/live mode where platform policy allows it
- strategy configuration navigation
- row selection
- sorting/filtering
- chart/detail navigation

Forbidden direct UI mutation:

- changing authorized risk after the fact
- changing a computed edge score
- changing a fill price
- rewriting peak P&L
- bypassing economic eligibility

## Visual language

Use existing Sterling terminal tokens. Keep the panel information-dense but distinct from the old signal table. Labels should be strategy concepts, not SuperTrend/Navigator terminology.
