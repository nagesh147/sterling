from __future__ import annotations

import math
from datetime import date

import pytest

from app.engines.navigator.gamma_activity import (
    GammaContractInput,
    bs_gamma,
    classify_expiry_profile,
    compute_gamma_sample,
    compute_level_and_acceleration_z,
    evaluate_gamma_activity,
    fractional_time_to_expiry,
    is_gamma_event,
)
from app.engines.navigator.schemas import GammaConfig
from app.services.navigator.calendar import expiry_close_ist

_EXPIRY = date(2026, 8, 6)
_CLOSE_MS = int(expiry_close_ist(_EXPIRY).timestamp() * 1000)


class TestFractionalTimeToExpiry:
    def test_five_days_out_matches_hand_calc(self):
        quote_ms = _CLOSE_MS - 5 * 24 * 3_600_000
        T = fractional_time_to_expiry(quote_ms, _CLOSE_MS)
        assert T == pytest.approx(5.0 / 365.0, rel=1e-6)

    def test_same_day_before_close_is_small_positive(self):
        quote_ms = _CLOSE_MS - 3600_000  # 1 hour before close
        T = fractional_time_to_expiry(quote_ms, _CLOSE_MS)
        assert T is not None and T > 0
        assert T == pytest.approx(1.0 / (365.0 * 24), rel=1e-6)

    def test_exact_zero_is_rejected(self):
        assert fractional_time_to_expiry(_CLOSE_MS, _CLOSE_MS) is None

    def test_negative_is_rejected(self):
        assert fractional_time_to_expiry(_CLOSE_MS + 1000, _CLOSE_MS) is None


class TestBsGammaFixture:
    def test_known_atm_gamma_fixture(self):
        # Hand-verified via the standard closed-form BSM gamma formula:
        # d1 = [ln(S/K) + (r - q + 0.5*sigma^2)*T] / (sigma*sqrt(T))
        #    = [0 + (0.06 + 0.02)*0.082192] / (0.2*0.286688) = 0.114689
        # gamma = N'(d1) / (S*sigma*sqrt(T)) = 0.39633 / 5.73362 = 0.069129
        g = bs_gamma(spot=100.0, strike=100.0, T=30 / 365.0, iv=0.20, risk_free_rate=0.06, dividend_yield=0.0)
        assert g == pytest.approx(0.069129, abs=2e-4)

    def test_invalid_iv_returns_none_not_zero(self):
        assert bs_gamma(spot=100, strike=100, T=0.1, iv=0.0, risk_free_rate=0.06, dividend_yield=0.0) is None
        assert bs_gamma(spot=100, strike=100, T=0.1, iv=None, risk_free_rate=0.06, dividend_yield=0.0) is None

    def test_none_time_returns_none(self):
        assert bs_gamma(spot=100, strike=100, T=None, iv=0.2, risk_free_rate=0.06, dividend_yield=0.0) is None

    def test_negative_or_zero_time_returns_none(self):
        assert bs_gamma(spot=100, strike=100, T=0.0, iv=0.2, risk_free_rate=0.06, dividend_yield=0.0) is None
        assert bs_gamma(spot=100, strike=100, T=-1.0, iv=0.2, risk_free_rate=0.06, dividend_yield=0.0) is None

    def test_gamma_is_nonnegative_across_moneyness(self):
        for strike in (80.0, 100.0, 120.0):
            g = bs_gamma(spot=100.0, strike=strike, T=0.1, iv=0.25, risk_free_rate=0.05, dividend_yield=0.0)
            assert g is not None and g >= 0.0


class TestGammaSampleAggregation:
    def _contract(self, iv=0.2, delta_volume=100, sign=1, lot_size=75, strike=100.0):
        return GammaContractInput(token=1, strike=strike, lot_size=lot_size, iv=iv, delta_volume=delta_volume, price_return_sign=sign)

    def test_gross_activity_is_nonnegative(self):
        contracts = [self._contract(sign=1), self._contract(sign=-1)]
        result = compute_gamma_sample(contracts, spot=100.0, T=0.05, risk_free_rate=0.06, dividend_yield=0.0, min_iv=0.01, max_iv=5.0)
        assert result.gross_gamma_activity >= 0.0
        assert result.valid_contracts == 2

    def test_signed_activity_reflects_sign_mix(self):
        contracts = [self._contract(sign=1, delta_volume=1000), self._contract(sign=-1, delta_volume=1)]
        result = compute_gamma_sample(contracts, spot=100.0, T=0.05, risk_free_rate=0.06, dividend_yield=0.0, min_iv=0.01, max_iv=5.0)
        assert result.signed_gamma_activity > 0  # dominated by the sign=+1, high-volume contract

    def test_iv_out_of_bounds_excludes_contract(self):
        contracts = [self._contract(iv=10.0)]  # above max_iv
        result = compute_gamma_sample(contracts, spot=100.0, T=0.05, risk_free_rate=0.06, dividend_yield=0.0, min_iv=0.01, max_iv=5.0)
        assert result.valid_contracts == 0
        assert result.gross_gamma_activity == 0.0

    def test_missing_delta_volume_excludes_contract_not_zero(self):
        c = GammaContractInput(token=1, strike=100.0, lot_size=75, iv=0.2, delta_volume=None, price_return_sign=1)
        result = compute_gamma_sample([c], spot=100.0, T=0.05, risk_free_rate=0.06, dividend_yield=0.0, min_iv=0.01, max_iv=5.0)
        assert result.valid_contracts == 0


class TestRobustLevelAndAcceleration:
    def test_returns_none_with_insufficient_history(self):
        level_z, accel_z = compute_level_and_acceleration_z([100.0], window=10)
        assert level_z is None

    def test_a_clear_spike_produces_a_large_positive_z(self):
        history = [10.0, 11.0, 9.0, 10.5, 9.5, 10.0, 200.0]
        level_z, accel_z = compute_level_and_acceleration_z(history, window=10)
        assert level_z is not None and level_z > 3.0


class TestGammaEventDetection:
    def test_event_requires_both_thresholds(self):
        assert is_gamma_event(5.0, 3.0, blast_z_min=3.0, acceleration_z_min=2.0, chain_quality_ok=True, sample_count=50, min_samples=30) is True
        assert is_gamma_event(1.0, 3.0, blast_z_min=3.0, acceleration_z_min=2.0, chain_quality_ok=True, sample_count=50, min_samples=30) is False

    def test_undersampled_history_blocks_event(self):
        assert is_gamma_event(10.0, 10.0, blast_z_min=3.0, acceleration_z_min=2.0, chain_quality_ok=True, sample_count=5, min_samples=30) is False

    def test_bad_chain_quality_blocks_event(self):
        assert is_gamma_event(10.0, 10.0, blast_z_min=3.0, acceleration_z_min=2.0, chain_quality_ok=False, sample_count=50, min_samples=30) is False


class TestExpiryProfileSelection:
    def test_non_expiry_day_is_non_expiry_profile(self):
        quote_ms = _CLOSE_MS - 3 * 24 * 3_600_000  # 3 days before expiry
        assert classify_expiry_profile(quote_ms, _EXPIRY, "14:00") == "non_expiry"

    def test_expiry_day_before_1400_ist(self):
        from datetime import datetime
        from app.services.navigator.calendar import IST
        dt = datetime(_EXPIRY.year, _EXPIRY.month, _EXPIRY.day, 11, 0, tzinfo=IST)
        assert classify_expiry_profile(int(dt.timestamp() * 1000), _EXPIRY, "14:00") == "expiry_before_14_ist"

    def test_expiry_day_after_1400_ist(self):
        from datetime import datetime
        from app.services.navigator.calendar import IST
        dt = datetime(_EXPIRY.year, _EXPIRY.month, _EXPIRY.day, 15, 0, tzinfo=IST)
        assert classify_expiry_profile(int(dt.timestamp() * 1000), _EXPIRY, "14:00") == "expiry_after_14_ist"

    def test_clock_alone_cannot_fire_without_an_event(self):
        # after 14:00 on expiry day, but the history is at THE SAME near-
        # expiry scale as the current sample (no real spike/acceleration) ->
        # being in the after-14:00 profile alone must not fire an event.
        from datetime import datetime
        from app.services.navigator.calendar import IST
        dt = datetime(_EXPIRY.year, _EXPIRY.month, _EXPIRY.day, 15, 0, tzinfo=IST)
        quote_ms = int(dt.timestamp() * 1000)
        contracts = [GammaContractInput(token=1, strike=100.0, lot_size=75, iv=0.2, delta_volume=100, price_return_sign=1)]

        # Establish the near-expiry activity scale from the same inputs first.
        baseline = evaluate_gamma_activity(
            spot=100.0, contracts=contracts, quote_ts_ms=quote_ms, expiry_date=_EXPIRY,
            risk_free_rate=0.06, dividend_yield=0.0, profile_history=[], config=GammaConfig(min_samples=1),
        )
        flat_history = [baseline.gross_gamma_activity] * 40
        ev = evaluate_gamma_activity(
            spot=100.0, contracts=contracts, quote_ts_ms=quote_ms, expiry_date=_EXPIRY,
            risk_free_rate=0.06, dividend_yield=0.0, profile_history=flat_history, config=GammaConfig(min_samples=30),
        )
        assert ev.expiry_profile == "expiry_after_14_ist"
        assert ev.is_event is False


class TestEvaluateGammaActivityIntegration:
    def _contracts(self, n=3):
        return [GammaContractInput(token=i, strike=100.0, lot_size=75, iv=0.2, delta_volume=500, price_return_sign=1) for i in range(n)]

    def test_missing_rates_is_unavailable(self):
        ev = evaluate_gamma_activity(
            spot=100.0, contracts=self._contracts(), quote_ts_ms=_CLOSE_MS - 3600_000, expiry_date=_EXPIRY,
            risk_free_rate=None, dividend_yield=None, profile_history=[], config=GammaConfig(),
        )
        assert ev.quality == "unavailable"
        assert ev.reason_codes == ["CONFIG_INVALID"]
        assert ev.gross_gamma_activity is None  # never a fabricated zero

    def test_expired_quote_is_unavailable(self):
        ev = evaluate_gamma_activity(
            spot=100.0, contracts=self._contracts(), quote_ts_ms=_CLOSE_MS + 1000, expiry_date=_EXPIRY,
            risk_free_rate=0.06, dividend_yield=0.0, profile_history=[], config=GammaConfig(),
        )
        assert ev.quality == "unavailable"
        assert ev.reason_codes == ["EXPIRY_INVALID"]

    def test_undersampled_profile_is_warming_up(self):
        ev = evaluate_gamma_activity(
            spot=100.0, contracts=self._contracts(), quote_ts_ms=_CLOSE_MS - 3600_000, expiry_date=_EXPIRY,
            risk_free_rate=0.06, dividend_yield=0.0, profile_history=[10.0, 12.0], config=GammaConfig(min_samples=30),
        )
        assert ev.quality == "unavailable"
        assert ev.reason_codes == ["GAMMA_WARMING_UP"]

    def test_gamma_direction_requires_flow_alignment(self):
        history = [10.0] * 30
        ev_no_flow = evaluate_gamma_activity(
            spot=100.0, contracts=self._contracts(), quote_ts_ms=_CLOSE_MS - 3600_000, expiry_date=_EXPIRY,
            risk_free_rate=0.06, dividend_yield=0.0, profile_history=history + [10000.0], config=GammaConfig(min_samples=30, blast_z_min=1.0, acceleration_z_min=0.5),
            flow_direction=0, flow_quality="unavailable",
        )
        assert ev_no_flow.direction == 0  # gamma alone never supplies direction

    def test_gamma_direction_follows_flow_when_event_and_aligned(self):
        history = [10.0] * 30
        ev = evaluate_gamma_activity(
            spot=100.0, contracts=self._contracts(), quote_ts_ms=_CLOSE_MS - 3600_000, expiry_date=_EXPIRY,
            risk_free_rate=0.06, dividend_yield=0.0, profile_history=history + [10000.0], config=GammaConfig(min_samples=30, blast_z_min=1.0, acceleration_z_min=0.5),
            flow_direction=1, flow_quality="ok",
        )
        if ev.is_event:
            assert ev.direction == 1
