"""
Issue 1 — baseline endpoint + persistence.
Issue 10 — CPCV endpoint.
Issue 13 — triple-barrier label endpoint.

These endpoints answer the TTACE Step 1+2 question: does the strategy clear
the deflated-Sharpe gate after honest costs, on the new opt-in payoff and
exit-ATR settings?
"""
from __future__ import annotations
import json
import sqlite3
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.engines.backtest.backtest_mtf import run_mtf_backtest, PROFILES
from app.engines.analytics.cpcv import CPCVConfig, run_cpcv
from app.engines.ml.labeling import (
    triple_barrier_labels, BarrierParams, label_distribution,
)
from app.services.funding import resolve_funding_8h_pct
from app.services.exchanges import instrument_registry as registry
from app.services import db as _db


router = APIRouter(prefix="/analytics", tags=["analytics_baseline"])


# ─── Schemas ─────────────────────────────────────────────────────────────


class BaselineRequest(BaseModel):
    underlying: str = "BTC"
    profile: str = "intraday_1h"
    lookback_days: int = Field(default=60, ge=14, le=365)
    funding_8h_pct: Optional[float] = None
    exit_atr_tf: str = Field(default="signal", description='"signal" or "regime"')
    payoff_mode: str = Field(default="chandelier_trail",
                             description='"fixed_2r" or "chandelier_trail"')


class CPCVRequest(BaseModel):
    underlying: str = "BTC"
    profile: str = "intraday_1h"
    lookback_days: int = Field(default=60, ge=14, le=365)
    n_groups: int = Field(default=6, ge=3, le=12)
    k_test: int = Field(default=2, ge=1, le=6)
    embargo_bars: int = Field(default=16, ge=0, le=200)
    funding_8h_pct: Optional[float] = None


class LabelRequest(BaseModel):
    underlying: str = "BTC"
    profile: str = "intraday_1h"
    lookback_days: int = Field(default=60, ge=14, le=365)
    pt_mult: float = 2.0
    sl_mult: float = 1.0
    max_hold_bars: int = 24
    funding_8h_pct: Optional[float] = None


# ─── Persistence helpers ─────────────────────────────────────────────────


def _ensure_baseline_table() -> None:
    """Idempotent SQLite migration for the baseline_reports table."""
    try:
        conn = sqlite3.connect(_db._DB_PATH)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS baseline_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                underlying TEXT NOT NULL,
                profile TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                deflated_p REAL,
                trade_count INTEGER,
                edge_proven INTEGER,
                run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _persist_baseline(
    underlying: str, profile: str, payload: Dict[str, Any],
) -> None:
    _ensure_baseline_table()
    try:
        conn = sqlite3.connect(_db._DB_PATH)
        conn.execute(
            "INSERT INTO baseline_reports "
            "(underlying, profile, payload_json, deflated_p, trade_count, edge_proven) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                underlying, profile,
                json.dumps(payload, default=str),
                payload.get("deflated_sharpe"),
                payload.get("trade_count", 0),
                int(bool(payload.get("edge_proven", False))),
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ─── Helpers ─────────────────────────────────────────────────────────────


async def _fetch_candles(
    request: Request, underlying: str, profile_key: str, lookback_days: int,
) -> Dict[str, list]:
    from app.services import adapter_manager as _adm
    from app.api.v1.endpoints.directional import _adapter_can_serve

    inst = registry.get_instrument(underlying)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {underlying}")
    src = _adm.get_data_source()
    if not _adapter_can_serve(inst, src):
        raise HTTPException(
            status_code=400,
            detail=f"{underlying} is not available on {src} data source",
        )
    adapter = _adm.get_adapter() or request.app.state.adapter

    needs = {"15m": False, "1H": False, "4H": False, "1D": False}
    if profile_key == "scalping_15m":
        needs["15m"] = True; needs["1H"] = True
    elif profile_key == "intraday_1h":
        needs["1H"] = True;  needs["4H"] = True
    elif profile_key == "intraday_4h":
        needs["4H"] = True;  needs["1D"] = True
    else:
        raise HTTPException(status_code=400, detail=f"Unknown profile: {profile_key}")

    limits = {
        "15m": min(lookback_days * 96 + 100, 4000),
        "1H":  min(lookback_days * 24 + 100, 5000),
        "4H":  min(lookback_days * 6  + 100, 1000),
        "1D":  lookback_days + 30,
    }
    out = {"15m": [], "1H": [], "4H": [], "1D": []}
    try:
        for k in ("15m", "1H", "4H", "1D"):
            if needs[k]:
                out[k] = await adapter.get_candles(inst, k, limit=limits[k])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Candle fetch failed: {exc}")
    return out


def _build_verdict(payload: Dict[str, Any]) -> bool:
    """
    Edge is "proven" only when ALL of:
      - n_trades >= 50
      - observed sharpe > 0 (negative-Sharpe runs can never be an edge)
      - deflated_sharpe probability >= 0.95
    """
    n = int(payload.get("trade_count", 0) or 0)
    ds = payload.get("deflated_sharpe")
    sharpe_v = payload.get("sharpe")
    try:
        sharpe_f = float(sharpe_v) if sharpe_v is not None else None
    except (TypeError, ValueError):
        sharpe_f = None
    if ds is None or sharpe_f is None or sharpe_f <= 0:
        return False
    try:
        return n >= 50 and float(ds) >= 0.95
    except (TypeError, ValueError):
        return False


# ─── Endpoints ───────────────────────────────────────────────────────────


@router.post("/baseline")
async def run_baseline(body: BaselineRequest, request: Request) -> Dict[str, Any]:
    """
    Issue 1 — TTACE truthful baseline. Runs an MTF backtest with the opt-in
    TTACE settings (signal-TF exit ATR, chandelier trail) and emits a report
    via `baseline_report.build_report`. Persists to `baseline_reports` table.
    """
    sym = body.underlying.upper()
    funding = resolve_funding_8h_pct(sym, body.funding_8h_pct)
    candles = await _fetch_candles(request, sym, body.profile, body.lookback_days)

    results = run_mtf_backtest(
        underlying=sym,
        candles_15m=candles["15m"],
        candles_1h=candles["1H"],
        candles_4h=candles["4H"],
        c_1d=candles["1D"],
        profiles=[body.profile],
        funding_8h_pct=funding,
        apply_slippage=True,
        emit_events=True,
        exit_atr_tf=body.exit_atr_tf,           # type: ignore[arg-type]
        payoff_mode=body.payoff_mode,            # type: ignore[arg-type]
    )
    profile_result = results.get(body.profile) or {}
    trades = profile_result.get("events", [])
    # Filter trade events from the ledger for build_report consumption.
    trade_records = []
    for ev in trades:
        if ev.get("kind") != "trade":
            continue
        payload = ev.get("payload") or {}
        trade_records.append({
            "pnl_pct":       payload.get("net_pnl_pct") or 0.0,
            "gross_pnl_pct": payload.get("gross_pnl_pct"),
            "net_pnl_pct":   payload.get("net_pnl_pct"),
            "cost_pct":      payload.get("cost_pct"),
            "regime":        payload.get("regime"),
            "direction":     payload.get("direction"),
            "entry_ts_ms":   payload.get("entry_ts_ms"),
            "exit_ts_ms":    payload.get("exit_ts_ms"),
        })

    from baseline_report import build_report
    profile_meta = PROFILES.get(body.profile)
    signal_bar_ms = profile_meta.signal_bar_ms if profile_meta else None
    report = build_report(
        asset=sym, profile=body.profile,
        trades=trade_records,
        signal_bar_ms=signal_bar_ms,
        n_trials_search=1,
    )
    report["edge_proven"] = _build_verdict(report)
    report["funding_8h_pct_used"] = funding
    report["exit_atr_tf"] = body.exit_atr_tf
    report["payoff_mode"] = body.payoff_mode
    report["timestamp_ms"] = int(time.time() * 1000)
    _persist_baseline(sym, body.profile, report)
    return report


@router.get("/baseline/{underlying}/latest")
async def get_latest_baseline(underlying: str, profile: Optional[str] = None) -> Dict[str, Any]:
    _ensure_baseline_table()
    try:
        conn = sqlite3.connect(_db._DB_PATH)
        conn.row_factory = sqlite3.Row
        if profile:
            row = conn.execute(
                "SELECT * FROM baseline_reports WHERE underlying=? AND profile=? "
                "ORDER BY id DESC LIMIT 1",
                (underlying.upper(), profile),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM baseline_reports WHERE underlying=? "
                "ORDER BY id DESC LIMIT 1",
                (underlying.upper(),),
            ).fetchone()
        conn.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"baseline read failed: {exc}")
    if not row:
        raise HTTPException(status_code=404, detail="no baseline runs found")
    return {
        "id":           row["id"],
        "underlying":   row["underlying"],
        "profile":      row["profile"],
        "deflated_p":   row["deflated_p"],
        "trade_count":  row["trade_count"],
        "edge_proven":  bool(row["edge_proven"]),
        "run_at":       row["run_at"],
        "payload":      json.loads(row["payload_json"]),
    }


@router.post("/cpcv")
async def run_cpcv_endpoint(body: CPCVRequest, request: Request) -> Dict[str, Any]:
    """Issue 10 — Combinatorial Purged CV on the directional track."""
    sym = body.underlying.upper()
    funding = resolve_funding_8h_pct(sym, body.funding_8h_pct)
    candles = await _fetch_candles(request, sym, body.profile, body.lookback_days)
    results = run_mtf_backtest(
        underlying=sym,
        candles_15m=candles["15m"],
        candles_1h=candles["1H"],
        candles_4h=candles["4H"],
        c_1d=candles["1D"],
        profiles=[body.profile],
        funding_8h_pct=funding,
        apply_slippage=True,
        emit_events=True,
    )
    profile_result = results.get(body.profile) or {}
    events = profile_result.get("events", [])
    trade_records: List[Dict[str, Any]] = []
    for ev in events:
        if ev.get("kind") != "trade":
            continue
        payload = ev.get("payload") or {}
        trade_records.append({
            "pnl_pct":   payload.get("net_pnl_pct") or 0.0,
            "entry_bar": payload.get("entry_bar"),
            "exit_bar":  payload.get("exit_bar"),
        })
    cfg = CPCVConfig(
        n_groups=body.n_groups, k_test=body.k_test,
        embargo_bars=body.embargo_bars,
    )
    cpcv = run_cpcv(trade_records, config=cfg)
    return {
        "underlying":            sym,
        "profile":               body.profile,
        "n_trades":              len(trade_records),
        "n_paths":               cpcv.n_paths,
        "mean_train_sharpe":     cpcv.mean_train_sharpe,
        "mean_test_sharpe":      cpcv.mean_test_sharpe,
        "median_test_sharpe":    cpcv.median_test_sharpe,
        "pbo":                   cpcv.pbo,
        "deflated_sharpe_oos":   cpcv.deflated_sharpe_oos,
        "warnings":              cpcv.warnings,
        "config":                asdict(cpcv.config),
    }


@router.post("/labels")
async def label_candidates(body: LabelRequest, request: Request) -> Dict[str, Any]:
    """Issue 13 — triple-barrier labels emitted from the event ledger."""
    sym = body.underlying.upper()
    funding = resolve_funding_8h_pct(sym, body.funding_8h_pct)
    candles = await _fetch_candles(request, sym, body.profile, body.lookback_days)
    profile_meta = PROFILES.get(body.profile)
    if profile_meta is None:
        raise HTTPException(status_code=400, detail=f"Unknown profile: {body.profile}")
    signal_candles = (
        candles["15m"] if body.profile == "scalping_15m" else
        candles["1H"]  if body.profile == "intraday_1h"  else
        candles["4H"]
    )
    results = run_mtf_backtest(
        underlying=sym,
        candles_15m=candles["15m"],
        candles_1h=candles["1H"],
        candles_4h=candles["4H"],
        c_1d=candles["1D"],
        profiles=[body.profile],
        funding_8h_pct=funding,
        apply_slippage=True,
        emit_events=True,
    )
    profile_result = results.get(body.profile) or {}
    events = profile_result.get("events", [])
    candidates = [
        ev for ev in events
        if ev.get("kind") in ("candidate", "entry_fill")
    ]
    labelled = triple_barrier_labels(
        candidates, signal_candles,
        params=BarrierParams(
            pt_mult=body.pt_mult, sl_mult=body.sl_mult,
            max_hold_bars=body.max_hold_bars,
            vol_lookback=14,
        ),
    )
    dist = label_distribution(labelled)
    return {
        "underlying":   sym,
        "profile":      body.profile,
        "n_events":     len(candidates),
        "label_counts": dist,
        "labels":       [
            {
                "bar_idx":          le.bar_idx,
                "label":            le.label,
                "horizon_bars":     le.horizon_bars,
                "barrier_hit":      le.barrier_hit,
                "entry_price":      le.entry_price,
                "realized_return":  le.realized_return,
            }
            for le in labelled
        ],
    }
