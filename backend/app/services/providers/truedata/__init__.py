"""TrueData Market Data Provider package."""
from app.services.market_data.truedata import (
    TrueDataAuthError,
    TrueDataError,
    TrueDataHistoricalClient,
    TrueDataNoDataError,
)

from .adapter import TrueDataMarketDataAdapter
from .config import DEFAULT_CONFIG, TrueDataProviderConfig
from .credentials import (
    add,
    bootstrap,
    build_client,
    clear,
    delete,
    get,
    get_active,
    list_credentials,
    save_session,
    to_response,
    update,
)
from .models import (
    TrueDataCredentialCreate,
    TrueDataCredentialResponse,
    TrueDataCredentialUpdate,
    TrueDataStatus,
)
from .ws_client import SingleStreamConflictError, TrueDataStreamManager, STREAM_MANAGER

__all__ = [
    "TrueDataError",
    "TrueDataAuthError",
    "TrueDataNoDataError",
    "TrueDataHistoricalClient",
    "TrueDataMarketDataAdapter",
    "TrueDataProviderConfig",
    "DEFAULT_CONFIG",
    "TrueDataCredentialCreate",
    "TrueDataCredentialUpdate",
    "TrueDataCredentialResponse",
    "TrueDataStatus",
    "add",
    "get",
    "get_active",
    "list_credentials",
    "update",
    "delete",
    "save_session",
    "to_response",
    "build_client",
    "bootstrap",
    "clear",
    "SingleStreamConflictError",
    "TrueDataStreamManager",
    "STREAM_MANAGER",
]
