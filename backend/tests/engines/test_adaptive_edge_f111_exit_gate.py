from app.engines.adaptive_edge.f111_exit_gate import ExitDecision, F111State, evaluate_exit


def test_f111_exits_on_protective_breach() -> None:
    assert evaluate_exit(F111State(True, 10, False, False, False)) is ExitDecision.EXIT


def test_f111_exits_on_non_positive_continuation_value() -> None:
    assert evaluate_exit(F111State(False, 0, False, False, False)) is ExitDecision.EXIT


def test_f111_exits_on_session_termination() -> None:
    assert evaluate_exit(F111State(False, 10, False, True, False)) is ExitDecision.EXIT


def test_f111_emergency_reversal_without_positive_continuation_exits() -> None:
    assert evaluate_exit(F111State(False, 0, True, False, False)) is ExitDecision.EXIT


def test_f111_improved_protection_updates_stop() -> None:
    assert evaluate_exit(F111State(False, 10, False, False, True)) is ExitDecision.UPDATE_STOP


def test_f111_holds_with_positive_continuation() -> None:
    assert evaluate_exit(F111State(False, 10, False, False, False)) is ExitDecision.HOLD
