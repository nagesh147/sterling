"""
Backwards-compat shim.

The Zerodha Kite adapter has graduated into a full, order-capable, multi-tenant
package at ``app.services.exchanges.kite``. This module preserves the historical
import path (``ZerodhaAdapter``, ``_parse_kite_ts``, ``_RESOLUTION_MAP``) used by
the adapter factory, registry and existing tests.
"""
from app.services.exchanges.kite.client import (  # noqa: F401
    KiteClient as ZerodhaAdapter,
    _parse_kite_ts,
    _RESOLUTION_MAP,
)

__all__ = ["ZerodhaAdapter", "_parse_kite_ts", "_RESOLUTION_MAP"]
