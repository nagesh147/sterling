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
    # `paper_store`, `alert_store`, `exchange_account_store` and the directional
    # engine's caches went with the crypto surface. Importing them here made an
    # AUTOUSE fixture raise, which errored every one of the 3748 collected tests
    # — the suite could not run at all.
    from app.services import eval_history, arrow_store
    from app.services import pnl_history, webhook_store
    from app.services.exchanges.kite import accounts as kite_accounts
    import app.api.v1.endpoints.config as config_ep

    eval_history.clear()
    arrow_store.clear()
    arrow_store._bootstrapped = True
    pnl_history.clear()
    pnl_history._loaded = True
    webhook_store.clear()
    webhook_store._loaded = True
    kite_accounts.clear()
    config_ep._risk = _default_risk()

    yield

    eval_history.clear()
    arrow_store.clear()
    arrow_store._bootstrapped = False
    pnl_history.clear()
    webhook_store.clear()
    kite_accounts.clear()
    config_ep._risk = _default_risk()
