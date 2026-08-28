"""One scan, two phases — and it must LOOK like one.

`KiteEngineScanner.scan` is wrapped: the main scan runs, then a second pass
evaluates broker-held contracts. The main scan clears `us.scanning` in its own
`finally`, and the held pass used to re-raise it only once it knew there was work
to do — which is *after* `client.get_positions_raw()`.

So for a full broker round-trip a scan was demonstrably running while the state
said idle. A status poll landing in that window reported "not scanning" with the
previous phase's label still on screen, which is what made the footer look stuck
on one symbol. The flag is now claimed before the round-trip and released on
every exit path.
"""
from unittest.mock import AsyncMock

import pytest

from app.services.kite_engine import held_contract_scan as hcs


class _Diag:
    def __getattr__(self, _name):
        return 0
    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)


class _State:
    def __init__(self):
        self.scanning = False
        self.scanning_label = ""
        self.rows = []
        self.scanned_contract_symbols = set()
        self.cancelled = False
        self.generated_ms = 0
        self.diag = _Diag()


class _Scanner:
    def __init__(self, st):
        self._st = st
    def snapshot(self, _uid):
        return self._st


@pytest.mark.asyncio
async def test_scanning_is_claimed_before_the_broker_round_trip():
    st = _State()
    seen: list[bool] = []

    async def positions():
        # Exactly where a status poll used to see "idle" mid-scan.
        seen.append(st.scanning)
        return {}

    client = AsyncMock()
    client.get_positions_raw = positions

    await hcs._append_held_contract_signals(
        _Scanner(st), uid="u1", client=client, cfg=object(),
        nfo_rows=(), bfo_rows=(), log_cb=None,
    )

    assert seen == [True], "the flag must already be set during the round-trip"


@pytest.mark.asyncio
async def test_the_flag_is_released_even_when_the_round_trip_fails():
    # The failure path is the one that matters: leaving `scanning` stuck true
    # would show a permanent scan and hide every later one.
    st = _State()
    client = AsyncMock()
    client.get_positions_raw = AsyncMock(side_effect=OSError("connection reset"))

    await hcs._append_held_contract_signals(
        _Scanner(st), uid="u1", client=client, cfg=object(),
        nfo_rows=(), bfo_rows=(), log_cb=None,
    )

    assert st.scanning is False
    assert st.scanning_label == ""


@pytest.mark.asyncio
async def test_the_flag_is_released_when_there_is_no_held_work():
    st = _State()
    client = AsyncMock()
    client.get_positions_raw = AsyncMock(return_value={})

    await hcs._append_held_contract_signals(
        _Scanner(st), uid="u1", client=client, cfg=object(),
        nfo_rows=(), bfo_rows=(), log_cb=None,
    )

    assert st.scanning is False, "an early return must not leave a scan showing"
    assert st.scanning_label == ""
