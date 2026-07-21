import numpy as np
import pytest
from typing import List
from app.schemas.market import Candle


def make_candles(n: int = 100, base: float = 30000.0, trend: float = 10.0) -> List[Candle]:
    np.random.seed(42)
    candles = []
    price = base
    for i in range(n):
        price += trend + np.random.normal(0, base * 0.002)
        o = price - abs(np.random.normal(0, base * 0.001))
        c = price + abs(np.random.normal(0, base * 0.001))
        h = max(o, c) + abs(np.random.normal(0, base * 0.0005))
        l = min(o, c) - abs(np.random.normal(0, base * 0.0005))
        candles.append(
            Candle(
                timestamp_ms=1_700_000_000_000 + i * 3_600_000,
                open=round(o, 2), high=round(h, 2),
                low=round(l, 2), close=round(c, 2),
                volume=float(np.random.uniform(100, 500)),
            )
        )
    return candles


def make_bearish_candles(n: int = 100, base: float = 30000.0) -> List[Candle]:
    return make_candles(n, base, trend=-50.0)


def _default_risk():
    from app.schemas.risk import RiskParams
    from app.core.config import settings
    return RiskParams(
        capital=settings.default_capital,
        max_position_pct=settings.max_position_pct,
        max_contracts=settings.max_contracts,
    )


def _reset_exchange_store(eas) -> None:
    """Reset both exchange-account memory and its SQLite write-through table."""
    from app.services import db

    try:
        if db._available:
            with db._conn() as connection:
                connection.execute("DELETE FROM exchange_configs")
    except Exception:
        pass
    eas._configs.clear()
    eas._loaded = False
    eas.bootstrap()


@pytest.fixture(autouse=True)
def reset_global_stores():
    """Reset every module-level and persisted mutable test store."""
    from app.services import paper_store, eval_history, arrow_store
    from app.services import alert_store, pnl_history, webhook_store
    from app.services import exchange_account_store as eas
    from app.services.exchanges.kite import accounts as kite_accounts
    import app.api.v1.endpoints.config as config_ep
    from app.engines.directional.regime_engine import _REGIME_CACHE
    from app.engines.directional.signal_engine import _SIGNAL_CACHE

    paper_store._positions.clear()
    paper_store._loaded = True
    eval_history.clear()
    arrow_store.clear()
    arrow_store._bootstrapped = True
    alert_store.clear()
    alert_store._loaded = True
    pnl_history.clear()
    pnl_history._loaded = True
    webhook_store.clear()
    webhook_store._loaded = True
    _reset_exchange_store(eas)
    kite_accounts.clear()
    config_ep._risk = _default_risk()
    _REGIME_CACHE.clear()
    _SIGNAL_CACHE.clear()

    yield

    paper_store._positions.clear()
    eval_history.clear()
    arrow_store.clear()
    arrow_store._bootstrapped = False
    alert_store.clear()
    pnl_history.clear()
    webhook_store.clear()
    _reset_exchange_store(eas)
    kite_accounts.clear()
    config_ep._risk = _default_risk()
    _REGIME_CACHE.clear()
    _SIGNAL_CACHE.clear()
