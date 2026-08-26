import pytest

from app.engines.adaptive_edge.decision_audit import (
    AuditChainError,
    AuditLink,
    DecisionAuditRecord,
    append_audit_record,
    require_link,
)


def record(at=100, links=None):
    return DecisionAuditRecord(
        audit_id=f"audit-{at}",
        occurred_at_ms=at,
        decision_id="decision-1",
        policy_id="policy-1",
        policy_version="1",
        # `links or [default]` swallowed the one case this file needs to test:
        # an explicitly empty list is falsy, so links=[] silently became the
        # default and the record under test had lineage after all.
        links=tuple([AuditLink("feature_snapshot", "feature-1")] if links is None else links),
    )


def test_audit_record_requires_lineage():
    with pytest.raises(AuditChainError):
        record(links=[])


def test_audit_chain_is_temporally_ordered():
    chain = (record(100),)
    with pytest.raises(AuditChainError):
        append_audit_record(chain, record(99))


def test_audit_chain_accepts_equal_or_later_timestamp():
    chain = (record(100),)
    result = append_audit_record(chain, record(100))
    assert len(result) == 2


def test_required_link_is_retrievable():
    result = require_link(record(links=[AuditLink("decision", "decision-1")]), "decision")
    assert result.reference_id == "decision-1"


def test_missing_required_link_is_rejected():
    with pytest.raises(AuditChainError):
        require_link(record(), "execution")
