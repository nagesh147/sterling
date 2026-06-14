"""
Kite error taxonomy + human-readable mapping.

Kite returns ``{"status": "error", "message": "...", "error_type": "..."}`` with a
known set of ``error_type`` values. We translate those into a small exception
hierarchy + friendly messages so the API/UI never surface a raw 4xx/5xx.
"""
from __future__ import annotations

from typing import Optional


class KiteError(RuntimeError):
    """Base error for all Kite interactions."""

    def __init__(self, message: str, error_type: str = "", status_code: Optional[int] = None,
                 data: Optional[dict] = None):
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code
        # Kite's error envelope `data` (e.g. {"hints": ["switch_to_amo"]}) — kept so
        # callers can react (the order path auto-converts to AMO on that hint).
        self.data = data if isinstance(data, dict) else {}

    @property
    def hints(self) -> list:
        h = self.data.get("hints")
        return h if isinstance(h, list) else []


class KiteTokenError(KiteError):
    """Session/access_token invalid or expired — user must re-login."""


class KitePermissionError(KiteError):
    """API key lacks permission for the requested resource."""


class KiteMarginError(KiteError):
    """Insufficient funds/margin for the order."""


class KiteOrderError(KiteError):
    """Order rejected / invalid order parameters."""


class KiteInputError(KiteError):
    """Malformed request / bad parameters."""


class KiteNetworkError(KiteError):
    """Upstream OMS/exchange/network failure."""


# error_type → (exception class, friendly default message)
_ERROR_MAP = {
    "TokenException": (KiteTokenError, "Kite session expired — reconnect via the login flow."),
    "PermissionException": (KitePermissionError, "Your API key is not permitted to do this."),
    "MarginException": (KiteMarginError, "Insufficient funds/margin for this order."),
    "OrderException": (KiteOrderError, "Order was rejected by the exchange."),
    "InputException": (KiteInputError, "Invalid request parameters."),
    "NetworkException": (KiteNetworkError, "Exchange/OMS network error — please retry."),
    "GeneralException": (KiteError, "Kite request failed."),
    "DataException": (KiteError, "Kite returned bad/again-try data."),
}


def raise_for_kite(message: str, error_type: str = "", status_code: Optional[int] = None,
                   data: Optional[dict] = None) -> None:
    """Raise the most specific KiteError subclass for a Kite error envelope."""
    cls, default = _ERROR_MAP.get(error_type, (KiteError, "Kite request failed."))
    raise cls(message or default, error_type=error_type, status_code=status_code, data=data)
