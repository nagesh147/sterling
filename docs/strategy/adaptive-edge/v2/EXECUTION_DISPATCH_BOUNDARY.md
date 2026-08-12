# Adaptive Edge V2 — Execution Dispatch Boundary

**Status:** FAIL-CLOSED

## Purpose

The execution dispatch boundary is the final handoff between an already-constructed provider-neutral order intent and an external execution adapter.

It does not construct strategy signals, choose instruments, calculate size, invent prices, or bypass strategy readiness.

## Required ordering

```text
Strategy decision
      |
      v
Execution gate
      |
      +-- BLOCKED --> dispatcher is never called
      |
      +-- AUTHORIZED
              |
              v
        OrderDispatcher
```

## Invariants

1. The default dispatch path requires all strategy-specific formulas F-101..F-114 to be `IMPLEMENTED`.
2. An unresolved formula prevents the dispatcher from being called.
3. An unknown formula ID is blocking.
4. The dispatch layer does not synthesize order fields.
5. The dispatcher receives only an already-constructed `OrderIntent`.
6. Explicitly supplied alternative formula sets are intended for infrastructure tests and controlled integration boundaries; production strategy execution must use the default required set.

## Scope

This boundary makes the non-executable state enforceable at the final adapter handoff. It does not resolve the missing Adaptive Edge strategy mathematics.
