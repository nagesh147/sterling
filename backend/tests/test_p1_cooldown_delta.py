"""
Tests for P1 strategy hardening primitives:
 1. Re-entry cooldown engine (per underlying × mode × direction)
 2. Delta-targeted strike filter on get_healthy_candidates

No orchestrator wiring is exercised here — these tests cover the pure
engine primitives and confirm they compose correctly.
"""
import time
import pytest

from app.engines.risk import cooldown
from app.engines.risk.cooldown import CooldownConfig
from app.engines.directional.option_translation_engine import get_healthy_candidates
from app.schemas.market import OptionSummary
from app.schemas.directional import IVRBand, PolicyResult
from app.schemas.instruments import InstrumentMeta


_INST = InstrumentMeta(
    underlying="BTC",
    tick_size=0.5,
    strike_step=1000.0,
    exchange="deribit",
    exchange_currency="BTC",
    perp_symbol="BTC-PERPETUAL",
    index_name="btc_usd",
    dvol_symbol="BTC-DVOL",
)

_POLICY = PolicyResult(
    allowed_structures=["naked_call", "bull_call_spread"],
    ivr=50.0,
    ivr_band=IVRBand.NORMAL,
    preferred_dte_min=10,
    preferred_dte_max=21,
    naked_allowed=True,
    debit_preferred=False,
    avoid_long_premium=False,
)


def _opt(strike: float, delta: float, dte: int = 14, otype: str = "call") -> OptionSummary:
    """Build a healthy OptionSummary with controllable strike + delta.

    Uses time.time() so the staleness check (5-min ceiling) always passes.
    """
    mid = max(20.0, strike * 0.001)
    spread = mid * 0.05
    return OptionSummary(
        instrument_name=f"BTC-{otype.upper()}-{int(strike)}",
        underlying="BTC",
        strike=strike,
        expiry_date="2026-12-31",
        dte=dte,
        option_type=otype,
        bid=mid - spread / 2,
        ask=mid + spread / 2,
        mark_price=mid,
        mid_price=mid,
        mark_iv=0.65,
        delta=delta,
        open_interest=500.0,
        volume_24h=200.0,
        last_updated_ms=int(time.time() * 1000),
    )


# ─── Cooldown engine ────────────────────────────────────────────────────────

class TestCooldownEngine:

    def setup_method(self) -> None:
        cooldown.clear()

    def test_no_prior_exit_is_not_blocked(self) -> None:
        assert cooldown.is_blocked("BTC", "swing", "long", now_ms=1_000_000) is False

    def test_recent_exit_blocks_same_key(self) -> None:
        cooldown.record_exit("BTC", "swing", "long", exit_ts_ms=1_000_000)
        # 1 minute later — well inside the 240-minute swing cooldown
        assert cooldown.is_blocked(
            "BTC", "swing", "long", now_ms=1_000_000 + 60_000
        ) is True

    def test_expired_cooldown_does_not_block(self) -> None:
        cooldown.record_exit("BTC", "swing", "long", exit_ts_ms=1_000_000)
        # 4h + 1 minute later
        future_ms = 1_000_000 + (240 * 60 * 1000) + 60_000
        assert cooldown.is_blocked("BTC", "swing", "long", now_ms=future_ms) is False

    def test_different_mode_is_isolated(self) -> None:
        """A scalping exit must NOT block a swing entry on the same underlying."""
        cooldown.record_exit("BTC", "scalping", "long", exit_ts_ms=1_000_000)
        assert cooldown.is_blocked(
            "BTC", "swing", "long", now_ms=1_000_000 + 60_000
        ) is False

    def test_different_direction_is_isolated(self) -> None:
        """A long exit must NOT block a short re-entry on the same underlying."""
        cooldown.record_exit("BTC", "swing", "long", exit_ts_ms=1_000_000)
        assert cooldown.is_blocked(
            "BTC", "swing", "short", now_ms=1_000_000 + 60_000
        ) is False

    def test_different_underlying_is_isolated(self) -> None:
        cooldown.record_exit("BTC", "swing", "long", exit_ts_ms=1_000_000)
        assert cooldown.is_blocked(
            "ETH", "swing", "long", now_ms=1_000_000 + 60_000
        ) is False

    def test_case_insensitive_keying(self) -> None:
        cooldown.record_exit("btc", "SWING", "Long", exit_ts_ms=1_000_000)
        assert cooldown.is_blocked(
            "BTC", "swing", "long", now_ms=1_000_000 + 60_000
        ) is True

    def test_remaining_ms_decays_to_zero(self) -> None:
        cooldown.record_exit("BTC", "scalping", "long", exit_ts_ms=1_000_000)
        cfg = CooldownConfig()
        # 1 minute in — 4 minutes left of the 5-minute scalp cooldown
        rem = cooldown.remaining_ms(
            "BTC", "scalping", "long",
            now_ms=1_000_000 + 60_000, config=cfg,
        )
        assert 230_000 <= rem <= 240_001

    def test_clear_resets_state(self) -> None:
        cooldown.record_exit("BTC", "swing", "long", exit_ts_ms=1_000_000)
        cooldown.clear()
        assert cooldown.is_blocked(
            "BTC", "swing", "long", now_ms=1_000_000 + 60_000
        ) is False

    def test_unknown_mode_uses_default_window(self) -> None:
        cfg = CooldownConfig()
        cooldown.record_exit("BTC", "weekly", "long", exit_ts_ms=1_000_000)
        # default_min = 60. At 30min still blocked, at 61min not.
        assert cooldown.is_blocked(
            "BTC", "weekly", "long",
            now_ms=1_000_000 + 30 * 60_000, config=cfg,
        ) is True
        assert cooldown.is_blocked(
            "BTC", "weekly", "long",
            now_ms=1_000_000 + 61 * 60_000, config=cfg,
        ) is False

    def test_per_mode_window_lengths(self) -> None:
        cfg = CooldownConfig()
        assert cfg.for_mode("scalping") == 5
        assert cfg.for_mode("intraday") == 30
        assert cfg.for_mode("swing") == 240
        assert cfg.for_mode("positional") == 720


# ─── Delta-band filter on get_healthy_candidates ─────────────────────────────

class TestDeltaBandFilter:

    def test_no_band_passes_all_in_strike_range(self) -> None:
        chain = [
            _opt(strike=100_000, delta=0.10),
            _opt(strike=100_000, delta=0.30),
            _opt(strike=100_000, delta=0.70),
        ]
        out = get_healthy_candidates(
            _INST, _POLICY, chain, spot_price=100_000.0, option_type="call",
        )
        assert len(out) == 3

    def test_band_includes_only_in_range(self) -> None:
        chain = [
            _opt(strike=100_000, delta=0.10),
            _opt(strike=100_000, delta=0.30),
            _opt(strike=100_000, delta=0.50),
            _opt(strike=100_000, delta=0.70),
        ]
        out = get_healthy_candidates(
            _INST, _POLICY, chain, spot_price=100_000.0, option_type="call",
            target_delta_band=(0.20, 0.40),
        )
        assert len(out) == 1
        assert out[0].delta == 0.30

    def test_band_handles_negative_put_deltas(self) -> None:
        """Puts have delta in [-1, 0]. Filter compares |delta|."""
        chain = [
            _opt(strike=100_000, delta=-0.10, otype="put"),
            _opt(strike=100_000, delta=-0.30, otype="put"),
            _opt(strike=100_000, delta=-0.55, otype="put"),
        ]
        out = get_healthy_candidates(
            _INST, _POLICY, chain, spot_price=100_000.0, option_type="put",
            target_delta_band=(0.20, 0.45),
        )
        assert len(out) == 1
        assert abs(out[0].delta) == 0.30

    def test_zero_delta_passes_through_when_band_set(self) -> None:
        """delta == 0 means greeks unavailable. Don't drop the contract."""
        chain = [
            _opt(strike=100_000, delta=0.0),
            _opt(strike=100_000, delta=0.30),
        ]
        out = get_healthy_candidates(
            _INST, _POLICY, chain, spot_price=100_000.0, option_type="call",
            target_delta_band=(0.50, 0.80),
        )
        # delta=0.0 contract passes through; delta=0.30 dropped (out of band)
        assert len(out) == 1
        assert out[0].delta == 0.0

    def test_band_combined_with_strike_filter(self) -> None:
        """Band filter must compose with the existing strike% filter."""
        # Strike at 30% from spot — already excluded by max_strike_pct=0.25
        chain = [
            _opt(strike=130_000, delta=0.30),
            _opt(strike=100_000, delta=0.30),
        ]
        out = get_healthy_candidates(
            _INST, _POLICY, chain, spot_price=100_000.0, option_type="call",
            target_delta_band=(0.20, 0.40),
        )
        assert len(out) == 1
        assert out[0].strike == 100_000
