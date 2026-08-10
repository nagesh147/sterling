# Adaptive Edge — Traceability

| ID | Requirement | Code | Tests | Status |
|---|---|---|---|---|
| F-001 | Causal availability | `adaptive_edge/feature_engine.py` | `test_adaptive_edge_pipeline.py` | Implemented |
| F-002 | Peak P&L | Accounting/protection owner | Pending strategy integration test | Anchored |
| F-003 | Profit giveback | Accounting/protection owner | Pending strategy integration test | Anchored |
| F-004 | Gross minus execution cost | `adaptive_edge/economic.py` | `test_adaptive_edge_pipeline.py` | Implemented |
| F-005 | Risk authorization immutable | `adaptive_edge/contracts.py` | `test_adaptive_edge_contracts.py` | Implemented |
| F-006 | Mode/risk independent | `adaptive_edge/contracts.py` | `test_adaptive_edge_contracts.py` | Implemented |
| F-007 | BUY uses executable ask | Execution owner | Pending | Anchored |
| F-008 | SELL uses executable bid | Execution owner | Pending | Anchored |
| F-101 | Feature formula | `adaptive_edge/feature_engine.py` contract | Pending | LOCKED |
| F-102 | Edge/prediction | `adaptive_edge/edge.py` contract | Pending | LOCKED |
| F-103 | Eligibility | Pending | Pending | LOCKED |
| F-104 | Dynamic mode | `adaptive_edge/contracts.py` state model | Pending exact thresholds | LOCKED |
| F-105 | Profit protection | Pending | Pending | LOCKED |
| F-106 | Dynamic risk | Pending | Pending | LOCKED |
| F-107 | Risk per unit | Pending | Pending | LOCKED |
| F-108 | Position sizing | Pending | Pending | LOCKED |
| F-109 | Instrument selection | Pending | Pending | LOCKED |
| F-110 | Entry trigger | Pending | Pending | LOCKED |
| F-111 | Exit trigger | Pending | Pending | LOCKED |
| F-112 | Protection parameterization | Pending | Pending | LOCKED |
| F-113 | Re-entry | Pending | Pending | LOCKED |
| F-114 | Multi-position interaction | Pending | Pending | LOCKED |

## Change rule

No implementation PR is complete if it introduces or changes a strategy formula without updating this matrix and the canonical formula registry.
