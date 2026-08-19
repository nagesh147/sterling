# Adaptive Edge — Traceability

| ID | Requirement | Code | Tests | Status |
|---|---|---|---|---|
| F-001 | Causal availability | `adaptive_edge/feature_engine.py` | `test_adaptive_edge_pipeline.py` | RESOLVED |
| F-002 | Peak P&L | `adaptive_edge/accounting.py` | `test_adaptive_edge_pnl_reconciliation.py` | RESOLVED |
| F-003 | Profit giveback | `adaptive_edge/accounting.py` | `test_adaptive_edge_pnl_reconciliation.py` | RESOLVED |
| F-004 | Gross minus execution cost | `adaptive_edge/economic.py` | `test_adaptive_edge_pipeline.py` | RESOLVED |
| F-005 | Risk authorization immutable | `adaptive_edge/contracts.py` | `test_adaptive_edge_contracts.py` | RESOLVED |
| F-006 | Mode/risk independent | `adaptive_edge/contracts.py` | `test_adaptive_edge_contracts.py` | RESOLVED |
| F-007 | BUY uses executable ask | `adaptive_edge/research_references.py` | `test_adaptive_edge_research_e2e.py` | RESOLVED |
| F-008 | SELL uses executable bid | `adaptive_edge/research_references.py` | `test_adaptive_edge_research_e2e.py` | RESOLVED |
| F-101 | Feature formula | `adaptive_edge/f101.py` research only | `test_adaptive_edge_f101_trial.py` | RESEARCH / REGISTRY-LOCKED |
| F-102 | Edge/prediction | `edge.py` contract; T4 uses identity binder + explicit gross | No unique score recovered | RESOLVED-BLOCKED |
| F-103 | Eligibility | Pending unique source | Pending | RESOLVED-BLOCKED |
| F-104 | Dynamic mode | `adaptive_edge/opportunity_mode.py` research | Pending unique thresholds | RESOLVED-BLOCKED |
| F-105 | Profit protection | `adaptive_edge/protection.py` policy-driven | Pending unique parameters | RESOLVED-BLOCKED |
| F-106 | Dynamic risk | Pending unique source | Pending | RESOLVED-BLOCKED |
| F-107 | Risk per unit | `adaptive_edge/risk_sizing.py` | `test_adaptive_edge_risk_sizing.py` | RESEARCH / REGISTRY-LOCKED |
| F-108 | Position sizing | `adaptive_edge/risk_sizing.py` | `test_adaptive_edge_risk_sizing.py` | RESEARCH / REGISTRY-LOCKED |
| F-109 | Instrument selection | `instrument_selection.py` listed-only + `ListedInstrumentSelector` | `test_adaptive_edge_instrument_selection.py`, T4/T5 | RESEARCH / REGISTRY-LOCKED |
| F-110 | Entry trigger | `entry_decision.py` conjunction; ConservativeEV explicit | `test_adaptive_edge_entry_decision.py` | RESEARCH / REGISTRY-LOCKED |
| F-111 | Exit trigger | `adaptive_edge/lifecycle_engine.py` | `test_adaptive_edge_lifecycle_engine.py` | RESEARCH / REGISTRY-LOCKED |
| F-112 | Protection parameterization | `adaptive_edge/protection.py` caller policy | `test_adaptive_edge_protection.py` | RESEARCH / REGISTRY-LOCKED |
| F-113 | Re-entry | `admission.py` semantic only; no score | `test_adaptive_edge_admission.py` | SEMANTIC / NUMERIC-BLOCKED |
| F-114 | Multi-position interaction | INV-ENTRY-003 one-position only | `test_adaptive_edge_admission.py` | SEMANTIC / AGGREGATION-BLOCKED |

## Resolution semantics

`RESOLVED` means the formula and all required inputs are authoritative, causal, versioned, and testable.

`RESOLVED-ANCHORED` means the relationship is authoritative but integration testing remains outstanding.

`RESOLVED-BLOCKED` means the artifact has been individually attacked against the currently available source set and no authoritative complete definition was recovered. It is a terminal resolution of the current investigation, not an implementation authorization.

## Change rule

No implementation change may promote a `RESOLVED-BLOCKED` artifact by inference. To unlock it, either:

1. recover the authoritative original artifact; or
2. create an explicitly versioned Adaptive Edge strategy revision containing the complete definition and obtain strategy change approval.

The complete attack and resolution procedure is defined in `ARTIFACT_RESOLUTION.md`.
