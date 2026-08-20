"""Config load-time safety and single-auto-path guarantees."""
import json
from datetime import date

import pytest

from app.services import nifty_orb_options as service
from app.engines.nifty_orb_options import StrategyConfig, is_monthly_expiry


class FakeDB:
    def __init__(self, stored=None):
        self.store = dict(stored or {})

    def get_config(self, key):
        return self.store.get(key)

    def set_config(self, key, value):
        self.store[key] = value


@pytest.fixture
def db(monkeypatch):
    fake = FakeDB()
    import app.services.db as real_db
    monkeypatch.setattr(real_db, "get_config", fake.get_config)
    monkeypatch.setattr(real_db, "set_config", fake.set_config)
    return fake


def test_a_valid_stored_config_is_loaded(db):
    db.store[service._CONFIG_KEY] = json.dumps({**StrategyConfig().__dict__, "enabled": True, "max_risk_inr": 5000.0})
    cfg = service.get_config()
    assert cfg.enabled is True
    assert cfg.max_risk_inr == 5000.0


def test_an_invalid_stored_config_falls_back_to_disabled_defaults(db, caplog):
    """A row written before validation existed must not become a trading config."""
    db.store[service._CONFIG_KEY] = json.dumps({**StrategyConfig().__dict__, "enabled": True, "volume_multiplier": 0.0})
    cfg = service.get_config()
    assert cfg.enabled is False                      # disabled is the safe state
    assert cfg == StrategyConfig(enabled=False)
    assert "invalid" in caplog.text.lower()


def test_an_out_of_range_stored_dte_range_also_falls_back(db):
    db.store[service._CONFIG_KEY] = json.dumps(
        {**StrategyConfig().__dict__, "enabled": True, "expiry_dte_min": 9, "expiry_dte_max": 2}
    )
    assert service.get_config().enabled is False


def test_no_stored_config_means_disabled(db):
    assert service.get_config() == StrategyConfig(enabled=False)


def test_set_config_persists_only_a_validated_config(db):
    with pytest.raises(ValueError, match="volume_multiplier"):
        service.set_config({"volume_multiplier": 0})
    assert service._CONFIG_KEY not in db.store   # nothing half-written


def test_set_config_rejects_an_expiry_preference_the_api_does_not_offer(db):
    """The engine accepts "any"; an operator-facing options strategy must choose."""
    with pytest.raises(ValueError, match="nearest, weekly or monthly"):
        service.set_config({"expiry_selection": "any"})


def test_execute_scan_is_the_only_automatic_execution_path():
    """`execute_auto` was an unreferenced duplicate that skipped the daily-loss
    breaker, fabricated a full fill on a broker read failure, and ignored whether
    protection actually armed. Any re-introduction must go through execute_scan."""
    assert not hasattr(service, "execute_auto")
    from app.services import nifty_orb_execution
    assert callable(nifty_orb_execution.execute_scan)


def test_the_kite_expiry_rule_is_the_engine_rule():
    """Guards against a third local reimplementation of weekly-vs-monthly."""
    import inspect
    source = inspect.getsource(service._kite_options)
    assert "is_monthly_expiry" in source
    assert is_monthly_expiry(date(2026, 8, 27)) is True      # last Thursday of August
    assert is_monthly_expiry(date(2026, 9, 3)) is False
