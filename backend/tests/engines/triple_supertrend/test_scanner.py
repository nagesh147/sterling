from datetime import date

import numpy as np
import pytest

from app.domain.models import Candle
from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.engine import TripleSupertrendEngine
from app.engines.triple_supertrend.regime import compute_regime, entry_transitions
from app.services.kite_engine.scanner import (
    KiteEngineScanner, attach_strikes, drop_forming, evaluate_derivative_contract,
    evaluate_item, option_order_args,
)
from app.services.kite_engine.strikes import OptionPick
from app.services.kite_engine.universe import UniverseItem


def _candles(close_path, start_ms=0):
    c = np.asarray(close_path, dtype=float)
    o = np.concatenate([[c[0]], c[:-1]])
    out = []
    for i in range(len(c)):
        hi = max(o[i], c[i]) + 1.0
        lo = min(o[i], c[i]) - 1.0
        out.append(Candle(timestamp_ms=start_ms + i * 3_600_000, open=float(o[i]),
                          high=float(hi), low=float(lo), close=float(c[i]), volume=1.0))
    return out


def _fresh_long_path():
    return list(np.linspace(300, 150, 60)) + list(np.linspace(150, 600, 80))


def _fresh_short_path():
    return list(np.linspace(150, 600, 60)) + list(np.linspace(600, 150, 80))


def _trim_to_transition(candles, cfg, side="long"):
    o = np.array([c.open for c in candles], float)
    h = np.array([c.high for c in candles], float)
    l = np.array([c.low for c in candles], float)
    c = np.array([c.close for c in candles], float)
    r = compute_regime(o, h, l, c, cfg)
    longs, shorts = entry_transitions(r)
    flags = longs if side == "long" else shorts
    idx = int(np.where(flags)[0][0])
    return candles[: idx + 1]


def test_drop_forming_removes_open_bar():
    candles = _candles([1, 2, 3])  # last ts = 2h
    # "now" only 30 min past the last bar's open → bar still forming
    assert len(drop_forming(candles, now_ms=2 * 3_600_000 + 1_800_000)) == 2
    # well past close → keep it
    assert len(drop_forming(candles, now_ms=10 * 3_600_000)) == 3


def test_evaluate_item_emits_row_on_fresh_transition():
    cfg = TripleSupertrendConfig()
    eng = TripleSupertrendEngine(cfg)
    item = UniverseItem("RELIANCE", "RELIANCE", 111, "NSE", "NFO")
    candles = _trim_to_transition(_candles(_fresh_long_path()), cfg)
    rows = evaluate_item(eng, item, candles, cfg)
    assert rows  # all transitions in the window; the latest bar is the fresh long
    row = rows[-1]
    assert row.regime == "BULL" and row.option_type == "CE" and row.direction == "long"
    assert row.token == 111 and row.exchange == "NFO" and row.stop_loss > 0


def test_attach_strike_uses_option_name_for_indices():
    cfg = TripleSupertrendConfig()
    eng = TripleSupertrendEngine(cfg)
    nifty = UniverseItem("NIFTY 50", "NIFTY", 256265, "INDICES", "NFO", is_index=True)
    candles = _trim_to_transition(_candles(_fresh_long_path()), cfg)
    rows = evaluate_item(eng, nifty, candles, cfg)
    assert rows
    row = rows[-1]
    spot = row.spot
    base = int(round(spot / 50) * 50)
    dump = [
        {"name": "NIFTY", "tradingsymbol": f"NIFTY25JUN{base}CE", "instrument_type": "CE",
         "strike": base, "expiry": "2026-06-26"},
        {"name": "NIFTY", "tradingsymbol": f"NIFTY25JUN{base}PE", "instrument_type": "PE",
         "strike": base, "expiry": "2026-06-26"},
    ]
    attach_strikes(row, dump, option_name="NIFTY", moneynesses=["ATM"], today=date(2026, 6, 13))
    assert len(row.legs) == 1
    assert row.legs[0].option_symbol == f"NIFTY25JUN{base}CE" and row.legs[0].strike == base


def test_attach_strikes_multi_moneyness_legs():
    cfg = TripleSupertrendConfig()
    eng = TripleSupertrendEngine(cfg)
    item = UniverseItem("ACME", "ACME", 1, "NSE", "NFO")
    candles = _trim_to_transition(_candles(_fresh_long_path()), cfg)
    rows = evaluate_item(eng, item, candles, cfg)
    assert rows
    row = rows[-1]
    spot = row.spot
    base = int(round(spot / 50) * 50)
    dump = [
        {"name": "ACME", "tradingsymbol": f"ACME{base}CE", "instrument_type": "CE",
         "strike": base, "expiry": "2099-01-01", "lot_size": 50},
        {"name": "ACME", "tradingsymbol": f"ACME{base-50}CE", "instrument_type": "CE",
         "strike": base - 50, "expiry": "2099-01-01", "lot_size": 50},
        {"name": "ACME", "tradingsymbol": f"ACME{base-100}CE", "instrument_type": "CE",
         "strike": base - 100, "expiry": "2099-01-01", "lot_size": 50},
    ]
    attach_strikes(row, dump, option_name="ACME", moneynesses=["ATM", "ITM1", "ITM2"],
                   today=date(2026, 6, 13))
    assert [leg.moneyness for leg in row.legs] == ["ATM", "ITM1", "ITM2"]
    assert [leg.strike for leg in row.legs] == [base, base - 50, base - 100]


def test_attach_strikes_otm_legs_and_canonical_order():
    """ITM + ATM + OTM together, resolved in a fixed canonical order (ATM first)
    regardless of the order they were requested in (the UI can scramble it)."""
    cfg = TripleSupertrendConfig()
    eng = TripleSupertrendEngine(cfg)
    item = UniverseItem("ACME", "ACME", 1, "NSE", "NFO")
    candles = _trim_to_transition(_candles(_fresh_long_path()), cfg)
    rows = evaluate_item(eng, item, candles, cfg)
    assert rows
    row = rows[-1]
    spot = row.spot
    base = int(round(spot / 50) * 50)
    dump = [
        {"name": "ACME", "tradingsymbol": f"ACME{s}CE", "instrument_type": "CE",
         "strike": s, "expiry": "2099-01-01", "lot_size": 50}
        for s in (base - 100, base - 50, base, base + 50, base + 100)
    ]
    # requested deliberately out of order
    attach_strikes(row, dump, option_name="ACME",
                   moneynesses=["OTM2", "ATM", "ITM2", "OTM1", "ITM1"], today=date(2026, 6, 13))
    assert [leg.moneyness for leg in row.legs] == ["ATM", "ITM1", "ITM2", "OTM1", "OTM2"]
    # CALL: ITM steps below spot, OTM steps above
    assert [leg.strike for leg in row.legs] == [base, base - 50, base - 100, base + 50, base + 100]


def test_option_order_args_auto_exec_picks_nearest_to_spot_leg():
    """Auto-exec must buy the at-the-money (nearest-spot) contract, never a deep
    OTM lottery — even if an OTM leg happens to be first in the list."""
    from app.engines.triple_supertrend.schemas import AlignmentChip, EngineSignalRow, OptionLeg

    row = EngineSignalRow(
        underlying="NIFTY 50", token=256265, exchange="NFO", regime="BULL",
        alignment=AlignmentChip(fast=1, mid=1, slow=1), direction="long", option_type="CE",
        legs=[
            OptionLeg(moneyness="OTM2", option_type="CE", option_symbol="N22200CE",
                      strike=22200.0, expiry="2026-06-26", lot_size=75),
            OptionLeg(moneyness="ATM", option_type="CE", option_symbol="N22000CE",
                      strike=22000.0, expiry="2026-06-26", lot_size=75),
            OptionLeg(moneyness="ITM1", option_type="CE", option_symbol="N21900CE",
                      strike=21900.0, expiry="2026-06-26", lot_size=75),
        ],
        spot=22010.0, stop_loss=21900.0, score=85.0, timestamp_ms=123,
    )
    assert option_order_args(row)["option_symbol"] == "N22000CE"  # nearest to spot 22010


@pytest.mark.asyncio
async def test_scan_end_to_end_with_fake_client():
    class FakeClient:
        async def get_candles(self, inst, resolution, limit):
            # one item fires (fresh transition), the other is flat noise
            if inst.zerodha_token == 1:
                return _trim_to_transition(_candles(_fresh_long_path()),
                                           TripleSupertrendConfig())
            return _candles(list(np.linspace(100, 101, 30)))

    base = 400  # rough ATM for the fired item (rises to ~600 region trimmed earlier)
    nfo = [
        {"name": "ACME", "tradingsymbol": "ACME25JUN300CE", "instrument_type": "CE",
         "strike": 300, "expiry": "2099-01-01"},
        {"name": "ACME", "tradingsymbol": "ACME25JUN300PE", "instrument_type": "PE",
         "strike": 300, "expiry": "2099-01-01"},
    ]
    universe = [
        UniverseItem("ACME", "ACME", 1, "NSE", "NFO"),
        UniverseItem("DULL", "DULL", 2, "NSE", "NFO"),
    ]
    sc = KiteEngineScanner()
    # candles are far in the past, so drop_forming keeps the last bar
    await sc.scan(uid="u1", client=FakeClient(), universe=universe, nfo_rows=nfo,
                  bfo_rows=[], cfg=TripleSupertrendConfig(), moneyness=["ATM"])
    snap = sc.snapshot("u1")
    assert not snap.scanning and snap.generated_ms > 0
    # only the firing item appears (DULL is flat); evaluate_item now returns all
    # transitions in the window, so there may be >1 ACME row (e.g. a short then the long)
    assert {r.underlying for r in snap.rows} == {"ACME"}
    fresh = max(snap.rows, key=lambda r: r.timestamp_ms)  # latest bar = the fresh long/CE
    assert fresh.option_type == "CE" and fresh.legs[0].option_symbol == "ACME25JUN300CE"


def test_evaluate_derivative_contract_emits_buy_on_premium_uptrend():
    cfg = TripleSupertrendConfig()
    item = UniverseItem("NIFTY 50", "NIFTY", 256265, "INDICES", "NFO", is_index=True)
    pick = OptionPick(option_symbol="NIFTY25JUN24500CE", strike=24500.0, option_type="CE",
                      expiry="2026-06-26", dte=8, lot_size=75, token=44001)
    candles = _trim_to_transition(_candles(_fresh_long_path()), cfg, "long")  # premium uptrend
    rows = evaluate_derivative_contract(item, "ATM", pick, candles, cfg)
    assert rows
    row = rows[-1]  # latest-bar BUY entry
    assert row.source == "derivatives"
    assert row.option_type == "CE" and row.regime == "BULL" and row.direction == "long"
    assert row.token == 44001  # the option's OWN token (click → option premium chart)
    assert row.legs and row.legs[0].option_symbol == "NIFTY25JUN24500CE"
    assert row.legs[0].moneyness == "ATM" and row.legs[0].lot_size == 75
    assert row.spot == candles[-1].close  # headline price = option premium last close
    assert row.stop_loss > 0  # premium-based SuperTrend trail


def test_evaluate_derivative_contract_pe_is_bearish():
    cfg = TripleSupertrendConfig()
    item = UniverseItem("BANKNIFTY", "BANKNIFTY", 260105, "INDICES", "NFO", is_index=True)
    pick = OptionPick(option_symbol="BANKNIFTY25JUN54000PE", strike=54000.0, option_type="PE",
                      expiry="2026-06-26", dte=8, lot_size=15, token=55001)
    candles = _trim_to_transition(_candles(_fresh_long_path()), cfg, "long")  # PE premium rising
    rows = evaluate_derivative_contract(item, "ATM", pick, candles, cfg)
    assert rows
    row = rows[-1]
    assert row.option_type == "PE" and row.regime == "BEAR" and row.direction == "long"


def test_evaluate_derivative_contract_buy_only_skips_premium_downtrend():
    cfg = TripleSupertrendConfig()
    item = UniverseItem("NIFTY 50", "NIFTY", 256265, "INDICES", "NFO", is_index=True)
    pick = OptionPick(option_symbol="NIFTY25JUN24500CE", strike=24500.0, option_type="CE",
                      expiry="2026-06-26", dte=8, lot_size=75, token=44001)
    # a premium that ONLY falls has no uptrend transition → no BUY ever (buy-only)
    candles = _candles(list(np.linspace(600, 150, 140)))
    assert evaluate_derivative_contract(item, "ATM", pick, candles, cfg) == []


def test_engine_config_default_offers_itm_and_otm():
    from app.engines.triple_supertrend.schemas import EngineConfigModel
    cfg = EngineConfigModel()
    assert cfg.strike_moneyness == ["ITM1", "ATM", "OTM1"]


def test_engine_config_scan_source_and_universe_defaults():
    from app.engines.triple_supertrend.schemas import EngineConfigModel
    c = EngineConfigModel()
    assert c.scan_source == "derivatives"   # default engine mode
    assert c.scan_all_stocks is False       # indices/curated only by default
    assert "NIFTY 50" in c.scan_indices and len(c.scan_indices) == 4
    c2 = EngineConfigModel(scan_source="both", scan_all_stocks=False,
                           scan_indices=["NIFTY 50"], scan_stocks=["RELIANCE"])
    assert c2.scan_indices == ["NIFTY 50"] and c2.scan_stocks == ["RELIANCE"]


def test_engine_config_accepts_otm_only_selection():
    from app.engines.triple_supertrend.schemas import EngineConfigModel
    cfg = EngineConfigModel(strike_moneyness=["OTM1", "OTM2"])
    assert cfg.strike_moneyness == ["OTM1", "OTM2"]
    # empty falls back to the default set (validator)
    assert EngineConfigModel(strike_moneyness=[]).strike_moneyness == ["ITM1", "ATM", "OTM1"]


def test_option_order_args_maps_buy_one_lot():
    from app.engines.triple_supertrend.schemas import AlignmentChip, EngineSignalRow, OptionLeg

    row = EngineSignalRow(
        underlying="NIFTY 50", token=256265, exchange="NFO", regime="BULL",
        alignment=AlignmentChip(fast=1, mid=1, slow=1), direction="long", option_type="CE",
        legs=[OptionLeg(moneyness="ATM", option_type="CE", option_symbol="NIFTY25JUN22000CE",
                        strike=22000.0, expiry="2026-06-26", lot_size=75)],
        spot=22010.0, stop_loss=21900.0, score=85.0, timestamp_ms=123,
    )
    args = option_order_args(row)  # primary leg
    assert args == {
        "option_symbol": "NIFTY25JUN22000CE", "side": "buy", "size": 75,
        "exchange": "NFO", "stop_loss": 21900.0,
    }
    # a put (bear) is still a BUY — this is an options-buying engine
    row.direction = "short"; row.option_type = "PE"
    assert option_order_args(row)["side"] == "buy"
    # no legs → no order
    row.legs = []
    assert option_order_args(row) is None


@pytest.mark.asyncio
async def test_scan_records_index_diagnostics():
    """The scan exposes a per-run breakdown so a silently-empty index candle fetch
    is visible (this is the 'no index signals' diagnostic)."""
    class FakeClient:
        async def get_candles(self, inst, resolution, limit):
            if inst.zerodha_token in (1, 10):  # a stock + an index fire
                return _trim_to_transition(_candles(_fresh_long_path()), TripleSupertrendConfig())
            if inst.zerodha_token == 11:        # an index whose fetch comes back empty
                return []
            return _candles(list(np.linspace(100, 101, 30)))  # token 2: data, no transition

    universe = [
        UniverseItem("ACME", "ACME", 1, "NSE", "NFO"),
        UniverseItem("DULL", "DULL", 2, "NSE", "NFO"),
        UniverseItem("NIFTY 50", "NIFTY", 10, "INDICES", "NFO", is_index=True),
        UniverseItem("SENSEX", "SENSEX", 11, "INDICES", "BFO", is_index=True),
    ]
    sc = KiteEngineScanner()
    await sc.scan(uid="u1", client=FakeClient(), universe=universe, nfo_rows=[],
                  bfo_rows=[], cfg=TripleSupertrendConfig(), moneyness=["ATM"])
    d = sc.snapshot("u1").diag
    assert d.universe == 4 and d.indices == 2
    assert d.evaluated == 3 and d.no_data == 1      # token 11 returned nothing
    assert d.index_evaluated == 1 and d.index_no_data == 1 and d.index_fired == 1


@pytest.mark.asyncio
async def test_scan_derivatives_charts_both_sides_and_emits_buy_rows():
    """Derivatives mode charts BOTH the CE and PE of each selected strike (on the
    contract's own premium series) and emits a BUY row only when the premium fires."""
    fired = _trim_to_transition(_candles(_fresh_long_path()), TripleSupertrendConfig(), "long")
    flat = _candles(list(np.linspace(100, 101, 40)))

    class FakeClient:
        async def get_candles(self, inst, resolution, limit):
            t = inst.zerodha_token
            if t == 100:    # underlying spot anchor → last close 100 (no transition needed)
                return _candles([100.0] * 40)
            if t == 7001:   # ATM CE premium → fresh uptrend → BUY
                return fired
            return flat     # 7002 ATM PE → has data, no transition → no signal

    nfo = [
        {"name": "NIFTY", "tradingsymbol": "NIFTY25JUN100CE", "instrument_type": "CE",
         "strike": 100, "expiry": "2099-01-01", "instrument_token": 7001, "lot_size": 75},
        {"name": "NIFTY", "tradingsymbol": "NIFTY25JUN100PE", "instrument_type": "PE",
         "strike": 100, "expiry": "2099-01-01", "instrument_token": 7002, "lot_size": 75},
    ]
    deriv = [UniverseItem("NIFTY 50", "NIFTY", 100, "INDICES", "NFO", is_index=True)]
    sc = KiteEngineScanner()
    await sc.scan(uid="u1", client=FakeClient(), universe=[], nfo_rows=nfo, bfo_rows=[],
                  cfg=TripleSupertrendConfig(), moneyness=["ATM"], deriv_universe=deriv)
    snap = sc.snapshot("u1")
    assert len(snap.rows) == 1
    row = snap.rows[0]
    assert row.source == "derivatives" and row.option_type == "CE"
    assert row.token == 7001 and row.legs[0].option_symbol == "NIFTY25JUN100CE"
    d = snap.diag
    assert d.deriv_charts == 2 and d.deriv_fired == 1 and d.deriv_no_data == 0
    assert d.deriv_resolved == 2            # both contracts resolved from the chain
    assert d.deriv_max_bars >= d.deriv_min_bars > 0  # premium history depth recorded


@pytest.mark.asyncio
async def test_scan_derivatives_does_not_skip_short_weeklies():
    """A short-dated contract is still CHARTED (not skipped); it just can't fire a
    21-period SuperTrend yet, so it produces no signal — never a fabricated one."""
    short = _candles([100.0] * 12)  # 12 bars < warmup(21): scanned, but no signal possible

    class FakeClient:
        async def get_candles(self, inst, resolution, limit):
            if inst.zerodha_token == 100:
                return _candles([100.0] * 40)  # underlying spot anchor
            return short  # both CE & PE are young weeklies

    nfo = [
        {"name": "NIFTY", "tradingsymbol": "NIFTY25JUN100CE", "instrument_type": "CE",
         "strike": 100, "expiry": "2099-01-01", "instrument_token": 7001, "lot_size": 75},
        {"name": "NIFTY", "tradingsymbol": "NIFTY25JUN100PE", "instrument_type": "PE",
         "strike": 100, "expiry": "2099-01-01", "instrument_token": 7002, "lot_size": 75},
    ]
    deriv = [UniverseItem("NIFTY 50", "NIFTY", 100, "INDICES", "NFO", is_index=True)]
    sc = KiteEngineScanner()
    await sc.scan(uid="u1", client=FakeClient(), universe=[], nfo_rows=nfo, bfo_rows=[],
                  cfg=TripleSupertrendConfig(), moneyness=["ATM"], deriv_universe=deriv)
    snap = sc.snapshot("u1")
    d = snap.diag
    assert d.deriv_charts == 2      # both young weeklies were charted (not skipped)
    assert d.deriv_no_data == 0     # present-but-short ≠ no-data
    assert d.deriv_fired == 0 and snap.rows == []  # no fabricated signal


@pytest.mark.asyncio
async def test_scan_derivatives_invokes_place_cb_for_auto_exec():
    """Auto-exec is universal: a fired derivative contract goes through place_cb too."""
    fired = _trim_to_transition(_candles(_fresh_long_path()), TripleSupertrendConfig(), "long")

    class FakeClient:
        async def get_candles(self, inst, resolution, limit):
            if inst.zerodha_token == 100:
                return _candles([100.0] * 40)
            if inst.zerodha_token == 7001:
                return fired
            return _candles(list(np.linspace(100, 101, 40)))

    nfo = [
        {"name": "NIFTY", "tradingsymbol": "NIFTY25JUN100CE", "instrument_type": "CE",
         "strike": 100, "expiry": "2099-01-01", "instrument_token": 7001, "lot_size": 75},
        {"name": "NIFTY", "tradingsymbol": "NIFTY25JUN100PE", "instrument_type": "PE",
         "strike": 100, "expiry": "2099-01-01", "instrument_token": 7002, "lot_size": 75},
    ]
    deriv = [UniverseItem("NIFTY 50", "NIFTY", 100, "INDICES", "NFO", is_index=True)]
    calls = []

    async def cb(row, item):
        calls.append((row.source, row.legs[0].option_symbol, row.legs[0].lot_size))

    sc = KiteEngineScanner()
    await sc.scan(uid="u1", client=FakeClient(), universe=[], nfo_rows=nfo, bfo_rows=[],
                  cfg=TripleSupertrendConfig(), moneyness=["ATM"], deriv_universe=deriv, place_cb=cb)
    assert calls == [("derivatives", "NIFTY25JUN100CE", 75)]


@pytest.mark.asyncio
async def test_deriv_index_spot_fallback_quotes_by_display_name():
    """When an index's 1H candle fetch comes back empty, the deriv scan resolves the
    spot from a QUOTE keyed by the DISPLAY name ("NSE:NIFTY 50"), not the option name
    ("NSE:NIFTY") which is not a valid quote symbol. Proves the chain still scans."""
    fired = _trim_to_transition(_candles(_fresh_long_path()), TripleSupertrendConfig(), "long")
    quoted = {}

    class FakeClient:
        async def get_candles(self, inst, resolution, limit):
            if inst.zerodha_token == 256265:  # the index underlying → EMPTY (silent drop)
                return []
            if inst.zerodha_token == 7001:     # ATM CE premium → fires
                return fired
            return _candles(list(np.linspace(100, 101, 40)))

        async def get_quote(self, syms):
            quoted['syms'] = list(syms)
            # Only the DISPLAY-name symbol resolves; the option-name symbol would 404.
            return {"NSE:NIFTY 50": {"last_price": 24510.0}}

    nfo = [
        {"name": "NIFTY", "tradingsymbol": "NIFTY25JUN24500CE", "instrument_type": "CE",
         "strike": 24500, "expiry": "2099-01-01", "instrument_token": 7001, "lot_size": 75},
        {"name": "NIFTY", "tradingsymbol": "NIFTY25JUN24500PE", "instrument_type": "PE",
         "strike": 24500, "expiry": "2099-01-01", "instrument_token": 7002, "lot_size": 75},
    ]
    deriv = [UniverseItem("NIFTY 50", "NIFTY", 256265, "INDICES", "NFO", is_index=True)]
    sc = KiteEngineScanner()
    await sc.scan(uid="u1", client=FakeClient(), universe=[], nfo_rows=nfo, bfo_rows=[],
                  cfg=TripleSupertrendConfig(), moneyness=["ATM"], deriv_universe=deriv)
    assert quoted['syms'] == ["NSE:NIFTY 50"]          # display name, not "NSE:NIFTY"
    snap = sc.snapshot("u1")
    assert snap.diag.deriv_no_spot == 0                # spot WAS resolved via the quote
    assert len(snap.rows) == 1 and snap.rows[0].option_type == "CE"


@pytest.mark.asyncio
async def test_deriv_unresolved_spot_is_visible_not_silent():
    """If BOTH the candle fetch and the quote come back empty, the underlying is
    skipped — but it's COUNTED (deriv_no_spot), never a silent drop."""
    class FakeClient:
        async def get_candles(self, inst, resolution, limit):
            return []  # everything empty

        async def get_quote(self, syms):
            return {}  # quote also empty

    deriv = [UniverseItem("SENSEX", "SENSEX", 265, "INDICES", "BFO", is_index=True)]
    logs = []
    sc = KiteEngineScanner()
    await sc.scan(uid="u1", client=FakeClient(), universe=[], nfo_rows=[], bfo_rows=[],
                  cfg=TripleSupertrendConfig(), moneyness=["ATM"], deriv_universe=deriv,
                  log_cb=lambda m: logs.append(m))
    d = sc.snapshot("u1").diag
    assert d.deriv_no_spot == 1 and d.deriv_resolved == 0
    assert any("spot unavailable" in m for m in logs)


def test_derivative_signal_marks_active_when_trend_intact_vs_stale():
    """A signal whose premium SuperTrend is still aligned on the latest bar is
    is_active=True (running); once the premium reverses and the trend breaks it goes
    is_active=False (stale entry, kept only for history). This is the fix for "I see a
    big move on the chart but the engine shows nothing today" — the entry was days ago
    and the trend has since ended."""
    cfg = TripleSupertrendConfig()
    item = UniverseItem("SENSEX", "SENSEX", 265, "INDICES", "BFO", is_index=True)
    pick = OptionPick(option_symbol="SENSEX2561876000CE", strike=76000.0, option_type="CE",
                      expiry="2026-06-18", dte=3, lot_size=20, token=999001)

    # still rising on the last bar → active
    rising = _candles(_fresh_long_path())
    rows = evaluate_derivative_contract(item, "ATM", pick, rising, cfg)
    assert rows and rows[-1].is_active is True and rows[-1].legs[0].is_active is True

    # entered (proven firing path), then reversed hard so the trend breaks before the
    # last bar → the entry still exists but is no longer running
    reversed_ = _candles(_fresh_long_path() + list(np.linspace(600, 150, 40)))
    rows2 = evaluate_derivative_contract(item, "ATM", pick, reversed_, cfg)
    assert rows2 and rows2[0].is_active is False
    assert rows2[0].legs[0].is_active is False


@pytest.mark.asyncio
async def test_deriv_grouping_dedupes_legs_for_repeated_transitions():
    """A contract that fires more than once over its premium history yields ONE leg
    (the most recent), not a duplicate strike chip per transition."""
    cfg = TripleSupertrendConfig()
    # premium that transitions up TWICE (up, down, up again) → 2 long transitions
    twice = (list(np.linspace(300, 150, 50)) + list(np.linspace(150, 600, 40))
             + list(np.linspace(600, 200, 40)) + list(np.linspace(200, 700, 40)))

    class FakeClient:
        async def get_candles(self, inst, resolution, limit):
            if inst.zerodha_token == 100:
                return _candles([100.0] * 40)       # underlying anchor
            if inst.zerodha_token == 7001:
                return _candles(twice)               # ATM CE fires twice
            return _candles(list(np.linspace(100, 101, 40)))  # PE flat

    nfo = [
        {"name": "NIFTY", "tradingsymbol": "NIFTY25JUN100CE", "instrument_type": "CE",
         "strike": 100, "expiry": "2099-01-01", "instrument_token": 7001, "lot_size": 75},
        {"name": "NIFTY", "tradingsymbol": "NIFTY25JUN100PE", "instrument_type": "PE",
         "strike": 100, "expiry": "2099-01-01", "instrument_token": 7002, "lot_size": 75},
    ]
    deriv = [UniverseItem("NIFTY 50", "NIFTY", 100, "INDICES", "NFO", is_index=True)]
    sc = KiteEngineScanner()
    await sc.scan(uid="u1", client=FakeClient(), universe=[], nfo_rows=nfo, bfo_rows=[],
                  cfg=cfg, moneyness=["ATM"], deriv_universe=deriv)
    rows = sc.snapshot("u1").rows
    assert len(rows) == 1
    syms = [l.option_symbol for l in rows[0].legs]
    assert syms == ["NIFTY25JUN100CE"]              # ONE leg, not duplicated per transition


@pytest.mark.asyncio
async def test_scan_invokes_place_cb_for_ready_rows():
    class FakeClient:
        async def get_candles(self, inst, resolution, limit):
            if inst.zerodha_token == 1:
                return _trim_to_transition(_candles(_fresh_long_path()), TripleSupertrendConfig())
            return _candles(list(np.linspace(100, 101, 30)))

    nfo = [
        {"name": "ACME", "tradingsymbol": "ACME25JUN300CE", "instrument_type": "CE",
         "strike": 300, "expiry": "2099-01-01", "lot_size": 50},
        {"name": "ACME", "tradingsymbol": "ACME25JUN300PE", "instrument_type": "PE",
         "strike": 300, "expiry": "2099-01-01", "lot_size": 50},
    ]
    universe = [
        UniverseItem("ACME", "ACME", 1, "NSE", "NFO"),
        UniverseItem("DULL", "DULL", 2, "NSE", "NFO"),
    ]
    calls = []

    async def cb(row, item):
        leg = row.legs[0]
        calls.append((row.underlying, leg.option_symbol, leg.lot_size))

    sc = KiteEngineScanner()
    await sc.scan(uid="u1", client=FakeClient(), universe=universe, nfo_rows=nfo,
                  bfo_rows=[], cfg=TripleSupertrendConfig(), moneyness=["ATM"], place_cb=cb)
    assert calls == [("ACME", "ACME25JUN300CE", 50)]
