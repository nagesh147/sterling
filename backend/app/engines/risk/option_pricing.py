"""Option-chain enrichment: fill any Greeks missing from an OptionSummary
via Black-Scholes, then cache the result so a single poll of N positions
on the same underlying doesn't re-run BSM N times.

Phase 1 of the derivatives build. Consumed by:
  • /options/chain endpoint — every response has all 5 Greeks populated
  • portfolio_greeks_aggregator — gets live IV refresh per open position
  • DerivativesSelector (Phase 2) — strike_picker needs gamma/theta/vega
  • Background monitor — premium-aware trailing reads delta + theta

Caching strategy
----------------
Greeks are stable inside a small spot bucket and constant DTE. We cache
keyed on `(instrument_name, spot_bucket, dte)` where the bucket is the
spot rounded to 0.1% of the spot (so a $50,000 BTC spot uses a $50 bucket
— more than enough resolution for portfolio-level Greeks, far cheaper
than recomputing per call). Entries TTL after 60s and are evicted lazily.
"""
from __future__ import annotations

import math
import time
from typing import Optional

from app.engines.risk.greeks_budget import bsm_greeks_full
from app.schemas.market import OptionSummary
from app.services.delta_iv_socket import iv_manager


# ── cache ─────────────────────────────────────────────────────────────


# {(instrument_name, spot_bucket, dte): (greeks_tuple, ts_ms)}
# Tuple shape: (delta, gamma, vega, theta, rho)
_CACHE: dict[tuple[str, float, int], tuple[tuple[float, float, float, float, float], int]] = {}
_CACHE_TTL_MS = 60_000
_CACHE_MAX = 4096                # eviction floor; far below memory pressure


def _spot_bucket(spot: float) -> float:
    """Bucket spot to a stable ~1% grid derived from its order of
    magnitude so neighbouring poll-time spots reliably hit the same
    cache entry. At BTC $50k → grid step is $100, so spots in
    [$50,000, $50,099] all share the bucket key $50,000.

    Note: an earlier formulation used `spot * 0.001` as the step which
    silently broke cache hits — the step itself drifted as spot moved,
    so two near-identical spots picked different bucket indices.
    Magnitude-derived step is invariant inside an order of magnitude.
    """
    if spot <= 0:
        return 0.0
    magnitude = 10 ** math.floor(math.log10(spot))
    step = magnitude * 0.01     # 1% of magnitude, stable across nearby spots
    return math.floor(spot / step) * step


def _cache_get(key) -> Optional[tuple[float, float, float, float, float]]:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    greeks, ts = entry
    if int(time.time() * 1000) - ts > _CACHE_TTL_MS:
        _CACHE.pop(key, None)
        return None
    return greeks


def _cache_put(key, greeks: tuple[float, float, float, float, float]) -> None:
    # Lazy eviction: when the cache balloons past _CACHE_MAX, drop the
    # oldest 25% by insertion order (Python dicts preserve insertion).
    if len(_CACHE) >= _CACHE_MAX:
        evict_count = _CACHE_MAX // 4
        for k in list(_CACHE.keys())[:evict_count]:
            _CACHE.pop(k, None)
    _CACHE[key] = (greeks, int(time.time() * 1000))


def clear_cache() -> None:
    """Test-only — wipe the cache between test cases that vary spot/IV."""
    _CACHE.clear()


# ── enrichment ────────────────────────────────────────────────────────


def _needs_enrichment(opt: OptionSummary) -> bool:
    """Has anyone — adapter or a prior enrich call — already filled in the
    extended Greeks? If gamma/vega/theta/rho are all zero AND
    greeks_enriched is False, we need to compute."""
    if opt.greeks_enriched:
        return False
    # mark_iv == 0 means BSM has nothing to compute against; skip and
    # leave the zeros in place. Callers see greeks_enriched=False and
    # know not to trust the Greeks for this contract.
    if opt.mark_iv <= 0:
        return False
    return opt.gamma == 0.0 and opt.vega == 0.0 and opt.theta == 0.0 and opt.rho == 0.0


def _normalise_iv(iv: float) -> float:
    """DEI returns IV as a percent (e.g. 65 for 65%) for some products
    and as a decimal (0.65) for others. Normalise to decimal so
    bsm_greeks_full can use sigma directly."""
    if iv <= 0:
        return 0.0
    return iv / 100.0 if iv > 5.0 else iv


def enrich_with_greeks(
    option: OptionSummary, spot: float, r: float = 0.0,
) -> OptionSummary:
    """Return a copy of `option` with the full Greeks vector populated.

    When the adapter already shipped gamma/vega/theta/rho (DEI sometimes
    does, in the `greeks` block of the ticker), they pass through
    untouched and `greeks_enriched` is False. When they're missing, we
    BSM-fill using the option's mark_iv as sigma and stamp
    `greeks_enriched=True`. The result is cached for 60s so a single
    poll fetching the same chain repeatedly doesn't re-run the math.

    Inputs:
      option — the raw OptionSummary from the adapter
      spot   — current underlying spot price (drives BSM)
      r      — risk-free rate (decimal). 0 is fine for short-dated crypto;
               the DerivativesSelector's positional profile sets r > 0 when
               wider DTE warrants it.

    Returns a new OptionSummary; the original is not mutated.
    """
    # ── Live IV Stream Priority ───────────────────────────────────────
    tick = iv_manager.get(option.instrument_name)
    if tick and tick.mark_iv > 0:
        has_greeks = (tick.gamma != 0.0 or tick.vega != 0.0 or tick.theta != 0.0)
        enriched_delta = tick.delta if tick.delta != 0.0 else option.delta
        
        if has_greeks:
            return option.model_copy(update={
                "mark_iv": tick.mark_iv,
                "delta": enriched_delta,
                "gamma": tick.gamma,
                "vega": tick.vega,
                "theta": tick.theta,
                "rho": tick.rho,
                "greeks_enriched": True,
            })
        else:
            # Update the option with live IV and Delta, let it fall through to BSM
            option = option.model_copy(update={
                "mark_iv": tick.mark_iv,
                "delta": enriched_delta,
            })

    if not _needs_enrichment(option):
        return option

    if spot <= 0 or option.dte <= 0 or option.strike <= 0:
        return option

    iv = _normalise_iv(option.mark_iv)
    if iv <= 0:
        return option

    key = (option.instrument_name, _spot_bucket(spot), int(option.dte))
    cached = _cache_get(key)
    if cached is not None:
        delta, gamma, vega, theta, rho = cached
    else:
        is_call = option.option_type == "call"
        T = option.dte / 365.0
        g = bsm_greeks_full(S=spot, K=option.strike, T=T, r=r, sigma=iv, is_call=is_call)
        delta, gamma, vega, theta, rho = g.delta, g.gamma, g.vega, g.theta, g.rho
        _cache_put(key, (delta, gamma, vega, theta, rho))

    # Preserve adapter-supplied delta when present — the adapter's delta is
    # the exchange's mark-implied delta which can differ subtly from a
    # naive BSM (skew, IV smile). Only fill delta if it was unset.
    enriched_delta = option.delta if option.delta != 0.0 else delta

    return option.model_copy(update={
        "delta": enriched_delta,
        "gamma": gamma,
        "vega":  vega,
        "theta": theta,
        "rho":   rho,
        "greeks_enriched": True,
    })


def enrich_chain(
    chain: list[OptionSummary], spot: float, r: float = 0.0,
) -> list[OptionSummary]:
    """Enrich every contract in a chain. Pure — returns a new list."""
    return [enrich_with_greeks(o, spot, r) for o in chain]
