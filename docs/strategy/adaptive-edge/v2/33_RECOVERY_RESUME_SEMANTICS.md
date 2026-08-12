# A57 — Recovery / Resume Semantics Contract

**Status:** FRAMEWORK IMPLEMENTED

## Purpose

A57 defines the boundary for recovery after an operational restriction. Clearing an incident does not silently restore trading permissions.

## Recovery flow

```text
restricted state
      |
      v
RECOVERY_PENDING
      |
      | recovery evidence + policy evaluation
      v
RECOVERED
      |
      | explicit resume authorization
      v
trading state may be restored
```

## Recovery evidence

A recovery decision retains:

- recovery identity
- source state
- recovery state
- triggering observation identity
- recovery evidence identity
- policy identity/version
- effective timestamp

## Resume authorization

A resume authorization must reference the recovery decision and use the same policy identity/version. Authorization cannot precede recovery effectiveness.

## Safety invariant

```text
fault cleared
    !=
automatic trading resume
```

A system may therefore remain operationally restricted after an underlying fault disappears until an explicit, auditable recovery decision and resume authorization exist.

## Deliberately unspecified

A57 does not invent:

- recovery timeouts
- health thresholds
- automatic restart rules
- position liquidation behavior
- strategy-specific recovery rules
- broker-specific recovery semantics
- capital or risk limits

Those require authoritative operational or strategy policy.

## Relationship to A56

A56 determines how operational state constrains trading permissions. A57 determines how a restricted system can transition toward restored operation without bypassing those permissions.
