"""The reconciled execution-authorization contract.

Two branches evolved this gate independently: one added an F-110 admission
token bound to the order fingerprint, the other added an ExecutionMode /
ReplayContext simulation path with a formula scope. The merge kept both, and
these tests pin the combination so a later edit cannot quietly drop either half.
"""
import pytest

from app.engines.adaptive_edge.broker_event_mapper import BrokerEventMapper, BrokerExecutionEvent
from app.engines.adaptive_edge.e2e import ExecutionMode, ReplayContext
from app.engines.adaptive_edge.execution_adapter import CanonicalExecutionStatus
from app.engines.adaptive_edge.execution_gateway import ExecutionGateway
from app.engines.adaptive_edge.formula_registry import FormulaStatus, get_formula
from app.engines.adaptive_edge.research_formulas import research_formula_table


class _Adapter:
    def __init__(self):
        self.submitted = []

    def submit(self, intent):
        self.submitted.append(intent)
        return "BROKER-1"


class _Intent:
    def fingerprint(self):
        return "fp-1"


def _research_gateway(adapter):
    return ExecutionGateway(adapter, None, None, authorized_formula_ids=("F-004",))


# --------------------------------------------------------------------------
# the F-110 admission token survives
# --------------------------------------------------------------------------

def test_a_research_gateway_demands_an_admission_token():
    adapter = _Adapter()
    with pytest.raises(PermissionError, match="F-110 admission token required"):
        _research_gateway(adapter).submit(_Intent())
    assert adapter.submitted == []


def test_a_formula_scope_cannot_be_used_instead_of_the_token():
    """The simulation scope must not become a way around the admission proof."""
    adapter = _Adapter()
    with pytest.raises(PermissionError, match="F-110 admission token required"):
        _research_gateway(adapter).submit(_Intent(), formula_ids=("F-004",))
    assert adapter.submitted == []


def test_a_forged_token_is_rejected():
    adapter = _Adapter()
    with pytest.raises(PermissionError, match="invalid F-110 admission token"):
        _research_gateway(adapter).submit(_Intent(), f110_admission_token="not-a-real-proof")
    assert adapter.submitted == []


def test_the_token_is_bound_to_this_intent():
    from hashlib import sha256
    adapter = _Adapter()
    other = sha256(b"F-110|a-different-intent").hexdigest()
    with pytest.raises(PermissionError, match="invalid F-110 admission token"):
        _research_gateway(adapter).submit(_Intent(), f110_admission_token=other)


# --------------------------------------------------------------------------
# production stays fail-closed while the strategy formulas are LOCKED
# --------------------------------------------------------------------------

def test_production_submission_is_blocked_while_formulas_are_locked():
    adapter = _Adapter()
    gateway = ExecutionGateway(adapter, None, None)          # no scope = production
    with pytest.raises(Exception):
        gateway.submit(_Intent())
    assert adapter.submitted == []


@pytest.mark.parametrize("formula_id", [f"F-1{n:02d}" for n in range(1, 15)])
def test_every_strategy_formula_is_still_locked(formula_id):
    assert get_formula(formula_id).status is FormulaStatus.LOCKED


# --------------------------------------------------------------------------
# main's simulation vocabulary survives
# --------------------------------------------------------------------------

def test_the_simulation_mode_and_replay_context_exist():
    assert ExecutionMode.PRODUCTION is not ExecutionMode.SIMULATION
    assert ReplayContext is not None


def test_the_new_pipeline_modules_import():
    from app.engines.adaptive_edge import historical_corpus, strategy_pipeline
    assert strategy_pipeline is not None and historical_corpus is not None


# --------------------------------------------------------------------------
# the reconciled spec-gap reporting
# --------------------------------------------------------------------------

def test_a_formula_without_a_recovered_form_is_reported_not_crashed():
    """The unguarded lookup this replaced raised KeyError instead of reporting."""
    table = research_formula_table()
    assert set(table) >= {f"F-1{n:02d}" for n in range(1, 15)}
    assert all(item.status in {"IMPLEMENTED", "RESEARCH_CODE_PRESENT_REGISTRY_LOCKED", "SPEC_GAP"}
               for item in table.values())


# --------------------------------------------------------------------------
# broker mapping: translate, then gate
# --------------------------------------------------------------------------

def _event(status, **kw):
    return BrokerExecutionEvent(
        broker_event_id="evt-1", order_intent_id="intent-1", broker_status=status,
        event_time="2026-08-19T03:45:02+00:00",
        filled_quantity=kw.get("filled_quantity", 0), fill_price=kw.get("fill_price"),
    )


def test_an_unknown_status_maps_to_unknown_and_is_gated_at_validate():
    mapper = BrokerEventMapper({"COMPLETE": CanonicalExecutionStatus.FILLED})
    canonical = mapper.map(_event("UNDOCUMENTED", filled_quantity=25, fill_price=100.0))
    assert canonical.event_type is CanonicalExecutionStatus.UNKNOWN
    with pytest.raises(ValueError):
        canonical.validate()


def test_fill_data_is_validated_even_for_an_unknown_status():
    mapper = BrokerEventMapper({})
    with pytest.raises(ValueError, match="filled_quantity cannot be negative"):
        mapper.map(_event("UNDOCUMENTED", filled_quantity=-1))
    with pytest.raises(ValueError, match="fill_price must be positive"):
        mapper.map(_event("UNDOCUMENTED", filled_quantity=1, fill_price=0.0))
