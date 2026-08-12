"""kitelake — an offline, relocatable market-data lake fed from Zerodha Kite.

Storage lives on whatever volume you choose (typically a removable drive); all code and
logic live here inside the Sterling project. The lake is found by identity, not by path,
so moving or unplugging the drive is a normal, recoverable state rather than a crash.

Quickstart::

    kitelake root --pick                 # choose where the data lives (graphical)
    kitelake auth                        # log in to Kite (daily; token expires)
    kitelake instruments                 # sync the instrument master (no auth needed)
    kitelake plan nse-all --interval minute --from 2026-02-13 --to 2026-08-13
    kitelake download nse-all --interval minute --from 2026-02-13 --to 2026-08-13
    kitelake verify && kitelake catalog
    kitelake read RELIANCE --tail 5

See ``kitelake/README.md`` for the operator manual, including what Kite structurally
cannot provide (there is no sub-minute historical data).
"""

from __future__ import annotations

__version__ = "1.0.0"

from .config import (  # noqa: F401
    DEFAULT_RATE,
    INTERVAL_DAY_CAP,
    IST,
    PRICE_SCALE,
    VALID_INTERVALS,
    Credentials,
    CredentialsMissing,
    load_credentials,
)
from .volume import (  # noqa: F401
    LakeStatus,
    LakeUnavailable,
    adopt_root,
    browse,
    lake_status,
    list_volumes,
    resolve_root,
)

__all__ = [
    "__version__",
    # config
    "PRICE_SCALE",
    "IST",
    "VALID_INTERVALS",
    "INTERVAL_DAY_CAP",
    "DEFAULT_RATE",
    "Credentials",
    "CredentialsMissing",
    "load_credentials",
    # volume
    "LakeStatus",
    "LakeUnavailable",
    "lake_status",
    "list_volumes",
    "resolve_root",
    "adopt_root",
    "browse",
]
