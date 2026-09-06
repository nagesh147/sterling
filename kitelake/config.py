"""Static configuration: protocol constants, credentials, and config-file locations.

This module holds only values that never depend on *where the data lives*. Path
resolution is deliberately NOT here — it lives in :mod:`kitelake.volume`, because the
lake root is relocatable (removable drive) and must be re-resolved at call time rather
than snapshotted at import.

Every number below was verified against the live Kite Connect v3 API and its docs on
2026-08-12. Do not "tidy" them from memory.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

__all__ = [
    "IST",
    "PRICE_SCALE",
    "VALID_INTERVALS",
    "INTERVAL_DAY_CAP",
    "CONTINUOUS_INTERVALS",
    "HIST_RATE_LIMIT_HARD",
    "DEFAULT_RATE",
    "KITE_BASE",
    "KITE_LOGIN_BASE",
    "INSTRUMENTS_URL",
    "MEASURED_BYTES_PER_BAR",
    "CONFIG_DIR",
    "ROOTS_FILE",
    "SESSION_FILE",
    "DEFAULT_LAKE_DIRNAME",
    "Credentials",
    "CredentialsMissing",
    "load_credentials",
    "save_session",
    "config_dir",
]

# ─── Market/time conventions ─────────────────────────────────────────────────
IST = ZoneInfo("Asia/Kolkata")

#: Prices are stored as ``int64`` = round(rupees * PRICE_SCALE).
#:
#: 1e4 (not 100) because currency derivatives on CDS quote to four decimals
#: (e.g. USDINR at 83.4525); paise would silently truncate them. int64 at this scale
#: still covers ~9.2e10 rupees, far beyond any Indian instrument price.
PRICE_SCALE = 10_000

# ─── Kite Connect v3 protocol constants (VERIFIED 2026-08-12) ────────────────
KITE_BASE = "https://api.kite.trade"
KITE_LOGIN_BASE = "https://kite.zerodha.com/connect/login"
INSTRUMENTS_URL = f"{KITE_BASE}/instruments"
KITE_VERSION = "3"
USER_AGENT = "kitelake/1.0"

#: The only intervals the historical API accepts. There is **no** sub-minute
#: historical interval — second/tick data exists solely on the live WebSocket.
VALID_INTERVALS: tuple[str, ...] = (
    "minute",
    "3minute",
    "5minute",
    "10minute",
    "15minute",
    "30minute",
    "60minute",
    "day",
)

#: Intervals the API will serve with ``continuous=1``. Measured against the live API
#: on 2026-09-07: only ``day`` is accepted; every other interval answers
#: ``"invalid interval for continuous data" (HTTP 400, InputException)``.
#:
#: This matters more than it looks. Continuous is the ONLY way to see a futures series
#: from before the current contract's inception — Kite refuses history for an expired
#: contract even when you know its token (``"invalid token"``, also measured). So
#: futures history is deep at ``day`` and about three months at any intraday interval,
#: and asking for a continuous minute series is not a slow path, it is an impossible one.
CONTINUOUS_INTERVALS: frozenset[str] = frozenset({"day"})

#: Maximum span (in days) the API will serve in ONE historical request, per interval.
#: Exceeding these yields a 400 InputException, so the chunker must respect them.
INTERVAL_DAY_CAP: dict[str, int] = {
    "minute": 60,
    "3minute": 100,
    "5minute": 100,
    "10minute": 100,
    "15minute": 200,
    "30minute": 200,
    "60minute": 400,
    "day": 2000,
}

#: Hard server-side ceiling for the historical endpoint: 3 requests/second.
HIST_RATE_LIMIT_HARD = 3.0

#: What we actually ask for by default. Deliberately under the ceiling: bursting to
#: exactly 3.0 rq/s trips 429s on clock jitter, and repeated 429s risk the API key.
DEFAULT_RATE = 2.5

#: Measured, not guessed: bytes-per-row for zstd-9 compressed int64 OHLCV parquet,
#: benchmarked on 46,500 synthetic minute bars (a maximally incompressible random
#: walk, so this is a conservative upper bound for real data).
MEASURED_BYTES_PER_BAR = 17.6

#: Interval used for bars derived from recorded ticks (not a Kite interval).
SECOND_INTERVAL = "second"

# ─── Where *our own* config lives (never on the removable volume) ─────────────
#: Config must survive the data volume being unplugged, so it lives in the user's
#: home config dir, not in the lake.
DEFAULT_LAKE_DIRNAME = "SterlingLake"


def config_dir() -> Path:
    """Return the kitelake config directory, honouring ``XDG_CONFIG_HOME``."""
    base = os.environ.get("KITELAKE_CONFIG_DIR")
    if base:
        return Path(base).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    root = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return root / "kitelake"


CONFIG_DIR = config_dir()
ROOTS_FILE = CONFIG_DIR / "roots.json"
SESSION_FILE = CONFIG_DIR / "session.json"


# ─── Credentials ─────────────────────────────────────────────────────────────
class CredentialsMissing(RuntimeError):
    """Raised when no usable Kite api_key/access_token could be found."""


@dataclass(frozen=True)
class Credentials:
    """A Kite API key plus a live access token.

    ``access_token`` is short-lived: Kite invalidates it every morning, so a stored
    session is expected to need refreshing daily via ``kitelake auth``.
    """

    api_key: str
    access_token: str

    def auth_header(self) -> dict[str, str]:
        return {
            "Authorization": f"token {self.api_key}:{self.access_token}",
            "X-Kite-Version": KITE_VERSION,
            "User-Agent": USER_AGENT,
        }

    def __repr__(self) -> str:  # pragma: no cover - defensive
        # Never let a token reach a log line, traceback, or event payload.
        return f"Credentials(api_key='***{self.api_key[-4:]}', access_token='<redacted>')"


_MISSING_MSG = """No Kite credentials found.

kitelake needs an api_key and a live access_token to read historical candles.
Provide them in any ONE of these ways:

  1. Run the login flow (recommended, stores a 0600 session file):
         kitelake auth
  2. Export them for this shell:
         export KITE_API_KEY=xxxxxxxx
         export KITE_ACCESS_TOKEN=yyyyyyyy

Note: the historical-candle endpoint also requires the paid "historical data"
subscription on your Kite Connect app — an app without it returns 403 even with a
perfectly valid token."""


def load_credentials(
    api_key: str | None = None,
    access_token: str | None = None,
) -> Credentials:
    """Resolve credentials from explicit args, then env, then the session file.

    Raises:
        CredentialsMissing: with actionable remediation text, never a bare KeyError.
    """
    key = api_key or os.environ.get("KITE_API_KEY") or ""
    token = access_token or os.environ.get("KITE_ACCESS_TOKEN") or ""

    if not (key and token):
        path = config_dir() / "session.json"
        if path.exists():
            try:
                blob = json.loads(path.read_text())
                key = key or str(blob.get("api_key") or "")
                token = token or str(blob.get("access_token") or "")
            except (OSError, ValueError):
                # A corrupt session file is equivalent to no session file.
                pass

    if not (key and token):
        raise CredentialsMissing(_MISSING_MSG)
    return Credentials(api_key=key, access_token=token)


def have_credentials() -> bool:
    """True if credentials can be resolved. Never raises."""
    try:
        load_credentials()
        return True
    except CredentialsMissing:
        return False


def save_session(api_key: str, access_token: str, *, user_id: str = "") -> Path:
    """Persist a session to ``$CONFIG/session.json`` with 0600 permissions.

    The file is written with restrictive permissions *before* the secret goes in
    (``os.open`` with mode 0600), so there is no window where a token sits in a
    world-readable file.
    """
    from datetime import datetime, timezone

    path = config_dir() / "session.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "api_key": api_key,
            "access_token": access_token,
            "user_id": user_id,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        },
        indent=2,
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, payload.encode())
    finally:
        os.close(fd)
    os.chmod(path, 0o600)  # enforce even if the file pre-existed with looser mode
    return path
