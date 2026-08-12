# Adaptive Edge V2 — Instrument / Contract Selection Definition

Artifact: A34
Version: 2.0.0-draft
Status: SPECIFICATION-DRAFT / PARTIALLY-BLOCKED
Implementation: PARTIAL — TrueData market-data adapter implemented; strategy selection remains blocked

## Purpose

Define the causal boundary and contract identity required before Adaptive Edge selects a tradable instrument. This artifact does not choose NIFTY strikes, expiries, liquidity thresholds, or other numerical parameters without authoritative definitions and validation.

## Canonical dependency

```text
Opportunity
 -> InstrumentUniverse(t_d)
 -> CandidateContracts(t_d)
 -> ContractValidity
 -> SelectionPolicy
 -> SelectedInstrument
```

Selection uses only information available at decision time `t_d`.

## Contract identity

A selected instrument must have an immutable identity sufficient to distinguish it from every other contract. For options, the source-defined identity will ordinarily require fields such as underlying, instrument identifier, option type, strike, expiry, contract multiplier/quantity semantics, and venue. The exact field set is SOURCE-DEFINED.

## Historical validity

Historical reconstruction must use the contract universe actually available at the historical decision time. Current chains, future-listed contracts, future strike availability, future expiry knowledge, and future liquidity cannot influence an earlier decision.

## Candidate layers

```text
InstrumentUniverse(t_d)
CandidateContracts(t_d)
EligibleContracts(t_d)
SelectedInstrument(t_d)
```

These are distinct. The universe establishes existence; candidate generation applies structural constraints; eligibility applies strategy/execution constraints; selection applies a versioned policy.

## Selection contract

```text
Select(CandidateContracts(t_d), SelectionPolicyVersion, DecisionState(t_d))
    -> SelectedInstrument
```

No numerical ranking or threshold is frozen here.

## Required semantics

Every selection input must eventually identify:

```text
source
owner
semantic meaning
unit
observation time
availability time
validity interval
historical availability
failure behavior
version
```

## Strike

Strike is a property of an existing option contract. A34 does not define ATM, ITM/OTM, strike distance, moneyness, delta-based selection, or premium-based selection. No strike offset is invented.

## Expiry

Expiry is a property of an existing contract. A34 does not choose nearest, weekly, monthly, DTE minimum, DTE maximum, or any expiry preference. Such rules require an explicit versioned strategy definition and validation.

## Liquidity

Liquidity is not a generic threshold. If used, its exact observable must be defined, e.g. spread, volume, open interest, quote freshness, depth, or execution-cost estimate. These variables are not interchangeable. No threshold is frozen.

## Price references

Bid, ask, last, mid, and executable references are distinct. Selection must not silently substitute one for another. Execution defines the price actually used for an order action.

## Option dependencies

Potential dependencies include underlying observation, option-chain snapshot, strike, expiry, option type, contract multiplier, quote state, liquidity observations, and execution constraints. The exact dependency set remains unresolved until source and execution contracts are documented.

## TrueData source recovery

The supplied TrueData Market Data API V2.6 documentation and TCP API V2.3 documentation now provide authoritative market-data transport contracts.

### Historical REST

TrueData V2.6 defines:

```text
Authentication: POST https://auth.truedata.in/token
History base: https://history.truedata.in
Token type: bearer
Token validity: 3600 seconds
```

The authentication request is `application/x-www-form-urlencoded` with the documented fields `username`, `password`, and the documented `grant_type` value. The adapter preserves the source spelling rather than silently correcting it.

The documented historical tick endpoint is:

```text
GET /getticks
symbol
bidask
from
 to
response=csv/json
```

The documented last-N-ticks endpoint is:

```text
GET /getlastnticks
symbol
bidask
response=csv/json
nticks=1..200
interval=tick
```

The documented LTP retrieval uses the same last-N-ticks endpoint with `nticks=1`.

The documented historical response fields include:

```text
timestamp
ltp
volume
oi
bid
bidqty
ask
askqty
```

Bid/ask fields are available when requested/enabled.

The documented request limits are:

```text
Tick history: 5/sec, 300/min, 18000/hour
Minute-bar history: 10/sec, 600/min, 18000/hour
```

The supplied V2.6 source lists Bar Data History and Last-N-Bars History, but the exact request contract was not recoverable from the uploaded source text used for this implementation. No bar endpoint has been invented.

### Symbol master

The supplied V2.6 source defines the symbol-master endpoint:

```text
GET https://api.truedata.in/getAllSymbols
```

with segments:

```text
eq
fo
in
fut
mcx
all
bseeq
bsefo
```

It also explicitly documents `search`, `csv=true`, and `allexpiry=true`. The source recommends retrieving large master files once daily and storing them locally.

### Option-chain symbols

The supplied V2.6 source defines:

```text
GET https://api.truedata.in/getOptionChain
symbol=<underlying>
expiry=<yyyymmdd>
csv=true (optional)
```

This establishes an authoritative provider endpoint for obtaining option-chain symbols for a specified underlying and expiry.

### Important remaining limitation

The TrueData documentation establishes provider transport and raw market-data fields. It does **not** define Adaptive Edge's strategy-specific strike-selection policy, expiry-selection policy, liquidity threshold, or historical contract-selection rule.

It also does not, from the recovered material, establish a time-indexed historical option-chain universe sufficient by itself to prove that every candidate contract was knowable at every historical `t_d`. That remains a separate historical-availability dependency.

Therefore:

```text
TrueData transport mapping          = RESOLVED
TrueData historical tick contract   = RESOLVED
TrueData symbol-master endpoint     = RESOLVED
TrueData option-chain endpoint      = RESOLVED
TrueData bar request contract       = UNKNOWN
Historical candidate availability   = PARTIAL / UNKNOWN
Adaptive Edge strike policy         = UNKNOWN
Adaptive Edge expiry policy         = UNKNOWN
Adaptive Edge liquidity policy      = UNKNOWN
```

## Selection / execution separation

```text
SelectedInstrument != ExecutableOrder != Fill
```

Selecting a contract does not establish that an order can be filled.

## Causal restrictions

Candidate filtering cannot use future return, future volatility, future liquidity, future fill quality, future P&L, or future labels. Learned parameters are permitted only after prior promotion under the V2 learning protocol.

## Bias attacks

**Look-ahead:** future chain information cannot construct historical candidates.

**Selection bias:** selecting the contract that eventually produced the best P&L is invalid.

**Survivorship bias:** historical candidate universes must include contracts that later expired worthless or became unattractive.

**Multiple testing:** if many contracts are scored and one is selected, the selection procedure itself is part of the strategy and must be validated temporally.

## Missing / ambiguous data

Missing required contract metadata produces an explicit insufficient-information/block state. No default strike or expiry is selected. Ambiguous source records must not be merged implicitly.

## Determinism

Given the same historical contract universe, market state, strategy state, and selection-policy version, replay must produce the same candidate and selected-contract sequence.

## Parameter classes

**Frozen:** causal selection boundary, contract identity, historical candidate construction, selection/execution separation, provenance, deterministic replay.

**Source-defined configuration:** universe membership, contract metadata, quantity increment, contract multiplier.

**Learned:** any learned selection parameter remains undefined and requires a later learning artifact.

**External UNKNOWN:** historical contract availability semantics, broker contract metadata, execution-specific constraints, and the missing TrueData bar request contract.

## Implementation gate

The TrueData transport adapter may be used for documented provider operations. A34 strategy selection cannot become executable until the historical instrument universe, contract identity, historical availability semantics, and selection policy are documented and versioned; strike, expiry, and liquidity policies must also be resolved where applicable.

## ARCHITECTURE STATUS

FROZEN:

```text
InstrumentUniverse
CandidateContracts
EligibleContracts
SelectedInstrument
historical contract identity
causal candidate construction
selection/execution separation
survivorship protection
selection provenance
deterministic replay
TrueData REST authentication contract
TrueData historical tick contract
TrueData symbol-master endpoint
TrueData option-chain endpoint
```

UNRESOLVED:

```text
universe scope
strike-selection policy
expiry-selection policy
liquidity definition
liquidity threshold
historical contract availability semantics
TrueData bar request contract
```

BLOCKERS:

Exact option-selection semantics and time-indexed historical candidate availability remain undefined. This blocks executable Adaptive Edge contract selection, not the provider adapter itself.

NEXT ARTIFACT:
A35 — Execution Price / Cost and Order Contract Definition.
