"""A58 immutable decision/authorization audit-chain primitives."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


class AuditChainError(ValueError):
    """Raised when an A58 audit-chain invariant is violated."""


@dataclass(frozen=True)
class AuditLink:
    link_type: str
    reference_id: str

    def __post_init__(self) -> None:
        if not self.link_type.strip() or not self.reference_id.strip():
            raise AuditChainError("audit link type and reference are required")


@dataclass(frozen=True)
class DecisionAuditRecord:
    audit_id: str
    occurred_at_ms: int
    decision_id: str
    policy_id: str
    policy_version: str
    links: Tuple[AuditLink, ...]

    def __post_init__(self) -> None:
        for value, name in (
            (self.audit_id, "audit_id"),
            (self.decision_id, "decision_id"),
            (self.policy_id, "policy_id"),
            (self.policy_version, "policy_version"),
        ):
            if not value.strip():
                raise AuditChainError(f"{name} must not be empty")
        if self.occurred_at_ms < 0:
            raise AuditChainError("occurred_at_ms must be non-negative")
        if not self.links:
            raise AuditChainError("audit record requires lineage links")


def append_audit_record(
    chain: Tuple[DecisionAuditRecord, ...],
    record: DecisionAuditRecord,
) -> Tuple[DecisionAuditRecord, ...]:
    if chain and record.occurred_at_ms < chain[-1].occurred_at_ms:
        raise AuditChainError("audit records must be temporally ordered")
    return (*chain, record)


def require_link(record: DecisionAuditRecord, link_type: str) -> AuditLink:
    for link in record.links:
        if link.link_type == link_type:
            return link
    raise AuditChainError(f"required audit link is missing: {link_type}")
