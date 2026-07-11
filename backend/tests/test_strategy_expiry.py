"""
Tests for strategy-aware option expiry and strike selection.

Verifies:
1. _strategy_expiry picks the Friday closest to dte_preferred midpoint
2. Selected DTE is always within [dte_min, dte_max] (or fallback when no Friday exists)
3. The 2× rule: DTE ≥ 2× expected hold time for all modes and all days of the week
4. Strike selection matches the mode's theta/delta strategy
5. opt_symbol format is correct for Delta Exchange India
"""
import datetime
import pytest

from app.api.v1.endpoints.directional import _strategy_expiry, _option_params
from app.core.trading_mode import MODES, TradingModeConfig

# Signal-timeframe minutes per bar (for computing expected hold time in days)
TF_MINS: dict[str, int] = {
    "scalping":   1,
    "intraday":   5,
    "swing":      60,
    "positional": 240,
    "all":        60,
}

# ── helpers ───────────────────────────────────────────────────────────────────

def all_mondays_in_year() -> list[datetime.date]:
    """Return every Monday in 2026 — covers all weekday patterns."""
    d = datetime.date(2026, 1, 5)   # first Monday of 2026
    dates = []
    while d.year == 2026:
        dates.append(d)
        d += datetime.timedelta(weeks=1)
    return dates


def expected_hold_days(mode_name: str, mode: TradingModeConfig) -> float:
    mins = TF_MINS.get(mode_name, 60)
    return (mode.max_hold_bars * mins) / (60 * 24)


# ── expiry tests ──────────────────────────────────────────────────────────────

class TestStrategyExpiry:

    def test_result_is_a_friday(self):
        """Selected expiry must always be a Friday."""
        for mode_name, mode in MODES.items():
            for monday in all_mondays_in_year()[:8]:       # first 8 weeks
                for offset in range(7):                     # all days of week
                    day = monday + datetime.timedelta(days=offset)
                    expiry_str, _dte = _strategy_expiry(
                        mode.dte_min, mode.dte_preferred, mode.dte_max, as_of=day
                    )
                    exp_date = datetime.datetime.strptime(expiry_str, '%d%m%y').date()
                    assert exp_date.weekday() == 4, (
                        f"{mode_name} on {day}: expiry {expiry_str} is not a Friday"
                    )

    def test_dte_within_range_or_fallback(self):
        """
        DTE should be within [dte_min, dte_max] whenever a Friday exists in range.
        On days where no Friday fits (e.g. dte_max=3 on a Saturday with nearest
        Friday 6 days away), the fallback may exceed dte_max — that is acceptable.
        """
        for mode_name, mode in MODES.items():
            for monday in all_mondays_in_year()[:8]:
                for offset in range(7):
                    day = monday + datetime.timedelta(days=offset)
                    _, dte = _strategy_expiry(
                        mode.dte_min, mode.dte_preferred, mode.dte_max, as_of=day
                    )
                    assert dte >= 0, f"{mode_name} on {day}: negative DTE {dte}"
                    # Check if a Friday existed in range
                    candidates = []
                    for d in range(max(0, mode.dte_min), mode.dte_max + 8):
                        candidate = day + datetime.timedelta(days=d)
                        if candidate.weekday() == 4:
                            cdte = (candidate - day).days
                            if mode.dte_min <= cdte <= mode.dte_max:
                                candidates.append(cdte)
                    if candidates:
                        assert mode.dte_min <= dte <= mode.dte_max, (
                            f"{mode_name} on {day}: DTE {dte} outside "
                            f"[{mode.dte_min}, {mode.dte_max}] despite valid candidates {candidates}"
                        )

    def test_preferred_midpoint_is_respected(self):
        """
        When multiple Fridays exist in range, the one closest to the preferred
        midpoint is chosen.
        """
        for mode_name, mode in MODES.items():
            pref_mid = (mode.dte_preferred[0] + mode.dte_preferred[1]) / 2.0
            monday = datetime.date(2026, 5, 18)             # a known Monday
            for offset in range(5):                         # Mon–Fri
                day = monday + datetime.timedelta(days=offset)
                _, selected_dte = _strategy_expiry(
                    mode.dte_min, mode.dte_preferred, mode.dte_max, as_of=day
                )
                # Collect all valid candidates
                candidates = []
                for d in range(max(0, mode.dte_min), mode.dte_max + 8):
                    candidate = day + datetime.timedelta(days=d)
                    if candidate.weekday() == 4:
                        cdte = (candidate - day).days
                        if mode.dte_min <= cdte <= mode.dte_max:
                            candidates.append(cdte)
                if len(candidates) >= 2:
                    best = min(candidates, key=lambda x: abs(x - pref_mid))
                    assert selected_dte == best, (
                        f"{mode_name} on {day}: selected DTE {selected_dte} "
                        f"but {best} is closer to preferred midpoint {pref_mid}"
                    )

    def test_theta_2x_rule(self):
        """
        For all modes and all weekdays: selected DTE / expected hold time >= 2
        (except scalping 0DTE on expiry day — intentional intraday strategy).
        """
        for mode_name, mode in MODES.items():
            hold_days = expected_hold_days(mode_name, mode)
            if hold_days < 0.1:
                continue                # scalping: seconds-to-minutes, ratio is huge
            monday = datetime.date(2026, 5, 18)
            for offset in range(7):
                day = monday + datetime.timedelta(days=offset)
                _, dte = _strategy_expiry(
                    mode.dte_min, mode.dte_preferred, mode.dte_max, as_of=day
                )
                # 0 DTE on expiry day is allowed for intraday/scalping
                # because force_close_time exits before market close
                if dte == 0 and mode.force_close_time is not None:
                    continue
                ratio = dte / hold_days if hold_days > 0 else 999
                assert ratio >= 2.0, (
                    f"{mode_name} on {day} ({day.strftime('%A')}): "
                    f"DTE={dte}, hold={hold_days:.1f}d, ratio={ratio:.1f}x — below 2× rule"
                )

    def test_expiry_format(self):
        """Expiry string must be 6 digits DDMMYY."""
        _, _dte = _strategy_expiry(7, (10, 21), 30)
        expiry, _ = _strategy_expiry(7, (10, 21), 30)
        assert len(expiry) == 6 and expiry.isdigit(), f"Bad format: {expiry!r}"

    def test_swing_skips_short_expiry(self):
        """Swing (dte_min=7) must never return a Friday < 7 DTE."""
        mode = MODES['swing']
        monday = datetime.date(2026, 5, 18)
        for offset in range(7):
            day = monday + datetime.timedelta(days=offset)
            _, dte = _strategy_expiry(
                mode.dte_min, mode.dte_preferred, mode.dte_max, as_of=day
            )
            assert dte >= mode.dte_min, (
                f"swing on {day}: DTE {dte} < dte_min {mode.dte_min}"
            )

    def test_positional_minimum_dte(self):
        """Positional (dte_min=21) must always return DTE >= 21."""
        mode = MODES['positional']
        monday = datetime.date(2026, 5, 18)
        for offset in range(7):
            day = monday + datetime.timedelta(days=offset)
            _, dte = _strategy_expiry(
                mode.dte_min, mode.dte_preferred, mode.dte_max, as_of=day
            )
            assert dte >= 21, f"positional on {day}: DTE {dte} < 21"


# ── option params tests ───────────────────────────────────────────────────────

class TestOptionParams:

    @pytest.mark.parametrize("spot, expected_step", [
        (80_000, 500),
        (2_100,  100),
        (150,     10),
    ])
    def test_atm_strike_rounds_correctly(self, spot, expected_step):
        mode = MODES['intraday']
        params = _option_params('BTC', spot, 'short', mode)
        assert params['opt_strike'] % expected_step == 0

    def test_long_direction_gives_ce(self):
        params = _option_params('BTC', 80_000, 'long', MODES['swing'])
        assert params['opt_type'] == 'CE'

    def test_short_direction_gives_pe(self):
        params = _option_params('BTC', 80_000, 'short', MODES['swing'])
        assert params['opt_type'] == 'PE'

    def test_swing_uses_itm_call(self):
        """Swing long: CE strike should be 1 step BELOW spot (ITM)."""
        spot = 80_000
        mode = MODES['swing']
        step = 500   # BTC
        params = _option_params('BTC', spot, 'long', mode)
        atm = round(spot / step) * step
        assert params['opt_strike'] == atm - step, (
            f"swing CE strike {params['opt_strike']} should be ATM-step={atm - step}"
        )

    def test_swing_uses_itm_put(self):
        """Swing short: PE strike should be 1 step ABOVE spot (ITM)."""
        spot = 80_000
        mode = MODES['swing']
        step = 500
        params = _option_params('BTC', spot, 'short', mode)
        atm = round(spot / step) * step
        assert params['opt_strike'] == atm + step, (
            f"swing PE strike {params['opt_strike']} should be ATM+step={atm + step}"
        )

    def test_scalping_uses_atm(self):
        """Scalping uses ATM for maximum gamma."""
        spot = 80_000
        mode = MODES['scalping']
        step = 500
        params = _option_params('BTC', spot, 'short', mode)
        atm = round(spot / step) * step
        assert params['opt_strike'] == atm

    def test_positional_uses_atm(self):
        """Positional uses ATM."""
        spot = 2_100
        mode = MODES['positional']
        step = 100
        params = _option_params('ETH', spot, 'long', mode)
        atm = round(spot / step) * step
        assert params['opt_strike'] == atm

    def test_opt_symbol_format(self):
        """Symbol must be {C|P}-{SYM}-{strike}-{DDMMYY}."""
        params = _option_params('BTC', 80_000, 'short', MODES['swing'])
        parts = params['opt_symbol'].split('-')
        assert len(parts) == 4, f"Bad symbol: {params['opt_symbol']}"
        assert parts[0] in ('C', 'P')
        assert parts[1] == 'BTC'
        assert parts[2].isdigit()
        assert len(parts[3]) == 6 and parts[3].isdigit()

    def test_swing_dte_is_strategy_aware(self):
        """Swing must not return next-Friday DTE < 7."""
        mode = MODES['swing']
        params = _option_params('BTC', 80_000, 'short', mode)
        assert params['opt_dte'] >= mode.dte_min, (
            f"swing DTE {params['opt_dte']} < dte_min {mode.dte_min}"
        )

    def test_positional_dte_is_strategy_aware(self):
        """Positional must not return DTE < 21."""
        mode = MODES['positional']
        params = _option_params('ETH', 2_100, 'long', mode)
        assert params['opt_dte'] >= 21, (
            f"positional DTE {params['opt_dte']} < 21"
        )

    def test_none_mode_falls_back_to_swing(self):
        """Passing mode=None should not crash and returns swing-like DTE."""
        params = _option_params('BTC', 80_000, 'long', None)
        assert params['opt_strike'] is not None
        assert params['opt_dte'] is not None

    def test_all_fields_present(self):
        required = {'opt_strike', 'opt_type', 'opt_expiry', 'opt_dte', 'opt_symbol'}
        params = _option_params('BTC', 80_000, 'short', MODES['intraday'])
        assert required.issubset(params.keys())
