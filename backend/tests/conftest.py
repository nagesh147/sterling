import numpy as np
import pytest
from typing import List
from app.schemas.market import Candle


def make_candles(n: int = 100, base: float = 30000.0, trend: float = 10.0) -> List[Candle]:
    np.random.seed(42)
    candles = []
    price = base
    for i in range(n):
        price += trend + np.random.normal(0, base * 0.002)  # noise 2x smaller than before
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
    # trend=-50 dominates noise σ≈base*0.002=60 at base=30000
    return make_candles(n, base, trend=-50.0)


def _default_risk():
    from app.schemas.risk import RiskParams
    from app.core.config import settings
    return RiskParams(
        capital=settings.default_capital,
        max_position_pct=settings.max_position_pct,
        max_contracts=settings.max_contracts,
    )


@pytest.fixture(autouse=True)
def reset_global_stores():
    """
    Reset ALL module-level mutable state between every test.
    Covers: paper positions, eval history, arrow store, risk config.
    Sets _loaded=True to bypass SQLite in all tests.
    """
    from app.services import paper_store, eval_history, arrow_store
    from app.services import alert_store, pnl_history, webhook_store
    from app.services import exchange_account_store as eas
    import app.api.v1.endpoints.config as config_ep

    paper_store._positions.clear()
    paper_store._loaded = True
    eval_history.clear()
    arrow_store.clear()
    alert_store.clear()
    pnl_history.clear()
    webhook_store.clear()
    eas._configs.clear()
    eas._loaded = False
    config_ep._risk = _default_risk()

    yield

    paper_store._positions.clear()
    eval_history.clear()
    arrow_store.clear()
    alert_store.clear()
    pnl_history.clear()
    webhook_store.clear()
    eas._configs.clear()
    eas._loaded = False
    config_ep._risk = _default_risk()
