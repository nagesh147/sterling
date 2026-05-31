"""Strategy catalog — plain-English descriptors joined to live validated combos."""
from __future__ import annotations

import types

from app.engines.edge.catalog import build_catalog, DESCRIPTORS


def _combo(strategy, symbol, tf, profile, score, oos=5.0, ploss=0.2):
    return types.SimpleNamespace(
        strategy=strategy, symbol=symbol, tf=tf, profile=profile,
        trades=166, win_rate=0.43, net_return=0.95, sharpe=1.83, pf=1.29,
        oos_sharpe=oos, p_loss=ploss, max_dd=-0.27, signal_score=score,
    )


def _registry(combos):
    return types.SimpleNamespace(all=lambda: combos)


def test_every_strategy_has_descriptor():
    cat = build_catalog(_registry([]))
    ids = {e["id"] for e in cat}
    assert {"ma_crossover", "mean_reversion", "breakout", "price_action", "smc"} <= ids
    for e in cat:
        assert e["how_it_works"] and e["direction"] and e["tagline"]


def test_live_combos_attached_and_marked():
    reg = _registry([
        _combo("ma_crossover", "BTCUSD", "4h", "Intraday", 100, oos=10.5, ploss=0.11),
        _combo("smc", "ETHUSD", "4h", "Scalping", 70),
    ])
    cat = {e["id"]: e for e in build_catalog(reg)}
    ma = cat["ma_crossover"]
    assert ma["live"] is True and ma["live_combo_count"] == 1
    c = ma["combos"][0]
    assert c["symbol"] == "BTC" and c["tf"] == "4h" and c["profile"] == "Intraday"
    assert c["oos_sharpe"] == 10.5 and c["p_loss_pct"] == 11.0
    assert "ATR" in c["bracket"]
    # a strategy with no live combos is still listed, marked not-live
    assert cat["breakout"]["live"] is False and cat["breakout"]["combos"] == []


def test_live_strategies_sorted_first():
    reg = _registry([_combo("smc", "ETHUSD", "4h", "Scalping", 70)])
    cat = build_catalog(reg)
    assert cat[0]["id"] == "smc"          # the only live one ranks first
    assert all(not e["live"] for e in cat[1:])


def test_oos_sharpe_infinity_serialized_as_none():
    reg = _registry([_combo("smc", "ETHUSD", "4h", "Scalping", 70, oos=float("inf"))])
    cat = {e["id"]: e for e in build_catalog(reg)}
    assert cat["smc"]["combos"][0]["oos_sharpe"] is None


def test_disambiguation_notes_present():
    # the whole point: each id's note must disambiguate the dual-engine confusion
    for sid in ("ma_crossover", "mean_reversion", "breakout"):
        assert DESCRIPTORS[sid].note
