from pydantic import BaseModel
from typing import List, Optional


class Candle(BaseModel):
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketSnapshotResponse(BaseModel):
    underlying: str
    spot_price: float
    index_price: float
    perp_price: float
    candles_4h_count: int
    candles_1h_count: int
    candles_15m_count: int
    dvol: Optional[float] = None
    ivr: Optional[float] = None
    data_source: str
    timestamp_ms: int


class OptionSummary(BaseModel):
    instrument_name: str
    underlying: str
    strike: float
    expiry_date: str
    dte: int
    option_type: str  # "call" | "put"
    bid: float
    ask: float
    mark_price: float
    mid_price: float
    mark_iv: float
    delta: float
    open_interest: float
    volume_24h: float
    last_updated_ms: int
    # ── Phase 1 derivatives build: full Greeks vector ──────────────────
    # Optional with sensible defaults so adapters that only ship delta/iv
    # (the legacy Delta India response) still validate. Downstream code
    # uses `enrich_with_greeks(option, spot)` to BSM-fill any field left
    # at the default — see app/engines/risk/option_pricing.py. The
    # extended fields are surfaced in every /options/chain response and
    # consumed by the DerivativesSelector + Greeks budget gate.
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    rho: float = 0.0
    # True once enrich_with_greeks has BSM-filled the missing Greeks. Lets
    # callers distinguish exchange-supplied from computed Greeks for audit.
    greeks_enriched: bool = False
    # Spread as a fraction of mid — pre-computed by the adapter when bid/ask
    # are present. Drives the liquidity_score and microstructure veto.
    # Defaults to 0 so legacy responses validate; aggregate consumers should
    # treat 0 as "unknown" rather than "zero spread".
    spread_pct: float = 0.0
