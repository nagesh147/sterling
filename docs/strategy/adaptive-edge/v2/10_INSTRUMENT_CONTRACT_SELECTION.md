# Adaptive Edge V2 — Instrument / Contract Selection Definition

Artifact: A34
Version: 2.0.0-draft
Status: SPECIFICATION-DRAFT / PARTIALLY-BLOCKED
Implementation: NONE

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

## TrueData

TrueData documentation has not been received. Therefore:

```text
TrueData field mapping             = UNKNOWN
TrueData option-chain semantics    = UNKNOWN
TrueData historical availability   = UNKNOWN
TrueData quote timestamp semantics = UNKNOWN
TrueData contract metadata         = UNKNOWN
```

No implementation may infer these semantics from field names or generic market-data conventions.

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

**External UNKNOWN:** TrueData semantics, historical contract availability, broker contract metadata, execution-specific constraints.

## Implementation gate

A34 cannot become executable until the instrument source, contract identity, historical availability, and selection policy are documented and versioned; strike, expiry, and liquidity policies must also be resolved where applicable.

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
```

UNRESOLVED:

```text
universe scope
strike-selection policy
expiry-selection policy
liquidity definition
liquidity threshold
TrueData mappings
historical contract availability semantics
```

BLOCKERS:

TrueData documentation remains UNKNOWN. Exact option-selection semantics remain undefined. This blocks executable selection, not the architecture.

NEXT ARTIFACT:
A35 — Execution Price / Cost and Order Contract Definition.
