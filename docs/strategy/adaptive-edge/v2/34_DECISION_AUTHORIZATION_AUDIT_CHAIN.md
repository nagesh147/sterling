# A58 — Decision / Authorization Audit Chain Contract

**Status:** FRAMEWORK IMPLEMENTED

## Purpose

A58 preserves the lineage required to answer why a decision or order was permitted without reconstructing the answer from mutable current configuration.

## Audit chain

```text
feature snapshot
      |
      v
prediction / model state
      |
      v
economic decision
      |
      v
risk authorization
      |
      v
operational authorization
      |
      v
execution authorization
      |
      v
execution event
```

Each persisted audit record retains an explicit identity, timestamp, decision identity, policy identity/version, and one or more lineage links.

## Required properties

1. Audit records are immutable value objects.
2. A record cannot exist without lineage links.
3. A chain cannot move backward in event time.
4. Individual lineage references remain explicit rather than inferred.
5. Missing required lineage is a contract violation.

## Audit question

The chain is designed to make the following reconstructible:

```text
Why was this decision/order allowed?
```

The answer must be obtained from recorded decision and authorization evidence, not from today's configuration.

## Scope boundary

A58 does not define the strategy's mathematics, risk limits, authorization thresholds, execution rules, or operational thresholds. It defines only the evidence lineage needed to audit those decisions once their governing policies exist.

## Relationship to A57

A57 establishes explicit recovery/resume authorization. A58 provides the lineage layer through which such authorizations and downstream decisions can be audited.
