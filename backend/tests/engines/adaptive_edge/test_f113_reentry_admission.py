from __future__ import annotations

from app.engines.adaptive_edge.f113_reentry_admission import ReentryContext, evaluate_reentry


def test_f113_requires_all_structural_reentry_conditions():
    assert evaluate_reentry(ReentryContext(True, True, True, True)).admitted is True
    for context in (
        ReentryContext(False, True, True, True),
        ReentryContext(True, False, True, True),
        ReentryContext(True, True, False, True),
        ReentryContext(True, True, True, False),
    ):
        assert evaluate_reentry(context).admitted is False
