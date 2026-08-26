# A194 — Runtime Verification & Conformance Evidence Contract

## Status
CANONICAL NEXT-PHASE CONTRACT

## Purpose
Define the evidence gate required after implementation changes. A194 does not declare code correct merely because tests exist; it requires executable evidence, traceability, and adversarial verification.

## Evidence hierarchy
```text
source implementation
    ↓
unit invariants
    ↓
component tests
    ↓
full regression
    ↓
static dependency audit
    ↓
execution-path audit
    ↓
CI evidence
    ↓
conformance decision
```

## Required evidence
### 1. Feature invariants
All A192 invariants must execute successfully:
```text
future availability
transitive causal violation
missing/stale/invalid/not-applicable semantics
provenance
version compatibility
instrument identity
immutability
serialization fidelity
formula lock
execution bypass prevention
```

### 2. Regression
The complete backend Adaptive Edge suite and repository regression gate must pass. Frontend verification must remain green where the PR affects shared contracts.

### 3. Zero-regression gate
The changed branch must not introduce failures relative to the merge base unless the failure is explicitly classified, justified, and covered by the conformance change.

### 4. Static boundary audit
Verify that feature infrastructure does not import or directly invoke broker execution, order submission, or other forbidden downstream capabilities.

### 5. Runtime path audit
Trace:
```text
feature snapshot
 -> edge/economic eligibility
 -> decision
 -> risk
 -> execution gate
```
No feature object may directly create an execution intent.

### 6. CI evidence
Record workflow, run, job, commit SHA, test environment, result, and timestamp. An in-progress workflow is not evidence of pass.

## Failure handling
Any failed invariant, regression, static-boundary violation, or runtime-path violation keeps A194 OPEN. Do not weaken the test to obtain a pass.

## Strategy locks
A194 must not unlock or invent:
```text
F-101..F-114
risk parameters
stop/trail/profit-lock parameters
horizon thresholds
learned model parameters
provider semantics
```

## Evidence record
The conformance record must include:
```text
commit_sha
pr_number
workflow_run_ids
job_ids
environment_versions
test_command
passed_tests
failed_tests
static_audit_result
runtime_path_result
known_external_blockers
review_decision
```

## Acceptance states
```text
PASS
PASS_WITH_EXPLICIT_EXTERNAL_BLOCKERS
FAIL
INCOMPLETE
```
`INCOMPLETE` applies while required CI or runtime evidence is still executing or unavailable.

## Current external dependency
Provider semantics and empirical validation remain outside this gate. A194 verifies implementation conformance to the frozen contract; it does not prove trading profitability or production readiness.

## Invariants
```text
INV-194-001 test existence is not test evidence
INV-194-002 in-progress CI cannot be recorded as PASS
INV-194-003 failed evidence cannot be hidden by changing the test
INV-194-004 conformance is evaluated against a specific commit SHA
INV-194-005 execution-path audit is independent of unit tests
INV-194-006 static dependency violations fail conformance
INV-194-007 strategy locks remain locked
INV-194-008 external-provider verification remains separate
INV-194-009 profitability is not an implementation-conformance criterion
INV-194-010 production authorization requires gates beyond A194
```

## Status
```text
ARCHITECTURE: COMPLETE
IMPLEMENTATION CONFORMANCE: A193 pending CI closure
A194 CONTRACT: COMPLETE
CURRENT EVIDENCE: INCOMPLETE while CI is running
NEXT: collect CI results, close A193, then execute A194 evidence gate
```
