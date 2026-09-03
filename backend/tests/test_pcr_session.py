from app.api.v1.endpoints.pcr import _hhmm, _latest, _marks, _spot


def test_hhmm_from_iso():
    assert _hhmm("2026-09-03T09:16:00") == "09:16"
    assert _hhmm("09:15") == "09:15"


def test_one_minute_ticks_fill_fifteen_minute_slots():
    ticks = []
    for minute in range(10, 32):
        ticks.append({
            "time": f"2026-09-03T09:{minute:02d}:00",
            "pcr": 0.70 + minute / 1000,
            "volumePcr": 1.0,
            "changeOiPcr": 0.3,
            "indexClose": 23900 + minute,
        })
    marks = _marks(ticks)
    by = {m["hhmm"]: m for m in marks}
    assert "09:15" in by
    assert "09:30" in by
    assert by["09:15"]["indexClose"] == 23915
    assert by["09:30"]["indexClose"] == 23930


def test_latest_is_the_newest_print_not_the_list_order():
    ticks = [
        {"time": "2026-09-03T11:12:00", "pcr": 0.76, "volumePcr": 1.1, "changeOiPcr": 0.9, "indexClose": 23935.6},
        {"time": "2026-09-03T09:15:00", "pcr": 0.73, "volumePcr": 0.8, "changeOiPcr": 0.6, "indexClose": 23997.95},
    ]
    latest = _latest(ticks)
    assert latest is not None
    assert latest["hhmm"] == "11:12"
    assert latest["pcr"] == 0.76


def test_spot_uses_last_trade_price_not_previous_close():
    page = {
        "initialSpot": {
            "last_trade_price": 23935.25,
            "close": 23914.45,
            "change_per": 0.09,
            "timestamp": "2026-09-03T11:12:00",
        }
    }
    spot = _spot(page, {"indexClose": 23935.6})
    assert spot["ltp"] == 23935.25
    assert spot["changePer"] == 0.09
