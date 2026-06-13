"""
Pydantic models for the Kite integration.

Read endpoints (quotes, holdings, instruments) pass Kite's rich native shapes
through as dicts; the typed models here cover the surfaces we own — multi-tenant
account CRUD, the session result, and the write request bodies — so the router and
clients stay strongly typed where it matters (orders, GTT, credentials).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from . import constants as K


# ─── Multi-tenant account CRUD ──────────────────────────────────────────────
class KiteAccountCreate(BaseModel):
    label: str = Field("My Kite", description="Friendly name for this Kite account")
    api_key: str = Field(..., description="Kite Connect API key (permanent)")
    api_secret: str = Field(..., description="Kite Connect API secret (used for login checksum)")
    is_paper: bool = True


class KiteAccountUpdate(BaseModel):
    label: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    is_paper: Optional[bool] = None


class KiteAccountResponse(BaseModel):
    """Account view — secrets are NEVER returned, only a masked hint."""
    id: str
    user_id: str
    label: str
    api_key_hint: str
    has_credentials: bool
    is_paper: bool
    is_active: bool
    connected: bool                       # access_token present
    kite_user_id: Optional[str] = None    # Zerodha user id once logged in
    last_login_at_ms: Optional[int] = None
    created_at_ms: int
    updated_at_ms: int


class KiteAccountListResponse(BaseModel):
    accounts: List[KiteAccountResponse]
    active_id: Optional[str]
    count: int


# ─── Session / status ───────────────────────────────────────────────────────
class LoginUrlResponse(BaseModel):
    login_url: str


class GenerateSessionRequest(BaseModel):
    request_token: str
    account_id: Optional[str] = None      # default: active account for the user


class RefreshSessionRequest(BaseModel):
    """Renew the access_token from a refresh_token (no full re-login). When
    ``refresh_token`` is omitted, the one captured at login is used."""
    refresh_token: Optional[str] = None
    account_id: Optional[str] = None


class KiteSessionResult(BaseModel):
    connected: bool
    kite_user_id: Optional[str] = None
    user_name: Optional[str] = None
    email: Optional[str] = None
    login_time: Optional[str] = None


class KiteStatus(BaseModel):
    connected: bool
    is_paper: bool
    account_id: Optional[str] = None
    kite_user_id: Optional[str] = None
    user_name: Optional[str] = None
    message: str = ""


# ─── Write request bodies ───────────────────────────────────────────────────
class PlaceOrderRequest(BaseModel):
    tradingsymbol: str                    # e.g. "INFY", "NIFTY25JAN25000CE"
    exchange: str = K.EXCHANGE_NSE        # NSE/BSE/NFO/...
    transaction_type: str = K.TXN_BUY     # BUY/SELL
    quantity: int = 1
    order_type: str = K.ORDER_TYPE_MARKET  # MARKET/LIMIT/SL/SL-M
    product: str = K.PRODUCT_MIS          # MIS/CNC/NRML
    variety: str = K.VARIETY_REGULAR      # regular/amo/co/iceberg
    price: Optional[float] = None         # for LIMIT/SL
    trigger_price: Optional[float] = None  # for SL/SL-M
    validity: str = K.VALIDITY_DAY        # DAY/IOC/TTL
    disclosed_quantity: Optional[int] = None
    validity_ttl: Optional[int] = None    # minutes, when validity=TTL
    iceberg_legs: Optional[int] = None
    iceberg_quantity: Optional[int] = None
    tag: Optional[str] = None             # ≤20 chars audit tag


class ModifyOrderRequest(BaseModel):
    variety: str = K.VARIETY_REGULAR
    quantity: Optional[int] = None
    price: Optional[float] = None
    order_type: Optional[str] = None
    trigger_price: Optional[float] = None
    validity: Optional[str] = None
    disclosed_quantity: Optional[int] = None


class GttLeg(BaseModel):
    tradingsymbol: str
    exchange: str = K.EXCHANGE_NSE
    transaction_type: str = K.TXN_BUY
    quantity: int = 1
    order_type: str = K.ORDER_TYPE_LIMIT
    product: str = K.PRODUCT_CNC
    price: float = 0.0


class PlaceGttRequest(BaseModel):
    trigger_type: str = K.GTT_TYPE_SINGLE   # single | two-leg (OCO)
    tradingsymbol: str
    exchange: str = K.EXCHANGE_NSE
    last_price: float                       # current LTP (required by Kite)
    trigger_values: List[float]             # [t] for single, [lower, upper] for OCO
    orders: List[GttLeg]


class HoldingAuthLeg(BaseModel):
    isin: str
    quantity: Optional[float] = None


class InitiateHoldingsAuthRequest(BaseModel):
    """Optional ISIN/quantity scoping for CDSL holdings authorisation (eDIS).
    Empty list = blanket authorisation of all holdings."""
    instruments: List[HoldingAuthLeg] = Field(default_factory=list)


# ─── Mutual fund SIPs ───────────────────────────────────────────────────────
class PlaceMfSipRequest(BaseModel):
    tradingsymbol: str                      # fund ISIN / Kite MF symbol
    amount: float
    instalments: int = -1                   # -1 = until cancelled
    frequency: str = "monthly"              # weekly | monthly | quarterly
    initial_amount: Optional[float] = None  # optional one-time first purchase


class ModifyMfSipRequest(BaseModel):
    amount: Optional[float] = None
    frequency: Optional[str] = None
    instalments: Optional[int] = None
    instalment_day: Optional[int] = None
    status: Optional[str] = None            # active | paused (pause/resume)


# ─── Alerts (native Kite Connect Alerts API) ────────────────────────────────
class CreateAlertRequest(BaseModel):
    name: str
    lhs_exchange: str = K.EXCHANGE_NSE
    lhs_tradingsymbol: str
    lhs_attribute: str = K.ALERT_ATTR_LTP   # e.g. LastTradedPrice
    operator: str = ">="                    # <= >= < > ==
    rhs_constant: Optional[float] = None     # threshold (rhs_type=constant)
    alert_type: str = K.ALERT_TYPE_SIMPLE   # simple | ato
    rhs_type: str = "constant"              # constant | instrument
    rhs_exchange: Optional[str] = None
    rhs_tradingsymbol: Optional[str] = None
    rhs_attribute: Optional[str] = None
    basket: Optional[List[dict]] = None     # order legs for an ATO alert


class ModifyAlertRequest(BaseModel):
    name: Optional[str] = None
    lhs_exchange: Optional[str] = None
    lhs_tradingsymbol: Optional[str] = None
    lhs_attribute: Optional[str] = None
    operator: Optional[str] = None
    rhs_constant: Optional[float] = None
    alert_type: Optional[str] = Field(default=None, alias="type")
    rhs_type: Optional[str] = None
    rhs_exchange: Optional[str] = None
    rhs_tradingsymbol: Optional[str] = None
    rhs_attribute: Optional[str] = None
    basket: Optional[List[dict]] = None
    status: Optional[str] = None            # enabled | disabled

    model_config = {"populate_by_name": True}


class DeleteAlertsRequest(BaseModel):
    uuids: List[str]


class ConvertPositionRequest(BaseModel):
    tradingsymbol: str
    exchange: str = K.EXCHANGE_NSE
    transaction_type: str = K.TXN_BUY
    position_type: str = "day"              # day | overnight
    quantity: int = 1
    old_product: str = K.PRODUCT_MIS
    new_product: str = K.PRODUCT_CNC


class MarginOrderLeg(BaseModel):
    exchange: str = K.EXCHANGE_NSE
    tradingsymbol: str
    transaction_type: str = K.TXN_BUY
    variety: str = K.VARIETY_REGULAR
    product: str = K.PRODUCT_MIS
    order_type: str = K.ORDER_TYPE_MARKET
    quantity: int = 1
    price: float = 0.0
    trigger_price: float = 0.0


# ─── Ticker subscription ────────────────────────────────────────────────────
class TickerSubscribeRequest(BaseModel):
    instrument_tokens: List[int]
    mode: str = K.MODE_QUOTE               # ltp | quote | full


# ─── Generic envelope ───────────────────────────────────────────────────────
class OkResponse(BaseModel):
    ok: bool = True
    data: Optional[Dict[str, Any]] = None
    message: str = ""
