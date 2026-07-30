"""Signal detail must resolve rows from BOTH engines.

Navigator is a peer engine with its own snapshot. Its originated rows never
pass through the Kite engine's scanner, and when the SuperTrend engine is
switched off that scanner holds nothing at all — so a detail lookup that only
consults the scanner 404s on a board the user can plainly see.
"""
from __future__ import annotations

import pytest

from app.engines.sterling_kite_engine.schemas import AlignmentChip, EngineSignalRow
from app.services.kite_engine import detail as detail_service
from app.services.kite_engine.scanner import scanner
from app.services.navigator import runtime as navigator_runtime

_TS = 1_753_000_000_000


class FakeClient:
    """No legs on these rows, so only the underlying LTP is ever requested."""

    async def get_ltp(self, symbols):
        return {symbols[0]: {"last_price": 24_600.0}}

    async def get_quote(self, symbols):  # pragma: no cover - no legs in these rows
        return {}


def _nav_row(token=256265, timestamp_ms=_TS, **updates):
    row = EngineSignalRow(
        underlying="NIFTY 50", token=token, exchange="NFO", regime="BULL",
        alignment=AlignmentChip(fast=0, mid=0, slow=0),
        direction="long", option_type="CE", legs=[],
        spot=24_500.0, underlying_spot=24_500.0, stop_loss=24_400.0, score=50.0,
        timestamp_ms=timestamp_ms, is_active=True, is_fresh=True, source="navigator",
    )
    return row.model_copy(update=updates)


@pytest.fixture(autouse=True)
def clean_snapshots():
    """Start with an empty scanner — the point is that Navigator answers alone."""
    scanner._users.pop("user-1", None)
    navigator_runtime._snapshots.pop("user-1", None)
    yield
    scanner._users.pop("user-1", None)
    navigator_runtime._snapshots.pop("user-1", None)


class TestNavigatorOwnedDetail:
    @pytest.mark.asyncio
    async def test_navigator_row_resolves_when_the_scanner_has_nothing(self):
        snap = navigator_runtime.snapshot("user-1")
        snap.rows = [_nav_row()]

        out = await detail_service.build_detail(FakeClient(), "user-1", 256265, _TS)

        assert out is not None
        assert out.underlying == "NIFTY 50"
        assert out.triggered_ms == _TS
        assert out.spot_now == 24_600.0

    @pytest.mark.asyncio
    async def test_prefers_the_clicked_timestamp_but_still_answers_without_it(self):
        snap = navigator_runtime.snapshot("user-1")
        snap.rows = [_nav_row(timestamp_ms=_TS), _nav_row(timestamp_ms=_TS + 3_600_000)]

        exact = await detail_service.build_detail(FakeClient(), "user-1", 256265, _TS)
        assert exact.triggered_ms == _TS

        # a background scan can regroup the row between click and request — answer
        # with the newest match rather than a misleading 404
        stale = await detail_service.build_detail(FakeClient(), "user-1", 256265, 1)
        assert stale.triggered_ms == _TS + 3_600_000

    @pytest.mark.asyncio
    async def test_unknown_token_is_still_a_miss(self):
        snap = navigator_runtime.snapshot("user-1")
        snap.rows = [_nav_row()]

        assert await detail_service.build_detail(FakeClient(), "user-1", 999_999, _TS) is None
