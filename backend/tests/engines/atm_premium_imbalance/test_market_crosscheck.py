"""Independent market-data cross-check of the decoded video observations.

Two layers:

* Fixture tests always run and cover the comparison logic.
* The **real** cross-check runs only when the offline lake is attached. It
  compares V17's printed index level and chosen strike against Kite's own
  SENSEX minute bars and instrument master, and is skipped -- loudly, with the
  reason -- when the lake is absent, so CI never silently reports coverage it
  did not have.

Why this matters: A231's readings were self-verified against identities the
source bot itself computed. That catches transcription slips but not a shared
misreading. This is the external check.
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json

import pytest

from app.engines.atm_premium_imbalance.market_crosscheck import (
    VERDICT_MATCH, VERDICT_MISMATCH, VERDICT_UNAVAILABLE, IndexBar,
    check_contract_metadata, check_session_open, format_table,
    nearest_listed_strike, open_bar, summarise,
)
from app.engines.atm_premium_imbalance import select_atm_strike

UTC = timezone.utc
IST = timezone(timedelta(hours=5, minutes=30))

#: kitelake stores prices as int64 = round(rupees * PRICE_SCALE). Documented in
#: kitelake/config.py, not inferred here.
PRICE_SCALE = 10_000

# ---------------------------------------------------------------- fixtures

def bar(y, m, d, hh, mm, o, h=None, l=None, c=None):
    return IndexBar(datetime(y, m, d, hh, mm, tzinfo=UTC), o, h or o, l or o, c or o)


def test_open_bar_is_matched_on_ist_wall_time_not_position():
    bars = [bar(2026, 7, 30, 3, 44, 1.0), bar(2026, 7, 30, 3, 45, 77638.86), bar(2026, 7, 30, 3, 46, 2.0)]
    got = open_bar(bars, date(2026, 7, 30))
    assert got is not None and got.open == 77638.86
    assert got.ts_ist.hour == 9 and got.ts_ist.minute == 15


def test_open_bar_returns_none_for_a_session_not_present():
    assert open_bar([bar(2026, 7, 30, 3, 45, 1.0)], date(2026, 8, 20)) is None


def test_nearest_listed_strike_agrees_with_the_strategys_own_selector():
    """Guards against the cross-check being circular *or* divergent."""
    strikes = [77400.0, 77500.0, 77600.0, 77700.0]
    for spot in (77638.86, 77370.77, 77500.0, 77650.0, 77449.99):
        assert nearest_listed_strike(spot, strikes) == select_atm_strike(spot, strikes)


def test_session_open_check_flags_a_mismatch():
    bars = [bar(2026, 7, 30, 3, 45, 77638.86)]
    checks = check_session_open(
        session=date(2026, 7, 30), observed_index_ltp=77000.00, observed_strike=77600.0,
        bars=bars, listed_strikes=[77500.0, 77600.0, 77700.0],
    )
    by = {c.field: c for c in checks}
    assert by["index_ltp_at_open"].verdict == VERDICT_MISMATCH
    assert by["atm_strike"].verdict == VERDICT_MATCH
    assert summarise(checks)["contradicted"] is True


def test_missing_bars_are_unavailable_not_a_pass():
    checks = check_session_open(
        session=date(2026, 8, 20), observed_index_ltp=77638.86, observed_strike=77500.0,
        bars=[], listed_strikes=[77500.0],
    )
    assert all(c.verdict == VERDICT_UNAVAILABLE for c in checks)
    s = summarise(checks)
    assert s["match"] == 0 and s["contradicted"] is False


def test_contract_metadata_check():
    rows = [
        {"expiry": "2026-08-20", "strike": s, "option_type": t, "lot_size": 20, "tick_size": 0.05}
        for s in (77400.0, 77500.0, 77600.0) for t in ("CE", "PE")
    ]
    checks = check_contract_metadata(
        observed_lot_size=20, observed_tick_size=0.05, expiry="2026-08-20",
        strike=77500.0, instrument_rows=rows,
    )
    by = {c.field: c for c in checks}
    assert by["lot_size"].verdict == VERDICT_MATCH
    assert by["tick_size"].verdict == VERDICT_MATCH
    assert by["strike_has_both_legs"].verdict == VERDICT_MATCH
    assert by["strike_ladder_uniform"].verdict == VERDICT_MATCH
    assert by["strike_ladder_uniform"].external == 100


def test_unlisted_expiry_is_unavailable():
    checks = check_contract_metadata(
        observed_lot_size=20, observed_tick_size=0.05, expiry="2026-07-30",
        strike=77600.0, instrument_rows=[{"expiry": "2026-08-20", "strike": 1.0,
                                         "option_type": "CE", "lot_size": 20, "tick_size": 0.05}],
    )
    assert checks[0].verdict == VERDICT_UNAVAILABLE


# ------------------------------------------------------ the real cross-check

def _lake_root():
    """Locate the offline lake via kitelake's own roots.json."""
    cfg = Path.home() / ".config" / "kitelake" / "roots.json"
    if not cfg.exists():
        return None
    try:
        known = json.loads(cfg.read_text()).get("known") or []
    except (json.JSONDecodeError, OSError):
        return None
    for entry in known:
        p = entry.get("last_path")
        if p and Path(p).is_dir():
            return Path(p)
    return None


def _sensex_bars(root: Path, session: date):
    import pyarrow.parquet as pq
    p = root / "bars" / "interval=minute" / "exchange=BSE" / "segment=INDICES" / "265__SENSEX.parquet"
    if not p.exists():
        return []
    d = pq.read_table(p).to_pydict()
    out = []
    for i, ts in enumerate(d["ts"]):
        stamp = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
        if stamp.astimezone(IST).date() != session:
            continue
        out.append(IndexBar(stamp, d["open"][i] / PRICE_SCALE, d["high"][i] / PRICE_SCALE,
                            d["low"][i] / PRICE_SCALE, d["close"][i] / PRICE_SCALE))
    return out


def _sensex_options(root: Path):
    import pyarrow.parquet as pq
    p = root / "instruments" / "latest.parquet"
    if not p.exists():
        return []
    d = pq.read_table(p).to_pydict()
    rows = []
    for i in range(len(d["tradingsymbol"])):
        if d["name"][i] != "SENSEX" or d["instrument_type"][i] not in ("CE", "PE"):
            continue
        rows.append({
            "expiry": str(d["expiry"][i])[:10], "strike": float(d["strike"][i]),
            "option_type": d["instrument_type"][i], "lot_size": int(d["lot_size"][i]),
            "tick_size": float(d["tick_size"][i]),
        })
    return rows


@pytest.fixture(scope="module")
def lake():
    root = _lake_root()
    if root is None:
        pytest.skip("offline lake not attached — external cross-check cannot run")
    return root


def test_v17_index_level_and_strike_match_real_market_data(lake):
    """V17 printed `SENSEX LTP : 77638.86` and `Strike : 77600`.

    Both are checked against Kite's own SENSEX minute bars: the bot's first
    post-open tick should equal the 09:15 IST bar's open, since both are the
    session's first trade.
    """
    session = date(2026, 7, 30)
    bars = _sensex_bars(lake, session)
    if not bars:
        pytest.skip(f"lake holds no SENSEX minute bars for {session}")
    options = _sensex_options(lake)
    listed = sorted({r["strike"] for r in options}) or [77600.0]

    checks = check_session_open(
        session=session,
        observed_index_ltp=77638.86,     # A231, V17 entry block
        observed_strike=77600.0,         # A231/M4
        bars=bars, listed_strikes=listed,
    )
    by = {c.field: c for c in checks}
    print("\n" + format_table(checks))

    assert by["index_ltp_at_open"].verdict == VERDICT_MATCH, (
        f"decoded {by['index_ltp_at_open'].observed} vs market {by['index_ltp_at_open'].external}")
    assert by["atm_strike"].verdict == VERDICT_MATCH
    assert summarise(checks)["contradicted"] is False


def test_contract_metadata_matches_the_real_instrument_master(lake):
    """Lot size 20 and tick 0.05 were *derived* in A231; here they are observed."""
    options = _sensex_options(lake)
    if not options:
        pytest.skip("lake holds no SENSEX option instrument rows")
    expiry = "2026-08-20"
    if not any(r["expiry"] == expiry for r in options):
        pytest.skip(f"{expiry} absent from the instrument master snapshot")

    checks = check_contract_metadata(
        observed_lot_size=20, observed_tick_size=0.05,
        expiry=expiry, strike=77500.0, instrument_rows=options,
    )
    by = {c.field: c for c in checks}
    print("\n" + format_table(checks))

    assert by["expiry_listed"].verdict == VERDICT_MATCH      # V1 traded a same-day expiry
    assert by["lot_size"].verdict == VERDICT_MATCH           # 20 -> PnL 469.0 = 23.45 x 20
    assert by["tick_size"].verdict == VERDICT_MATCH          # 0.05 -> 148.70 / 126.60 are valid
    assert by["strike_ladder_uniform"].verdict == VERDICT_MATCH
    assert by["strike_ladder_uniform"].external == 100
    assert by["strike_has_both_legs"].verdict == VERDICT_MATCH
    assert summarise(checks)["contradicted"] is False


def test_lake_has_no_option_bars_so_premiums_stay_unverified(lake):
    """Records the boundary of this cross-check, so nobody overstates it."""
    segments = {p.name for p in (lake / "bars" / "interval=minute").glob("exchange=*/segment=*")}
    assert not any("BFO" in s or "NFO" in s for s in segments), (
        "option bars appeared in the lake — the premium cross-check is now possible "
        "and A275 must be updated"
    )
    assert not list((lake / "ticks").rglob("*.parquet")), (
        "tick files appeared — asynchronous leg behaviour is now checkable"
    )
