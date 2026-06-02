"""Live options-chain snapshot capture for the derivatives edge study.

Pulls the full Delta India option chain once, persists it as a
reproducible JSON fixture, and extracts the structured surface
parameters that the options simulator needs: ATM IV curve, skew,
VRP, and measured spread%.

Also serves as a fixture loader for offline/replay runs so that
the options model is always tagged with the exact snapshot it uses.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from app.engines.derivatives_native.regime import compute_regime
from app.schemas.market import OptionSummary

log = logging.getLogger(__name__)


@dataclass
class SurfaceSnapshot:
    """Calibratable surface slice captured from the live chain.

    All parameters measured from the raw tickers returned by
    Delta India /v2/tickers at the moment of the snapshot.
    """
    underlying: str
    spot: float
    timestamp_ms: int
    snapshot_date: str            # YYYY-MM-DD (for labelling)
    atm_iv: dict[int, float]      # DTE → ATM IV
    skew_25d: float | None        # put IV − call IV at |delta| ≈ 0.25
    vrp: float | None             # ATM_IV(30d) / realized_vol_30d
    realized_vol_30d: float | None
    spread_median_pct: float
    regime_label: str             # "cheap" | "fair" | "rich" | "unknown"
    regime_provisional: bool
    chain_json: str               # serialized full chain (list[dict])

    @property
    def fixture_path(self) -> str:
        """Default fixture path: study/fixtures/delta_surface_<date>_<ul>.json"""
        return os.path.join(
            os.path.dirname(__file__), "fixtures",
            f"delta_surface_{self.snapshot_date}_{self.underlying}.json",
        )

    def save_fixture(self, path: Optional[str] = None) -> str:
        """Persist the snapshot to a JSON fixture for reproducibility."""
        dest = path or self.fixture_path
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w") as fh:
            json.dump({
                "underlying": self.underlying,
                "spot": self.spot,
                "timestamp_ms": self.timestamp_ms,
                "snapshot_date": self.snapshot_date,
                "atm_iv": self.atm_iv,
                "skew_25d": self.skew_25d,
                "vrp": self.vrp,
                "realized_vol_30d": self.realized_vol_30d,
                "spread_median_pct": self.spread_median_pct,
                "regime_label": self.regime_label,
                "regime_provisional": self.regime_provisional,
                "chain": json.loads(self.chain_json),
            }, fh, indent=2, default=str)
        log.info("Surface fixture saved: %s", dest)
        return dest

    @staticmethod
    def load_fixture(path: str) -> SurfaceSnapshot:
        """Deserialize a previously-saved snapshot."""
        with open(path) as fh:
            data = json.load(fh)
        return SurfaceSnapshot(
            underlying=data["underlying"],
            spot=data["spot"],
            timestamp_ms=data["timestamp_ms"],
            snapshot_date=data["snapshot_date"],
            atm_iv={int(k): v for k, v in data["atm_iv"].items()},
            skew_25d=data.get("skew_25d"),
            vrp=data.get("vrp"),
            realized_vol_30d=data.get("realized_vol_30d"),
            spread_median_pct=data["spread_median_pct"],
            regime_label=data["regime_label"],
            regime_provisional=data.get("regime_provisional", True),
            chain_json=json.dumps(data["chain"]),
        )


async def capture_live(
    underlying: str,
    adapter,                         # BaseExchangeAdapter (live or mock)
    spot: Optional[float] = None,
) -> SurfaceSnapshot | None:
    """Fetch the live chain and build a SurfaceSnapshot.

    Requires a live adapter. Returns None if the underlying has no
    listed options (e.g. SOL on Delta India) or the chain is empty.
    """
    from app.services.exchanges import instrument_registry as registry
    from app.engines.risk.option_pricing import enrich_chain

    inst = registry.get_instrument(underlying)
    if inst is None:
        log.warning("No instrument for %s; cannot capture surface", underlying)
        return None

    if spot is None:
        spot_raw = await adapter.get_index_price(inst)
        spot = float(spot_raw) if spot_raw else 0.0

    chain_raw = await adapter.get_option_chain(inst)
    if not chain_raw:
        log.warning("Empty option chain for %s", underlying)
        return None

    # Enrich missing greeks (fill BSM for any missing fields)
    chain_enriched = enrich_chain(chain_raw, spot)
    if not chain_enriched:
        log.warning("Enrichment produced empty chain for %s", underlying)
        return None

    now_ms = int(time.time() * 1000)
    snapshot_date = time.strftime("%Y-%m-%d", time.gmtime(now_ms / 1000))

    # ── ATM IV per expiry ───────────────────────────────────────────────
    atm_iv: dict[int, float] = {}
    for tick in chain_enriched:
        if tick.option_type not in ("call", "put"):
            continue
        dte = int(tick.dte) if tick.dte else 0
        delta_abs = abs(tick.delta) if tick.delta else 0.0
        # Near-the-money: |delta| in [0.35, 0.65]
        if 0.35 <= delta_abs <= 0.65 and tick.mark_iv and tick.mark_iv > 0:
            atm_iv[dte] = tick.mark_iv

    # ── Skew: put IV − call IV at |delta| ≈ 0.25 ───────────────────────
    put_25d = [t.mark_iv for t in chain_enriched
               if t.option_type == "put" and 0.20 <= abs(t.delta or 0) <= 0.30
               and t.mark_iv and t.mark_iv > 0]
    call_25d = [t.mark_iv for t in chain_enriched
                if t.option_type == "call" and 0.20 <= abs(t.delta or 0) <= 0.30
                and t.mark_iv and t.mark_iv > 0]
    skew_25d = None
    if put_25d and call_25d:
        skew_25d = round(
            (sum(put_25d) / len(put_25d)) - (sum(call_25d) / len(call_25d)), 4)

    # ── Spread% ─────────────────────────────────────────────────────────
    spreads = [t.spread_pct for t in chain_enriched
               if t.spread_pct is not None and t.spread_pct > 0]
    spread_median_pct = round(float(sorted(spreads)[len(spreads) // 2]), 4) if spreads else 0.0

    # ── VRP (ATM_IV / realized_vol) ─────────────────────────────────────
    atm_iv_30d = atm_iv.get(30) or atm_iv.get(max(atm_iv.keys())) if atm_iv else None
    rv_30d = None
    try:
        candles = await adapter.get_candles(inst, "1D", limit=60)
        if candles and len(candles) >= 30:
            import numpy as np
            closes = np.array([c.close for c in candles[-30:]])
            log_ret = np.diff(np.log(closes))
            rv_30d = float(log_ret.std(ddof=1) * np.sqrt(365))
    except Exception:
        # candles might not be available or failed
        pass

    vrp = (atm_iv_30d / rv_30d) if (atm_iv_30d and rv_30d and rv_30d > 0) else None

    # ── Regime classification ───────────────────────────────────────────
    regime = compute_regime(
        atm_iv=atm_iv_30d,
        realized_vol=rv_30d,
        underlying=underlying,
    )

    # ── Serialize chain as JSON string ──────────────────────────────────
    chain_dicts = []
    for t in chain_enriched:
        d = {
            "option_type": t.option_type,
            "strike": t.strike,
            "expiry": str(t.expiry) if t.expiry else None,
            "dte": t.dte,
            "mark_iv": t.mark_iv,
            "bid_iv": t.bid_iv,
            "ask_iv": t.ask_iv,
            "delta": t.delta,
            "gamma": t.gamma,
            "theta": t.theta,
            "vega": t.vega,
            "rho": t.rho,
            "mark_price": t.mark_price,
            "bid": t.bid_price,
            "ask": t.ask_price,
            "oi": t.oi,
            "volume": t.volume,
            "spread_pct": t.spread_pct,
        }
        chain_dicts.append(d)

    return SurfaceSnapshot(
        underlying=underlying,
        spot=round(spot, 2),
        timestamp_ms=now_ms,
        snapshot_date=snapshot_date,
        atm_iv=atm_iv,
        skew_25d=skew_25d,
        vrp=round(vrp, 4) if vrp else None,
        realized_vol_30d=round(rv_30d, 4) if rv_30d else None,
        spread_median_pct=spread_median_pct,
        regime_label=regime.label,
        regime_provisional=regime.provisional,
        chain_json=json.dumps(chain_dicts),
    )
