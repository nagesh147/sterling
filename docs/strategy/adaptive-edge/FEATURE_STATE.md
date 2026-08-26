# Adaptive Edge — Feature State Traceability

## Authority

The Master Mathematical Specification v1.0 is authoritative. The implementation must preserve the event -> state -> feature separation and must not invent provider-specific fields.

## Implemented mapping

| Master Specification | Canonical implementation |
|---|---|
| §3 information rule | `build_feature_state()` uses current + prior state only |
| §5 validation | positive price validation, bid/ask ordering, non-negative volume/quantity, invalid volume reset handling |
| §7 price state | mid, spread, relative spread, price change, return, velocity, acceleration |
| §8 trade state | TTQ incremental volume with reset treated as data-quality failure |
| §9 aggressor state | BUY at/above ask, SELL at/below bid, UNKNOWN strictly inside spread |
| §10 delta | delta, cumulative delta, delta velocity, delta acceleration |
| §11 liquidity | bid/ask quantity and liquidity imbalance |
| §18 feature vector | downstream contract; full P/D/V/L/volatility/profile/options/time/quality vector is not yet claimed complete |

## Provider boundary

The feature state is provider-neutral. TrueData/Kite wire fields must be mapped into the canonical market/event contract before strategy features are computed. No TrueData API assumptions are encoded here because the TrueData account documentation has not yet been supplied.

## Deliberate non-claims

This module does **not** yet implement the complete Master Specification market-state surface. The following remain separate work items:

- multiple configured delta horizons;
- incremental volume-rate and trade-frequency distributions;
- multi-horizon volatility state;
- incremental volume profile;
- market profile;
- options-state vector;
- temporal state;
- data-quality event persistence/sequence handling at the canonical-event layer.

Those must be implemented from the corresponding source sections before the feature layer is marked complete.

## No invented strategy rules

No fixed trading threshold, score, indicator substitute, or provider-specific assumption is introduced by this module.
