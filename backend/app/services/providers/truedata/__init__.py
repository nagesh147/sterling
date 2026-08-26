"""TrueData Market Data Provider package."""
from app.services.market_data.truedata import (
    TrueDataAuthError,
    TrueDataError,
    TrueDataHistoricalClient,
    TrueDataNoDataError,
)

from .adapter import TrueDataMarketDataAdapter
from .bar_history import BarAcquisitionResult, BarHistoryAcquirer, bars_to_canonical_sequence
from .bar_store import BarStore
from .tick_history import (
    TickAcquisitionResult,
    TickHistoryAcquirer,
    format_history_timestamp,
    nse_session_chunks,
    ticks_to_canonical_sequence,
)
from .tick_store import TickStore
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
from .diagnostics import (
    DiagnosticCategoryResult,
    DiagnosticFieldCheck,
    DiagnosticSuiteResult,
    run_truedata_diagnostics,
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
    "TickStore",
    "TickHistoryAcquirer",
    "TickAcquisitionResult",
    "BarStore",
    "BarHistoryAcquirer",
    "BarAcquisitionResult",
    "bars_to_canonical_sequence",
    "format_history_timestamp",
    "nse_session_chunks",
    "ticks_to_canonical_sequence",
    "TrueDataProviderConfig",
    "DEFAULT_CONFIG",
    "TrueDataCredentialCreate",
    "TrueDataCredentialUpdate",
    "TrueDataCredentialResponse",
    "TrueDataStatus",
    "DiagnosticFieldCheck",
    "DiagnosticCategoryResult",
    "DiagnosticSuiteResult",
    "run_truedata_diagnostics",
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
