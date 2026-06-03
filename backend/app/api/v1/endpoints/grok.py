from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/grok", tags=["grok"])

class GrokConfig(BaseModel):
    dsr_threshold: float
    p_loss_max: float
    wfa_consistency: int
    enable_auto_arbitration: bool
    strict_pearson_dedup: bool
    direction_allow_long: bool
    direction_allow_short: bool
    macro_trend_filter: bool
    risk_percent: float
    max_position_pct: int
    min_rr: float
    max_stop_atr: float
    account_equity: int
    symbols: List[str]
    disabled_symbols: List[str]

_mock_config = GrokConfig(
    dsr_threshold=0.85,
    p_loss_max=15.0,
    wfa_consistency=60,
    enable_auto_arbitration=True,
    strict_pearson_dedup=True,
    direction_allow_long=True,
    direction_allow_short=True,
    macro_trend_filter=True,
    risk_percent=1.0,
    max_position_pct=10,
    min_rr=1.5,
    max_stop_atr=3.0,
    account_equity=10000,
    symbols=['BTC', 'ETH', 'SOL', 'XRP'],
    disabled_symbols=[]
)

@router.get("/config", response_model=GrokConfig)
async def get_grok_config():
    return _mock_config

@router.post("/config", response_model=GrokConfig)
async def update_grok_config(config: GrokConfig):
    global _mock_config
    _mock_config = config
    return _mock_config
