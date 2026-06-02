"""End-to-end tests for the study runner pipeline."""
import os
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

_ = os


def _make_ohlcv(n: int = 20000, base: float = 50000.0, seed: int = 42):
    """Deterministic synthetic 1m OHLCV DataFrame with DatetimeIndex."""
    np.random.seed(seed)
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0002, 0.015, n)
    close = base * np.cumprod(1.0 + returns)
    noise = np.abs(rng.normal(0, 50, n))
    high = close + noise
    low = close - noise
    open_ = low + (high - low) * rng.random(n)
    volume = rng.lognormal(8, 2, n)
    times = pd.date_range("2023-12-01", periods=n, freq="1min", tz="UTC")
    df = pd.DataFrame({
        "time": times, "open": open_, "high": high,
        "low": low, "close": close, "volume": volume,
    })
    return df


class TestStudyRunnerPipeline:
    def test_grid_builds(self):
        from study.grid import build_stage_a
        configs = build_stage_a(symbols=["BTCUSD"], surfaces={})
        assert len(configs) > 0
        futures = [c for c in configs if c.instrument == "futures"]
        assert len(futures) > 0

    def test_simulate_idx_returns_trades(self):
        from app.engines.edge.strategies import SIGNAL_FNS, resample
        from study.sim import simulate_idx

        df1 = _make_ohlcv(20000)
        df1 = df1.set_index("time").sort_index()
        df = resample(df1, "1h")
        sigs = SIGNAL_FNS["ma_crossover"](df)
        if not sigs.any():
            sigs[50] = True
            sigs[150] = True

        trades = simulate_idx(df, sigs, slm=2.0, tpm=3.5, direction="long")
        assert len(trades) > 0
        for t in trades:
            assert "pnl_pct" in t

    def test_futures_vs_options_simulation(self):
        from app.engines.edge.strategies import SIGNAL_FNS, resample
        from study.futures_sim import simulate_futures_config
        from study.options_sim import build_iv_surface, simulate_option_config
        from study.surface_snapshot import SurfaceSnapshot

        df1 = _make_ohlcv(20000)
        df1 = df1.set_index("time").sort_index()
        df = resample(df1, "1h")
        sigs = SIGNAL_FNS["ma_crossover"](df)
        if not sigs.any():
            sigs[50] = True
            sigs[150] = True

        fut = simulate_futures_config(df, sigs, sl_mult=2.0, tp_mult=3.5, direction="long")
        assert "metrics" in fut
        assert fut["metrics"]["trades"] > 0

        snap = SurfaceSnapshot(
            underlying="BTCUSD", spot=50000.0, timestamp_ms=0,
            snapshot_date="2026-01-01", atm_iv={30: 0.55, 60: 0.58},
            skew_25d=0.02, vrp=1.05, realized_vol_30d=0.52,
            spread_median_pct=0.013, regime_label="fair",
            regime_provisional=False, chain_json="[]",
        )
        iv_fn = build_iv_surface(snap)
        opt = simulate_option_config(
            df, sigs, option_type="call", delta_target=0.30,
            dte_entry=30, iv_surface=iv_fn, hold_bars=50,
        )
        assert "metrics" in opt

    def test_report_generates_files(self, tmp_path):
        from study.report import generate_report
        results = pd.DataFrame([{
            "config_id": "test/1", "symbol": "BTCUSD", "tf": "1h",
            "strategy": "ma_crossover", "direction": "long",
            "instrument": "futures", "trades": 100, "win_rate": 0.55,
            "pf": 1.5, "sharpe": 1.2, "oos_sharpe": 0.9,
            "oos_keep": 0.75, "P_loss%": 18, "net_return": 0.15,
            "ret%": 15, "exit_type": "fixed_tp",
        }])
        gate = pd.DataFrame([{
            "config_id": "test/1", "underlying": "BTC", "strategy": "ma_crossover",
            "tf": "1h", "direction": "long", "ivr_pct": 50,
            "verdict": "options", "reason": "OK",
        }])
        md_path = generate_report(results, results, gate, output_dir=str(tmp_path))
        assert os.path.exists(md_path)
        assert os.path.exists(os.path.join(str(tmp_path), "derivatives_study_results.csv"))

    def test_robustness_gate_survival(self):
        from study.robustness import robustness_gate
        rng = np.random.default_rng(42)
        pnls = rng.normal(0.003, 0.02, 200).tolist()
        trades = [{"pnl_pct": p, "entry_bar": i, "exit_bar": i + 10}
                  for i, p in enumerate(pnls)]
        result = robustness_gate(trades, min_trades=50)
        assert "survived" in result
        assert "oos_sharpe" in result
        assert "p_loss" in result

    def test_gate_audit_produces_dataframe(self):
        from study.gate_audit import replay_routing_gate
        survivors = [{
            "config_id": "test/1", "symbol": "BTCUSD",
            "strategy": "edge/ma_crossover", "tf": "4h",
            "direction": "long", "sharpe": 1.2,
        }]
        df = replay_routing_gate(survivors, ivr_range=(30, 50, 10))
        assert len(df) > 0
        assert "ivr_pct" in df.columns
        assert "verdict" in df.columns


class TestStudyProgressTracking:
    def test_init_run_state(self):
        from study.run import StudyRunner, StudyRunRequest
        req = StudyRunRequest(symbols=["BTCUSD"], timeframes=["1h"])
        runner = StudyRunner()
        state = runner.init_run(req)
        assert state.status == "starting"
        assert state.progress_pct == 0.0

    def test_progress_updates(self):
        from study.run import StudyRunner, StudyRunRequest
        req = StudyRunRequest()
        runner = StudyRunner()
        runner.init_run(req)
        runner._progress(42.5, "testing")
        assert runner.state.progress_pct == 42.5
        assert runner.state.current_stage == "testing"


class TestSurfaceSnapshotFixture:
    def test_save_load_roundtrip(self, tmp_path):
        from study.surface_snapshot import SurfaceSnapshot
        snap = SurfaceSnapshot(
            underlying="BTC", spot=50000.0, timestamp_ms=1234567890,
            snapshot_date="2026-06-02", atm_iv={7: 0.52, 14: 0.54, 30: 0.55},
            skew_25d=0.025, vrp=1.10, realized_vol_30d=0.50,
            spread_median_pct=0.015, regime_label="fair",
            regime_provisional=False, chain_json='[{"strike":50000}]',
        )
        path = os.path.join(str(tmp_path), "test_fixture.json")
        snap.save_fixture(path)
        loaded = SurfaceSnapshot.load_fixture(path)
        assert loaded.underlying == "BTC"
        assert loaded.spot == 50000.0
        assert loaded.atm_iv[30] == 0.55


class TestMultiLegExecution:
    def test_structure_detected_as_multi_leg(self):
        from app.engines.derivatives.schemas import (
            DerivativesCandidate, DerivativesStructure, StructureLeg,
        )
        struct = DerivativesStructure(
            structure_type="iron_condor", underlying="BTC", direction="neutral",
            legs=[
                StructureLeg(option_type="put", side="sell", strike=48000,
                            premium=200, ratio=1,
                            option_symbol="P-BTC-48000-020626"),
                StructureLeg(option_type="put", side="buy", strike=47000,
                            premium=100, ratio=1,
                            option_symbol="P-BTC-47000-020626"),
            ],
            contracts=1.0, defined=True, net_premium_usd=200.0,
            max_loss_usd=800.0, max_profit_usd=200.0, breakevens=[],
        )
        cand = DerivativesCandidate(
            rank=0, instrument_type="options", underlying="BTC",
            entry_price=50000.0, direction="neutral",
            contracts=1.0, leverage=1.0, notional_usd=50000.0,
            premium_usd=200.0, expected_r=0.25, score=1.0, structure=struct,
        )
        assert cand.structure is not None
        assert len(cand.structure.legs) == 2
        assert cand.structure.legs[0].option_symbol is not None
