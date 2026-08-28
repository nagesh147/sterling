"""The BSE Ltd 29-Sep-2026 chain that motivated this engine.

Numbers transcribed from the chain screenshot at spot 3392.50 / +1.94%.
OI is lot-count as the UI showed it.
"""
from __future__ import annotations

import pytest

from app.engines.oi_wall_flow import ChainRow, ChainSnapshot, OIWallFlowConfig

# strike, call_oi, call_oi_chg, call_ltp, call_ltp_chg, put_ltp, put_ltp_chg, put_oi, put_oi_chg
BSE_ROWS = (
    (2600, 16, 0.00, 753.62, 1.85, 3.00, -22.08, 507, 0.00),
    (2800, 29, -3.33, 619.50, 11.69, 6.85, -12.74, 1895, 6.10),
    (2900, 102, 6.25, 508.50, 10.64, 9.95, -19.76, 827, 2.61),
    (3000, 370, -11.48, 429.00, 15.70, 15.35, -27.08, 2593, 14.68),
    (3100, 445, -5.32, 344.80, 20.16, 25.15, -30.04, 2630, 6.82),
    (3200, 1290, -2.79, 261.90, 23.60, 41.95, -31.00, 2998, 2.22),
    (3300, 4442, -6.80, 186.70, 24.18, 68.50, -30.35, 5281, 13.11),
    (3400, 6109, -8.48, 128.65, 25.70, 109.00, -26.94, 2973, 7.48),
    (3500, 8136, -2.02, 84.15, 25.22, 164.70, -22.88, 4048, -1.24),
    (3600, 5013, 7.53, 52.00, 22.35, 232.30, -18.99, 1189, -5.78),
    (3700, 3511, -13.09, 31.65, 18.76, 314.90, -15.27, 919, 1.88),
    (3800, 4382, 47.94, 19.10, 12.35, 394.00, -14.54, 601, -1.48),
    (3900, 999, -3.94, 12.10, 8.52, 495.00, -14.66, 183, 0.00),
    (4000, 3855, 1.34, 8.25, 6.45, 581.05, -12.19, 668, -0.60),
    (4200, 1445, -4.37, 4.10, -5.75, 783.00, -7.71, 268, 0.75),
)


def rows_from(raw=BSE_ROWS):
    return [
        ChainRow(strike=s, call_oi=coi, call_oi_chg_pct=coic, call_ltp=cltp,
                 call_ltp_chg_pct=cltpc, put_ltp=pltp, put_ltp_chg_pct=pltpc,
                 put_oi=poi, put_oi_chg_pct=poic)
        for s, coi, coic, cltp, cltpc, pltp, pltpc, poi, poic in raw
    ]


@pytest.fixture
def bse_rows():
    return rows_from()


@pytest.fixture
def bse_snap(bse_rows):
    return ChainSnapshot(
        underlying="BSE",
        spot=3392.50,
        expiry="2026-09-29",
        rows=bse_rows,
        at_ms=1_788_000_000_000,
        days_to_expiry=32,
        lot_size=200,
        tick_size=0.05,
        exchange="NFO",
    )


@pytest.fixture
def cfg():
    return OIWallFlowConfig(max_premium_at_risk_inr=50_000).validate()
