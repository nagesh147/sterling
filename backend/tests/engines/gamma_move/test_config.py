"""Config validation, with the emphasis on the thresholds that must not be zero."""
from __future__ import annotations

import pytest

from app.engines.gamma_move import CALIBRATED_FIELDS, GammaMoveConfig


def test_defaults_validate():
    cfg = GammaMoveConfig().validate()
    assert cfg.enabled is False
    assert cfg.execution_mode == "paper"


def test_defaults_are_the_calibrated_values():
    """The measured numbers, locked. If one changes, the docstring and the
    validation report have to change with it."""
    cfg = GammaMoveConfig()
    assert cfg.level_proximity_pct == 1.0
    assert cfg.min_oi_drop_pct == 3.0
    assert cfg.volume_spike_mult == 2.5
    assert cfg.min_price_gain_pct == 2.0
    assert cfg.regime_period == 10
    # 2.0, not the conventional 3.0: at 3.0 the gate measured *inverted*.
    assert cfg.regime_multiplier == 2.0
    assert cfg.min_option_premium == 10.0
    assert cfg.stop_percent == 30.0


def test_every_calibrated_field_is_a_real_field():
    names = GammaMoveConfig.field_names()
    assert CALIBRATED_FIELDS <= names


@pytest.mark.parametrize("field", ["level_proximity_pct", "min_oi_drop_pct",
                                   "min_price_gain_pct"])
def test_zero_threshold_is_refused(field):
    """Zero does not disable these — it makes the condition trivially true,
    which silently deletes part of the entry rule while looking like a setting."""
    with pytest.raises(ValueError, match=field):
        GammaMoveConfig(**{field: 0}).validate()


def test_volume_multiplier_must_exceed_one():
    with pytest.raises(ValueError, match="volume_spike_mult"):
        GammaMoveConfig(volume_spike_mult=1.0).validate()
    with pytest.raises(ValueError, match="volume_spike_mult"):
        GammaMoveConfig(volume_spike_mult=0.5).validate()


def test_zero_expiry_window_is_a_mistake_not_no_limit():
    with pytest.raises(ValueError, match="not 'no limit'"):
        GammaMoveConfig(max_days_to_expiry=0).validate()


def test_expiry_window_must_be_ordered():
    with pytest.raises(ValueError, match="min_days_to_expiry"):
        GammaMoveConfig(min_days_to_expiry=20, max_days_to_expiry=14).validate()


def test_confirm_bars_bounded():
    GammaMoveConfig(confirm_bars=3).validate()
    with pytest.raises(ValueError, match="confirm_bars"):
        GammaMoveConfig(confirm_bars=4).validate()
    with pytest.raises(ValueError, match="confirm_bars"):
        GammaMoveConfig(confirm_bars=0).validate()


def test_hundred_percent_stop_is_the_premium():
    with pytest.raises(ValueError, match="100% stop is the premium"):
        GammaMoveConfig(stop_percent=100).validate()


def test_percent_target_needs_a_target():
    with pytest.raises(ValueError, match="target_pct"):
        GammaMoveConfig(exit_policy="PERCENT_TARGET", target_pct=0).validate()


class TestLiveGate:
    """Live mode refuses everything the evidence does not support."""

    base = dict(execution_mode="live", protection_mode="GTT", lots=1,
                sizing_mode="LOTS", regime_enabled=True)

    def test_a_fully_specified_live_config_passes(self):
        GammaMoveConfig(**self.base).validate()

    def test_research_exit_policies_refused(self):
        with pytest.raises(ValueError, match="research-only"):
            GammaMoveConfig(**{**self.base, "exit_policy": "PERCENT_TARGET",
                               "target_pct": 50}).validate()

    def test_points_stop_refused(self):
        with pytest.raises(ValueError, match="stop_basis=PERCENT"):
            GammaMoveConfig(**{**self.base, "stop_basis": "POINTS",
                               "stop_points": 5}).validate()

    def test_unprotected_position_refused(self):
        with pytest.raises(ValueError, match="broker-side protection"):
            GammaMoveConfig(**{**self.base, "protection_mode": "NONE"}).validate()

    def test_regime_gate_cannot_be_off(self):
        with pytest.raises(ValueError, match="regime gate"):
            GammaMoveConfig(**{**self.base, "regime_enabled": False}).validate()

    def test_penny_options_refused(self):
        with pytest.raises(ValueError, match="min_option_premium"):
            GammaMoveConfig(**{**self.base, "min_option_premium": 1.0}).validate()

    def test_size_must_be_set(self):
        with pytest.raises(ValueError, match="explicit positive size"):
            GammaMoveConfig(**{**self.base, "lots": 0}).validate()


def test_as_dict_round_trips():
    cfg = GammaMoveConfig(min_oi_drop_pct=4.5, explicit_symbols=("RELIANCE",))
    again = GammaMoveConfig(**{**cfg.as_dict(),
                               "explicit_symbols": tuple(cfg.as_dict()["explicit_symbols"])})
    assert again.min_oi_drop_pct == 4.5
    assert again.explicit_symbols == ("RELIANCE",)
