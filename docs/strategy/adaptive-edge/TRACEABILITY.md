# Adaptive Edge — Traceability

| ID | Requirement | Code | Tests | Status |
|---|---|---|---|---|
| F-001 | Causal availability | `adaptive_edge/feature_engine.py` | `test_adaptive_edge_pipeline.py` | RESOLVED |
| F-002 | Peak P&L | Accounting/protection owner | Pending strategy integration test | RESOLVED-ANCHORED |
| F-003 | Profit giveback | Accounting/protection owner | Pending strategy integration test | RESOLVED-ANCHORED |
| F-004 | Gross minus execution cost | `adaptive_edge/economic.py` | `test_adaptive_edge_pipeline.py` | RESOLVED |
| F-005 | Risk authorization immutable | `adaptive_edge/contracts.py` | `test_adaptive_edge_contracts.py` | RESOLVED |
| F-006 | Mode/risk independent | `adaptive_edge/contracts.py` | `test_adaptive_edge_contracts.py` | RESOLVED |
| F-007 | BUY uses executable ask | Execution owner | Pending | RESOLVED-ANCHORED |
| F-008 | SELL uses executable bid | Execution owner | Pending | RESOLVED-ANCHORED |
| F-101 | Feature formula | `adaptive_edge/feature_engine.py` contract | Pending | RESOLVED-BLOCKED |
| F-102 | Edge/prediction | `adaptive_edge/edge.py` contract | Pending | RESOLVED-BLOCKED |
| F-103 | Eligibility | Pending | Pending | RESOLVED-BLOCKED |
| F-104 | Dynamic mode | `adaptive_edge/contracts.py` state model | Pending exact thresholds | RESOLVED-BLOCKED |
| F-105 | Profit protection | Pending | Pending | RESOLVED-BLOCKED |
| F-106 | Dynamic risk | Pending | Pending | RESOLVED-BLOCKED |
| F-107 | Risk per unit | Pending | Pending | RESOLVED-BLOCKED |
| F-108 | Position sizing | Pending | Pending | RESOLVED-BLOCKED |
| F-109 | Instrument selection | Pending | Pending | RESOLVED-BLOCKED |
| F-110 | Entry trigger | Pending | Pending | RESOLVED-BLOCKED |
| F-111 | Exit trigger | Pending | Pending | RESOLVED-BLOCKED |
| F-112 | Protection parameterization | Pending | Pending | RESOLVED-BLOCKED |
| F-113 | Re-entry | Pending | Pending | RESOLVED-BLOCKED |
| F-114 | Multi-position interaction | Pending | Pending | RESOLVED-BLOCKED |

## Resolution semantics

`RESOLVED` means the formula and all required inputs are authoritative, causal, versioned, and testable.

`RESOLVED-ANCHORED` means the relationship is authoritative but integration testing remains outstanding.

`RESOLVED-BLOCKED` means the artifact has been individually attacked against the currently available source set and no authoritative complete definition was recovered. It is a terminal resolution of the current investigation, not an implementation authorization.

## Change rule

No implementation change may promote a `RESOLVED-BLOCKED` artifact by inference. To unlock it, either:

1. recover the authoritative original artifact; or
2. create an explicitly versioned Adaptive Edge strategy revision containing the complete definition and obtain strategy change approval.

The complete attack and resolution procedure is defined in `ARTIFACT_RESOLUTION.md`.
