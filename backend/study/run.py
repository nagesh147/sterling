"""Study orchestrator — runs the full derivatives edge study pipeline.

Coordinates 8 stages: data load → surface capture → grid build →
futures sim → options sim → robustness gate → gate audit → report.

Runs CPU-bound work in asyncio.to_thread() so the server event loop
stays responsive. Progress is tracked in-memory via StudyRunState.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

# ── Pydantic schemas for API ──────────────────────────────────────────

class StudyRunRequest(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: ["BTCUSD", "ETHUSD", "SOLUSD"])
    timeframes: list[str] = Field(default_factory=lambda: ["15m", "30m", "1h", "2h", "4h"])
    validation_method: int = 1  # 1=calibrate-live, 2=real-only, 3=snapshot


@dataclass
class StudyRunState:
    run_id: str
    status: str = "starting"        # starting | running | complete | failed
    progress_pct: float = 0.0        # 0-100
    current_stage: str = ""          # human-readable
    started_at: float = field(default_factory=time.time)
    elapsed_seconds: float = 0.0
    error: Optional[str] = None
    output_dir: str = ""
    n_configs: int = 0
    n_survivors: int = 0


# ── Orchestrator ──────────────────────────────────────────────────────

class StudyRunner:
    """Orchestrate the 8-stage study pipeline.

    Usage:
        runner = StudyRunner(app=None)
        state = runner.init_run(request)
        await runner.run(state)
    """

    def __init__(self, app=None, data_dir: str = ".", output_dir: str = "."):
        self._app = app
        self._data_dir = data_dir
        self._output_dir = output_dir
        self._state: Optional[StudyRunState] = None

    @property
    def state(self) -> Optional[StudyRunState]:
        return self._state

    @property
    def runs(self) -> dict[str, StudyRunState]:
        """Read app.state.study_runs if available."""
        if self._app and hasattr(self._app.state, "study_runs"):
            return self._app.state.study_runs
        return {}

    def _progress(self, pct: float, stage: str):
        if self._state:
            self._state.progress_pct = round(pct, 1)
            self._state.current_stage = stage
            self._state.elapsed_seconds = round(time.time() - self._state.started_at, 1)

    def init_run(self, request: StudyRunRequest) -> StudyRunState:
        run_id = str(uuid.uuid4())[:8]
        self._state = StudyRunState(run_id=run_id, progress_pct=0.0)
        if self._app is not None:
            if not hasattr(self._app.state, "study_runs"):
                self._app.state.study_runs = {}
            self._app.state.study_runs[run_id] = self._state
        return self._state

    async def run(self, request: StudyRunRequest) -> StudyRunState:
        """Main entry point. Runs all 8 stages sequentially."""
        state = self._state or self.init_run(request)
        state.status = "running"

        # Method 3 (live-snapshot characterization): capture & describe the
        # live surface only — no grid, no simulation, no gate.
        if request.validation_method == 3:
            return await self._run_characterization(request, state)

        # Convert TF strings to (rule, label) tuples
        tf_map = {
            "15m": ("15min", "15m"), "30m": ("30min", "30m"),
            "1h": ("1h", "1h"), "2h": ("2h", "2h"), "4h": ("4h", "4h"),
        }
        timeframes = [tf_map[t] for t in request.timeframes if t in tf_map]

        try:
            # ── Stage 0-1: Load data + surfaces (0-10%) ─────────────────
            self._progress(0, "Loading parquet data")
            data_cache = await asyncio.to_thread(
                _load_data, request.symbols, timeframes, self._data_dir)
            self._progress(5, "Data loaded")

            # Surface source depends on validation method:
            #   1 = calibrate-to-live  → capture a fresh live surface snapshot
            #   2 = real-only/forward  → reconstruct real surfaces from the
            #                            forward IV recorder's recorded history
            surfaces = {}
            forward_surfaces: dict[str, list] = {}
            if request.validation_method == 1:
                self._progress(5, "Capturing live option surfaces")
                surfaces = await _capture_surfaces(request.symbols, self._app)
                self._progress(10, "Surfaces captured")
            elif request.validation_method == 2:
                self._progress(5, "Loading forward IV history (recorder)")
                forward_surfaces = await asyncio.to_thread(
                    _load_forward_surfaces, request.symbols)
                # A representative real surface per symbol (latest capture) seeds
                # the grid + gate audit; the options sim replays the full series.
                surfaces = {
                    sym: (snaps[-1] if snaps else None)
                    for sym, snaps in forward_surfaces.items()
                }
                n_surf = sum(len(v) for v in forward_surfaces.values())
                self._progress(10, f"Forward IV: {n_surf} recorded surfaces")

            # ── Stage 2: Build grid (10-12%) ────────────────────────────
            self._progress(10, "Building Stage A grid")
            from study.grid import build_stage_a
            configs = await asyncio.to_thread(build_stage_a, request.symbols, surfaces)
            state.n_configs = len(configs)
            self._progress(12, f"Grid built: {len(configs)} configs")

            # ── Stage 3: Futures simulation (12-45%) ─────────────────────
            self._progress(12, "Running futures simulation")
            results = await asyncio.to_thread(
                _run_futures_sim, configs, data_cache, self._progress_update)
            self._progress(45, f"Futures simulation complete: {len(results)} results")

            # ── Stage 4: Options simulation (45-70%) ─────────────────────
            opt_configs = [c for c in configs if c.instrument in ("call", "put")]
            have_surface = any(s is not None for s in surfaces.values())
            if opt_configs and have_surface:
                self._progress(45, "Running options simulation")
                if request.validation_method == 2:
                    opt_results = await asyncio.to_thread(
                        _run_options_sim_real, opt_configs, data_cache,
                        forward_surfaces, self._progress_update)
                else:
                    opt_results = await asyncio.to_thread(
                        _run_options_sim, opt_configs, data_cache, surfaces,
                        self._progress_update)
                results.extend(opt_results)
            elif request.validation_method == 2:
                log.info("Method 2: no forward IV history yet — futures only "
                         "(recorder must accrue data before options can be priced)")
            self._progress(70, f"Total simulation complete: {len(results)} results")

            # ── Stage 5: Robustness gate (70-80%) ────────────────────────
            self._progress(70, "Running robustness gates")
            from study.robustness import robustness_gate
            survivors = []
            total = len(results)
            for idx, r in enumerate(results):
                if r.get("trades", 0) >= 50 and r["metrics"].get("net_return", 0) > 0:
                    rob = await asyncio.to_thread(robustness_gate, r.get("trades", []))
                    r["robustness"] = rob
                    if rob.get("survived"):
                        survivors.append(r)
                if idx % 100 == 0:
                    pct = 70 + min(10, int(10 * idx / max(1, total)))
                    self._progress(pct, f"Robustness: {idx}/{total}")
            state.n_survivors = len(survivors)
            self._progress(80, f"Robustness complete: {len(survivors)} survivors")

            # ── Stage 6: Gate audit (80-90%) ────────────────────────────
            self._progress(80, "Running gate audit")
            from study.gate_audit import replay_routing_gate
            surf_for_audit = None
            for s in surfaces.values():
                if s is not None:
                    surf_for_audit = s
                    break
            gate_df = await asyncio.to_thread(
                replay_routing_gate, survivors,
                ivr_range=(10, 90, 5),
                spread_pct=surf_for_audit.spread_median_pct if surf_for_audit else 0.013,
                snapshot=surf_for_audit,
            )
            self._progress(90, "Gate audit complete")

            # ── Stage 7: Report (90-100%) ───────────────────────────────
            self._progress(90, "Generating report")
            from study.report import generate_report

            results_df = pd.DataFrame(results)
            surv_df = pd.DataFrame(survivors)
            md_path = await asyncio.to_thread(
                generate_report, results_df, surv_df, gate_df, surfaces,
                self._output_dir, request.validation_method)
            state.output_dir = self._output_dir
            self._progress(100, f"Report generated: {md_path}")

            state.status = "complete"
            log.info("Study %s complete — %d survivors / %d configs",
                     state.run_id, len(survivors), len(configs))

        except Exception as exc:
            state.status = "failed"
            state.error = str(exc)
            log.exception("Study %s failed", state.run_id)

        state.elapsed_seconds = round(time.time() - state.started_at, 1)
        return state

    def _progress_update(self, pct: float, stage: str):
        """Callback for inner loops to update progress."""
        if self._state:
            self._state.progress_pct = round(pct, 1)
            self._state.current_stage = stage
            self._state.elapsed_seconds = round(time.time() - self._state.started_at, 1)

    async def _run_characterization(self, request: StudyRunRequest,
                                    state: StudyRunState) -> StudyRunState:
        """Validation method 3: capture the live surface and write a
        characterization report. No backtest is run."""
        try:
            self._progress(10, "Capturing live option surfaces")
            surfaces = await _capture_surfaces(request.symbols, self._app)
            self._progress(80, "Generating characterization report")
            from study.report import generate_characterization_report
            md_path = await asyncio.to_thread(
                generate_characterization_report, surfaces, self._output_dir)
            state.output_dir = self._output_dir
            n = sum(1 for s in surfaces.values() if s is not None)
            self._progress(100, f"Characterization complete: {n} surface(s) — {md_path}")
            state.status = "complete"
            log.info("Study %s characterization complete — %d surfaces", state.run_id, n)
        except Exception as exc:
            state.status = "failed"
            state.error = str(exc)
            log.exception("Study %s characterization failed", state.run_id)
        state.elapsed_seconds = round(time.time() - state.started_at, 1)
        return state


# ── Internal helpers (run in threads) ─────────────────────────────────

def _load_data(
    symbols: list[str],
    timeframes: list[tuple[str, str]],
    data_dir: str,
) -> dict:
    from study.data import prepare_data
    return prepare_data(symbols, timeframes, data_dir)


async def _capture_surfaces(
    symbols: list[str],
    app,
) -> dict[str, object]:
    """Capture live option chains for each symbol with options."""
    from study.surface_snapshot import capture_live, SurfaceSnapshot
    from app.services import adapter_manager
    from app.services.exchanges import instrument_registry

    surfaces = {}
    adapter = adapter_manager.get_adapter()
    if adapter is None:
        log.warning("No adapter available; skipping surface capture")
        return surfaces

    for sym in symbols:
        ul = sym.replace("USD", "")
        inst = instrument_registry.get_instrument(ul)
        if inst is None:
            continue
        # Check if this underlying has options
        if not instrument_registry.has_options(ul):
            surfaces[sym] = None
            continue
        try:
            snap = await capture_live(ul, adapter)
            if snap:
                snap.save_fixture()
            surfaces[sym] = snap
        except Exception:
            log.exception("Surface capture failed for %s", sym)
            surfaces[sym] = None

    return surfaces


def _run_futures_sim(
    configs: list,
    data_cache: dict,
    progress_cb=None,
) -> list[dict]:
    """Run futures simulation on all futures configs."""
    from study.futures_sim import simulate_futures_config, simulate_futures_trailing
    from study.sim import sharpe

    results = []
    futures_configs = [c for c in configs if c.instrument == "futures"]
    total = len(futures_configs)

    for idx, cfg in enumerate(futures_configs):
        key = (cfg.symbol, cfg.tf_label)
        df = data_cache.get(key)
        if df is None:
            continue

        from app.engines.edge.strategies import SIGNAL_FNS
        if cfg.strategy not in SIGNAL_FNS:
            continue
        signals = SIGNAL_FNS[cfg.strategy](df)

        # Choose simulation based on exit type
        if cfg.exit_type == "atr_trailing":
            sim = simulate_futures_trailing(
                df, signals, cfg.sl_mult, cfg.direction,
                fee_rt=0.001, max_hold=200,
            )
        else:
            sim = simulate_futures_config(
                df, signals, cfg.sl_mult, cfg.tp_mult,
                cfg.direction, fee_rt=0.001, max_hold=200,
            )

        row = {
            "config_id": cfg.id,
            "symbol": cfg.symbol,
            "tf": cfg.tf_label,
            "strategy": cfg.strategy,
            "profile": cfg.profile,
            "direction": cfg.direction,
            "instrument": cfg.instrument,
            "sl_mult": cfg.sl_mult,
            "tp_mult": cfg.tp_mult,
            "exit_type": cfg.exit_type,
            "trades": sim["metrics"]["trades"],
            **sim["metrics"],
            "trades_list": sim["trades"],
        }
        results.append(row)

        if progress_cb and idx % 200 == 0:
            pct = 12 + min(33, int(33 * idx / max(1, total)))
            progress_cb(pct, f"Futures: {idx}/{total} ({cfg.id})")

    return results


def _load_forward_surfaces(symbols: list[str]) -> dict[str, list]:
    """Reconstruct real historical surfaces from the forward IV recorder
    (`option_iv_ticks`). Keyed by study symbol (e.g. 'BTCUSD'). Empty lists
    when the recorder has no data yet."""
    from app.services import db
    from study.forward_surface import reconstruct_surfaces

    out: dict[str, list] = {}
    for sym in symbols:
        ul = sym.replace("USD", "")           # recorder stores 'BTC', not 'BTCUSD'
        ticks = db.get_option_iv_ticks(ul)
        out[sym] = reconstruct_surfaces(ticks, sym)
    return out


def _run_options_sim_real(
    configs: list,
    data_cache: dict,
    forward_surfaces: dict,
    progress_cb=None,
) -> list[dict]:
    """Options sim for method 2 (real-only/forward): price each trade through
    the REAL recorded surface, restricted to the forward window the recorder
    has actually covered (bars at/after the first recorded capture)."""
    from study.options_sim import build_iv_surface, simulate_option_config
    from study.forward_surface import earliest_capture_ts
    from app.engines.edge.strategies import SIGNAL_FNS

    results = []
    total = len(configs)
    for idx, cfg in enumerate(configs):
        df = data_cache.get((cfg.symbol, cfg.tf_label))
        if df is None:
            continue
        snaps = forward_surfaces.get(cfg.symbol) or []
        if not snaps:
            continue
        start_ts = earliest_capture_ts(snaps)
        cutoff = pd.to_datetime(start_ts, unit="s")
        df_fwd = df[df.index >= cutoff]
        if df_fwd.empty or len(df_fwd) < 60:
            # Not enough forward history covered yet → skip (futures-only).
            continue
        if cfg.strategy not in SIGNAL_FNS:
            continue
        signals = SIGNAL_FNS[cfg.strategy](df_fwd)

        iv_fn = build_iv_surface(snaps[-1])    # latest real recorded surface
        sim = simulate_option_config(
            df_fwd, signals, cfg.instrument,
            delta_target=cfg.delta_target or 0.30,
            dte_entry=cfg.dte or 30,
            iv_surface=iv_fn, chain_json=None,
            hold_bars=50, max_hold=200, fee_rt=0.001,
        )
        row = {
            "config_id": cfg.id, "symbol": cfg.symbol, "tf": cfg.tf_label,
            "strategy": cfg.strategy, "profile": cfg.profile,
            "direction": cfg.direction, "instrument": cfg.instrument,
            "delta_target": cfg.delta_target, "dte": cfg.dte,
            "exit_type": cfg.exit_type, "trades": sim["metrics"]["trades"],
            **sim["metrics"], "trades_list": sim["trades"],
            "note": "real recorded IV (forward window)",
        }
        results.append(row)

        if progress_cb and idx % 100 == 0:
            pct = 45 + min(25, int(25 * idx / max(1, total)))
            progress_cb(pct, f"Options(real): {idx}/{total}")

    return results


def _run_options_sim(
    configs: list,
    data_cache: dict,
    surfaces: dict,
    progress_cb=None,
) -> list[dict]:
    """Run options simulation on all options configs."""
    from study.options_sim import build_iv_surface, simulate_option_config

    # Build IV surfaces per symbol
    iv_surfaces = {}
    for sym, snap in surfaces.items():
        if snap is not None:
            iv_surfaces[sym] = build_iv_surface(snap)

    results = []
    total = len(configs)

    for idx, cfg in enumerate(configs):
        key = (cfg.symbol, cfg.tf_label)
        df = data_cache.get(key)
        if df is None:
            continue

        iv_fn = iv_surfaces.get(cfg.symbol)
        if iv_fn is None:
            continue

        from app.engines.edge.strategies import SIGNAL_FNS
        if cfg.strategy not in SIGNAL_FNS:
            continue
        signals = SIGNAL_FNS[cfg.strategy](df)

        snap = surfaces.get(cfg.symbol)
        chain_json = snap.chain_json if snap else None

        sim = simulate_option_config(
            df, signals, cfg.instrument,     # "call" or "put"
            delta_target=cfg.delta_target or 0.30,
            dte_entry=cfg.dte or 30,
            iv_surface=iv_fn,
            chain_json=chain_json,
            hold_bars=50, max_hold=200, fee_rt=0.001,
        )

        row = {
            "config_id": cfg.id,
            "symbol": cfg.symbol,
            "tf": cfg.tf_label,
            "strategy": cfg.strategy,
            "profile": cfg.profile,
            "direction": cfg.direction,
            "instrument": cfg.instrument,
            "delta_target": cfg.delta_target,
            "dte": cfg.dte,
            "exit_type": cfg.exit_type,
            "trades": sim["metrics"]["trades"],
            **sim["metrics"],
            "trades_list": sim["trades"],
            "note": cfg.note,
        }
        results.append(row)

        if progress_cb and idx % 100 == 0:
            pct = 45 + min(25, int(25 * idx / max(1, total)))
            progress_cb(pct, f"Options: {idx}/{total} ({cfg.id})")

    return results
