"""Fetching historical candles: chunking, retries, and error classification.

Two things in here decide whether a 40,000-request download succeeds or quietly corrupts
itself.

**1. :func:`chunk_range`.** The API serves at most 60 days of minute bars per request, so
a 6-month pull is split into 4 chunks. An off-by-one here does not crash — it silently
drops or double-fetches a trading day, and you find out months later when a backtest
disagrees with reality. Chunks are inclusive on both ends, contiguous, non-overlapping,
and the last one ends exactly on the requested end date.

**2. Error classification.** Verified against the live API on 2026-08-12: a missing or
expired credential comes back as **HTTP 400 InputException** with the message
``"Invalid `api_key` or `access_token`."`` — *not* 403 as the docs' exception table
implies. That distinction is load-bearing. If a dead token were classified as an ordinary
per-chunk input error, a resumed run would mark all 40,000 chunks ``failed`` and then skip
them forever, leaving a permanently incomplete lake that looks finished. So anything that
smells like a credential problem raises :class:`KitelakeAuthError`, which aborts the whole
run on the first occurrence.
"""

from __future__ import annotations

import asyncio
import random
import re
from datetime import date, timedelta
from typing import Any, Callable, Sequence

import httpx

from .calendar_ import session_bounds
from .config import (
    DEFAULT_RATE,
    INTERVAL_DAY_CAP,
    KITE_BASE,
    KITE_VERSION,
    USER_AGENT,
    Credentials,
    VALID_INTERVALS,
)
from .ratelimit import AdaptiveLimiter

__all__ = [
    "chunk_range",
    "KitelakeError",
    "KitelakeFatal",
    "KitelakeAuthError",
    "KitelakePermissionError",
    "KitelakeInputError",
    "KitelakeRateLimited",
    "KitelakeTransportError",
    "KiteHistoricalFetcher",
]


# ─── Errors ──────────────────────────────────────────────────────────────────
class KitelakeError(RuntimeError):
    """Base for fetch failures."""


class KitelakeFatal(KitelakeError):
    """Unrecoverable for the *whole run* — retrying other chunks cannot help."""


class KitelakeAuthError(KitelakeFatal):
    """Missing, invalid, or expired api_key/access_token."""


class KitelakePermissionError(KitelakeFatal):
    """Authenticated, but this app is not entitled to historical data."""


class KitelakeInputError(KitelakeError):
    """This particular request was malformed or unsupported. Not retried."""


class KitelakeRateLimited(KitelakeError):
    """429 — too many requests. Retried after backoff."""


class KitelakeTransportError(KitelakeError):
    """Network/5xx problem. Retried."""


# ─── Chunking ────────────────────────────────────────────────────────────────
def chunk_range(frm: date, to: date, interval: str) -> list[tuple[date, date]]:
    """Split ``[frm, to]`` (inclusive) into request-sized, contiguous chunks.

    Guarantees, all covered by tests:

    - every chunk spans at most ``INTERVAL_DAY_CAP[interval]`` calendar days
    - ``chunks[0][0] == frm`` and ``chunks[-1][1] == to``
    - ``chunks[i+1][0] == chunks[i][1] + 1 day`` — no gaps, no overlaps
    """
    if interval not in VALID_INTERVALS:
        raise ValueError(
            f"invalid interval {interval!r}; expected one of {', '.join(VALID_INTERVALS)}"
        )
    if to < frm:
        raise ValueError(f"'to' ({to}) is before 'from' ({frm})")
    cap = INTERVAL_DAY_CAP[interval]
    out: list[tuple[date, date]] = []
    start = frm
    while start <= to:
        # cap - 1 because both endpoints are inclusive: start..start+59 is 60 days.
        end = min(to, start + timedelta(days=cap - 1))
        out.append((start, end))
        start = end + timedelta(days=1)
    return out


# ─── Response classification ─────────────────────────────────────────────────
#: Messages that mean "your credentials are the problem", whatever the HTTP code.
_AUTH_HINTS = re.compile(
    r"api_key|access_token|token\s*exception|invalid\s+session|expired", re.IGNORECASE
)
_PERMISSION_HINTS = re.compile(
    r"not\s+(?:subscribed|entitled|authorised|authorized)|permission|insufficient\s+permission|"
    r"historical.*(?:subscription|plan)",
    re.IGNORECASE,
)


def _classify(status: int, message: str, error_type: str) -> KitelakeError:
    """Map an API error onto our taxonomy, prioritising 'is this fatal?'."""
    msg = message or f"HTTP {status}"
    etype = error_type or ""

    if etype == "TokenException" or _AUTH_HINTS.search(msg):
        return KitelakeAuthError(
            f"{msg} (HTTP {status}, {etype or 'no error_type'})\n"
            "Your Kite session is missing or expired. Refresh it with `kitelake auth` "
            "(tokens expire every morning), then resume — completed chunks are not re-fetched."
        )
    if status == 403 or etype == "PermissionException" or _PERMISSION_HINTS.search(msg):
        return KitelakePermissionError(
            f"{msg} (HTTP {status}, {etype or 'no error_type'})\n"
            "The credentials work but this Kite Connect app is not entitled to historical "
            "candles. That is a paid add-on — enable it on the app, then resume."
        )
    if status == 429:
        return KitelakeRateLimited(f"{msg} (HTTP 429)")
    if status == 400:
        return KitelakeInputError(f"{msg} (HTTP 400, {etype or 'no error_type'})")
    if status >= 500:
        return KitelakeTransportError(f"{msg} (HTTP {status})")
    return KitelakeError(f"{msg} (HTTP {status}, {etype or 'no error_type'})")


# ─── Fetcher ─────────────────────────────────────────────────────────────────
class KiteHistoricalFetcher:
    """Async client for ``/instruments/historical/:token/:interval``.

    One shared :class:`~kitelake.ratelimit.AdaptiveLimiter` gates every request, so the
    3 rq/s ceiling holds no matter how many workers call :meth:`fetch_chunk`.
    """

    def __init__(
        self,
        creds: Credentials,
        *,
        limiter: AdaptiveLimiter | None = None,
        rate: float = DEFAULT_RATE,
        timeout: float = 30.0,
        max_attempts: int = 5,
        transport: httpx.AsyncBaseTransport | None = None,
        base_url: str = KITE_BASE,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._creds = creds
        self.limiter = limiter or AdaptiveLimiter(rate)
        self._timeout = timeout
        self._max_attempts = max(1, int(max_attempts))
        self._transport = transport
        self._base_url = base_url
        self._on_event = on_event
        self._client: httpx.AsyncClient | None = None
        self.requests_made = 0

    # ─── lifecycle ───────────────────────────────────────────────────────────
    async def __aenter__(self) -> "KiteHistoricalFetcher":
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
            headers={"X-Kite-Version": KITE_VERSION, "User-Agent": USER_AGENT},
            limits=httpx.Limits(max_keepalive_connections=8, max_connections=16),
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _emit(self, **payload: Any) -> None:
        if self._on_event:
            # Payloads reach a JSONL log on disk; credentials must never appear here.
            self._on_event(payload)

    # ─── the request ─────────────────────────────────────────────────────────
    @staticmethod
    def _fmt(day: date, exchange: str, *, end: bool) -> str:
        """Frame a chunk boundary at the session edge, in IST, as Kite expects."""
        opened, closed = session_bounds(day, exchange)
        stamp = closed if end else opened
        return stamp.strftime("%Y-%m-%d %H:%M:%S")

    async def fetch_chunk(
        self,
        token: int,
        interval: str,
        frm: date,
        to: date,
        *,
        continuous: bool = False,
        oi: bool = False,
        exchange: str = "NSE",
    ) -> list[list[Any]]:
        """Fetch one chunk's candles. Returns ``[]`` when the API has no data.

        An empty list is a normal answer — illiquid instruments and pre-listing windows
        both produce it — and callers must not treat it as failure.
        """
        if self._client is None:
            raise RuntimeError("use KiteHistoricalFetcher as an async context manager")

        path = f"/instruments/historical/{int(token)}/{interval}"
        params = {
            "from": self._fmt(frm, exchange, end=False),
            "to": self._fmt(to, exchange, end=True),
            "continuous": 1 if continuous else 0,
            "oi": 1 if oi else 0,
        }

        last_error: KitelakeError | None = None
        for attempt in range(1, self._max_attempts + 1):
            await self.limiter.acquire()
            try:
                resp = await self._client.get(path, params=params, headers=self._creds.auth_header())
                self.requests_made += 1
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = KitelakeTransportError(f"{type(exc).__name__}: {exc}")
            else:
                outcome = self._read(resp)
                if isinstance(outcome, list):
                    self.limiter.reward()
                    return outcome
                last_error = outcome
                if isinstance(last_error, KitelakeFatal):
                    # A dead token or missing entitlement will not fix itself; failing
                    # fast keeps us from hammering the API 40,000 more times.
                    raise last_error
                if isinstance(last_error, KitelakeInputError):
                    raise last_error  # malformed request: retrying is pointless
                if isinstance(last_error, KitelakeRateLimited):
                    self.limiter.penalize()

            if attempt >= self._max_attempts:
                break
            # Exponential backoff with full jitter, so N workers that all got 429 do not
            # retry in lockstep and immediately trip the limit again.
            delay = min(30.0, 0.75 * (2 ** (attempt - 1)))
            delay = random.uniform(delay * 0.5, delay)
            self._emit(
                event="retry", token=int(token), interval=interval, attempt=attempt,
                delay=round(delay, 2), error=str(last_error)[:200],
                rate=round(self.limiter.current_rate, 2),
            )
            await asyncio.sleep(delay)

        raise last_error or KitelakeError("exhausted retries with no recorded error")

    @staticmethod
    def _read(resp: httpx.Response) -> list[list[Any]] | KitelakeError:
        """Unwrap Kite's ``{status, data:{candles}}`` envelope or classify the failure."""
        try:
            body = resp.json()
        except ValueError:
            if resp.is_success:
                return KitelakeTransportError(
                    f"non-JSON body from {resp.request.url.path} (HTTP {resp.status_code})"
                )
            return _classify(resp.status_code, resp.text[:200], "")

        if isinstance(body, dict) and body.get("status") == "error":
            return _classify(
                resp.status_code, str(body.get("message") or ""), str(body.get("error_type") or "")
            )
        if not resp.is_success:
            msg = body.get("message") if isinstance(body, dict) else str(body)[:200]
            etype = body.get("error_type", "") if isinstance(body, dict) else ""
            return _classify(resp.status_code, str(msg or ""), str(etype))

        data = body.get("data") if isinstance(body, dict) else None
        candles = (data or {}).get("candles") if isinstance(data, dict) else None
        if candles is None:
            return []
        if not isinstance(candles, list):
            return KitelakeTransportError(f"unexpected candles payload type {type(candles).__name__}")
        return candles
