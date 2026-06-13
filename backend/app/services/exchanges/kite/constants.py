"""
Zerodha Kite Connect v3 — protocol constants.

Single source of truth for endpoints, enums and the binary-tick segment maths so
no magic strings/numbers leak into the client, ticker or router.

Docs: https://kite.trade/docs/connect/v3/
"""
from __future__ import annotations

# ─── Endpoints ──────────────────────────────────────────────────────────────
BASE_URL = "https://api.kite.trade"
WS_URL = "wss://ws.kite.trade"
LOGIN_URL_BASE = "https://kite.zerodha.com/connect/login"
KITE_VERSION = "3"
USER_AGENT = "Sterling/1.0"

# ─── Order enums (Kite vocabulary) ──────────────────────────────────────────
# Exchanges / trading segments
EXCHANGE_NSE = "NSE"
EXCHANGE_BSE = "BSE"
EXCHANGE_NFO = "NFO"
EXCHANGE_BFO = "BFO"
EXCHANGE_CDS = "CDS"
EXCHANGE_BCD = "BCD"
EXCHANGE_MCX = "MCX"
EXCHANGES = (EXCHANGE_NSE, EXCHANGE_BSE, EXCHANGE_NFO, EXCHANGE_BFO,
             EXCHANGE_CDS, EXCHANGE_BCD, EXCHANGE_MCX)

# Margin product
PRODUCT_MIS = "MIS"     # intraday
PRODUCT_CNC = "CNC"     # delivery (equity)
PRODUCT_NRML = "NRML"   # carry-forward (F&O / commodity)
PRODUCT_MTF = "MTF"     # margin trading facility
PRODUCTS = (PRODUCT_MIS, PRODUCT_CNC, PRODUCT_NRML, PRODUCT_MTF)

# Order type
ORDER_TYPE_MARKET = "MARKET"
ORDER_TYPE_LIMIT = "LIMIT"
ORDER_TYPE_SL = "SL"        # stop-loss limit
ORDER_TYPE_SLM = "SL-M"     # stop-loss market
ORDER_TYPES = (ORDER_TYPE_MARKET, ORDER_TYPE_LIMIT, ORDER_TYPE_SL, ORDER_TYPE_SLM)

# Order variety (path segment of /orders/{variety})
VARIETY_REGULAR = "regular"
VARIETY_AMO = "amo"
VARIETY_CO = "co"
VARIETY_ICEBERG = "iceberg"
VARIETY_AUCTION = "auction"
VARIETIES = (VARIETY_REGULAR, VARIETY_AMO, VARIETY_CO, VARIETY_ICEBERG, VARIETY_AUCTION)

# Validity
VALIDITY_DAY = "DAY"
VALIDITY_IOC = "IOC"
VALIDITY_TTL = "TTL"
VALIDITIES = (VALIDITY_DAY, VALIDITY_IOC, VALIDITY_TTL)

# Transaction side
TXN_BUY = "BUY"
TXN_SELL = "SELL"

# GTT
GTT_TYPE_SINGLE = "single"
GTT_TYPE_OCO = "two-leg"

# Alerts (native Kite Connect Alerts API)
ALERT_TYPE_SIMPLE = "simple"   # price/attribute threshold → notification
ALERT_TYPE_ATO = "ato"         # alert-triggered order (carries a basket)
ALERT_TYPES = (ALERT_TYPE_SIMPLE, ALERT_TYPE_ATO)
ALERT_OPERATORS = ("<=", ">=", "<", ">", "==")
ALERT_STATUS_ENABLED = "enabled"
ALERT_STATUS_DISABLED = "disabled"
# Common LHS attributes the UI exposes (Kite supports more on the quote object)
ALERT_ATTR_LTP = "LastTradedPrice"

# Position conversion / GTT statuses we treat as "open"
OPEN_ORDER_STATUSES = ("OPEN", "TRIGGER PENDING", "AMO REQ RECEIVED", "MODIFY PENDING")

# ─── Generic resolution → Kite historical interval ──────────────────────────
# Kept name-compatible with the legacy adapter (_RESOLUTION_MAP re-exported).
RESOLUTION_MAP = {
    "1m": "minute",
    "3m": "3minute",
    "5m": "5minute",
    "10m": "10minute",
    "15m": "15minute",
    "30m": "30minute",
    "1H": "60minute",
    "4H": "60minute",   # 4×60min aggregated client-side
    "D": "day",
    "1D": "day",
}
HISTORICAL_INTERVALS = (
    "minute", "3minute", "5minute", "10minute", "15minute",
    "30minute", "60minute", "day",
)

# India VIX instrument token (NSE indices segment)
INDIA_VIX_TOKEN = 264969

# ─── KiteTicker binary protocol ─────────────────────────────────────────────
# Streaming modes
MODE_LTP = "ltp"
MODE_QUOTE = "quote"
MODE_FULL = "full"

# instrument_token & 0xFF → segment. Index & currency segments need special
# price divisors (everything else is paise → /100).
SEGMENT_INDICES = 9
SEGMENT_NSE_CD = 3   # NSE currency
SEGMENT_BSE_CD = 6   # BSE currency

# Packet byte-lengths (see _parse_binary in ticker.py)
PACKET_LTP = 8
PACKET_INDEX_QUOTE = 28
PACKET_INDEX_FULL = 32
PACKET_QUOTE = 44
PACKET_FULL = 184


def price_divisor(instrument_token: int) -> float:
    """Kite quotes prices as integers; the divisor depends on the segment."""
    segment = instrument_token & 0xFF
    if segment == SEGMENT_NSE_CD:
        return 10_000_000.0
    if segment == SEGMENT_BSE_CD:
        return 10_000.0
    return 100.0
