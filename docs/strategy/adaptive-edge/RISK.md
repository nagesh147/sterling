# Adaptive Edge — Risk Semantics

## Risk is authorization, not prediction

```text
Edge says: opportunity quality.
Economics says: whether acting is worthwhile after cost.
Risk says: how much loss is authorized.
```

These values cannot be substituted for one another.

## Immutable authorization

`RiskAuthorization` is immutable for the opportunity for which it was issued.

The following cannot increase it implicitly:

- favorable P&L
- increased prediction score
- DynamicMode transition
- better fill
- lower realized execution cost

A new authorization requires an explicit policy event.

## Profit protection

Peak P&L is accounting state, not risk budget:

```text
PeakPnL(t) = max(CurrentPnL(τ))
ProfitGiveback(t) = PeakPnL(t) - CurrentPnL(t)
```

Protection can reduce exposure or force an exit. It cannot silently increase the risk ceiling.

## Risk-definition recovery status

The repository was searched for the exact historical definitions of:

```text
EffectiveRisk_i
EffectiveRiskPerUnit
F-107
F-108
```

No authoritative historical definition was recovered.

`RECOVERY.md` explicitly records that F-101..F-114 were a reconstructed v0.1.0 model rather than recovered historical mathematics. Therefore F-107/F-108 cannot be used as evidence for the canonical strategy. They remain deprecated.

The Master Mathematical Specification does define these relationships:

```text
RiskPerUnit
    = EntryPrice - InitialStop

GrossRisk
    = RiskPerUnit × Q

Q
    = floor(MaxRisk / EffectiveRiskPerUnit)
```

and separately:

```text
EVPerRisk_i
    = ConservativeEV_i / EffectiveRisk_i
```

However, the source material available in this repository does not define the semantics or derivation of `EffectiveRisk_i`, nor establish that it is identical to `EffectiveRiskPerUnit`, `GrossRisk`, or any other existing risk quantity.

Therefore:

```text
RiskPerUnit                  EXACT operator
GrossRisk                    EXACT operator
Position-size equation       EXACT relationship
EffectiveRiskPerUnit         UNRESOLVED INPUT SEMANTICS
EffectiveRisk_i              BLOCKED
EVPerRisk_i                  EXACT relationship / BLOCKED input
```

No substitution is permitted.

In particular, do not implement any of the following without an authoritative source definition:

```text
EffectiveRisk_i = GrossRisk
EffectiveRisk_i = RiskPerUnit × Q
EffectiveRisk_i = EffectiveRiskPerUnit
EffectiveRisk_i = abs(EntryPrice - Stop)
EffectiveRisk_i = max(loss distribution)
```

Those are mathematically plausible alternatives, not recovered strategy semantics.

## Governing rule

A mathematically valid formula is insufficient. Every required input must have a source-defined semantic meaning and provenance before the formula is promoted to canonical strategy logic.
