from __future__ import annotations

import csv
import io
import time
from dataclasses import dataclass
from typing import Any, Mapping

import httpx


class TrueDataError(RuntimeError):
    """Base error for the TrueData adapter."""


class TrueDataAuthError(TrueDataError):
    """Authentication failed."""


class TrueDataNoDataError(TrueDataError):
    """TrueData reported that no data exists for the requested scope."""


class TrueDataSpecificationBlocked(TrueDataError):
    """The source lists an API but does not define its request contract."""


@dataclass(frozen=True)
class TrueDataToken:
    access_token: str
    token_type: str
    expires_at: float


class TrueDataHistoricalClient:
    """TrueData V2.6 historical REST adapter plus documented master APIs."""

    AUTH_URL = "https://auth.truedata.in/token"
    HISTORY_BASE_URL = "https://history.truedata.in"
    MARKET_API_BASE_URL = "https://api.truedata.in"

    # The supplied V2.6 document literally specifies this value as
    # ``passoword``. Do not silently replace it with an inferred value.
    DOCUMENTED_GRANT_TYPE = "passoword"

    TICK_PER_SECOND = 5
    TICK_PER_MINUTE = 300
    TICK_PER_HOUR = 18000
    BAR_PER_SECOND = 10
    BAR_PER_MINUTE = 600
    BAR_PER_HOUR = 18000

    DOCUMENTED_BAR_INTERVALS = {
        "1min",
        "2min",
        "3min",
        "5min",
        "10min",
        "15min",
        "30min",
        "60min",
    }
    DOCUMENTED_LAST_N_BAR_INTERVALS = {
        "1min",
        "2min",
        "3min",
        "5min",
        "15min",
        "30min",
        "60min",
        "eod",
    }

    def __init__(
        self,
        username: str,
        password: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        if not username or not password:
            raise ValueError("TrueData username and password are required")
        self._username = username
        self._password = password
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None
        self._token: TrueDataToken | None = None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def authenticate(self) -> TrueDataToken:
        response = await self._client.post(
            self.AUTH_URL,
            data={
                "username": self._username,
                "password": self._password,
                "grant_type": self.DOCUMENTED_GRANT_TYPE,
            },
        )
        payload = self._json(response)
        if response.status_code >= 400 and payload.get("error") == "unsupported_grant_type":
            # Documented PDF specifies "passoword", but live OAuth server expects "password"
            response = await self._client.post(
                self.AUTH_URL,
                data={
                    "username": self._username,
                    "password": self._password,
                    "grant_type": "password",
                },
            )
            payload = self._json(response)

        if response.status_code >= 400 or "access_token" not in payload:
            detail = payload.get("error_description") or payload.get("error") or response.text
            raise TrueDataAuthError(str(detail))

        expires_in = float(payload.get("expires_in", 3600))
        self._token = TrueDataToken(
            access_token=str(payload["access_token"]),
            token_type=str(payload.get("token_type", "bearer")),
            expires_at=time.time() + expires_in,
        )
        return self._token

    async def _headers(self) -> dict[str, str]:
        if self._token is None or time.time() >= self._token.expires_at:
            await self.authenticate()
        assert self._token is not None
        return {"Authorization": f"bearer {self._token.access_token}"}

    async def _history_get(self, path: str, params: Mapping[str, Any]) -> httpx.Response:
        response = await self._client.get(
            f"{self.HISTORY_BASE_URL}{path}",
            params=dict(params),
            headers=await self._headers(),
        )
        self._raise_history_error(response)
        return response

    async def get_ticks(
        self,
        symbol: str,
        start: str,
        end: str,
        *,
        bidask: int = 0,
        response_format: str = "csv",
    ) -> list[dict[str, Any]]:
        response = await self._history_get(
            "/getticks",
            {
                "symbol": symbol,
                "bidask": bidask,
                "from": start,
                "to": end,
                "response": response_format,
            },
        )
        return self._records(
            response,
            response_format,
            ("timestamp", "ltp", "volume", "oi", "bid", "bidqty", "ask", "askqty"),
        )

    async def get_bars(
        self,
        symbol: str,
        start: str,
        end: str,
        *,
        interval: str = "1min",
        response_format: str = "csv",
    ) -> list[dict[str, Any]]:
        if interval not in self.DOCUMENTED_BAR_INTERVALS:
            raise ValueError(
                "TrueData V2.6 documents bar intervals: "
                + ", ".join(sorted(self.DOCUMENTED_BAR_INTERVALS))
            )
        response = await self._history_get(
            "/getbars",
            {
                "symbol": symbol,
                "from": start,
                "to": end,
                "response": response_format,
                "interval": interval,
            },
        )
        return self._records(
            response,
            response_format,
            ("timestamp", "open", "high", "low", "close", "volume", "oi"),
        )

    async def get_last_bars(
        self,
        symbol: str,
        n: int,
        *,
        interval: str = "1min",
        response_format: str = "csv",
        bidask: int = 0,
    ) -> list[dict[str, Any]]:
        if not 1 <= n <= 200:
            raise ValueError("TrueData V2.6 documents nbars as 1..200")
        if interval not in self.DOCUMENTED_LAST_N_BAR_INTERVALS:
            raise ValueError(
                "TrueData V2.6 documents last-N-bar intervals: "
                + ", ".join(sorted(self.DOCUMENTED_LAST_N_BAR_INTERVALS))
            )
        if bidask != 0:
            raise ValueError("TrueData V2.6 documents bidask=0 for last-N bars")
        response = await self._history_get(
            "/getlastnbars",
            {
                "symbol": symbol,
                "response": response_format,
                "nbars": n,
                "interval": interval,
                "bidask": 0,
            },
        )
        return self._records(
            response,
            response_format,
            ("timestamp", "open", "high", "low", "close", "volume", "oi"),
        )

    async def get_last_ticks(
        self,
        symbol: str,
        n: int,
        *,
        bidask: int = 0,
        response_format: str = "csv",
    ) -> list[dict[str, Any]]:
        if not 1 <= n <= 200:
            raise ValueError("TrueData V2.6 documents nticks as 1..200")
        response = await self._history_get(
            "/getlastnticks",
            {
                "symbol": symbol,
                "bidask": bidask,
                "response": response_format,
                "nticks": n,
                "interval": "tick",
            },
        )
        return self._records(
            response,
            response_format,
            ("timestamp", "ltp", "volume", "oi", "bid", "bidqty", "ask", "askqty"),
        )

    async def get_ltp(
        self,
        symbol: str,
        *,
        bidask: int = 0,
        response_format: str = "csv",
    ) -> list[dict[str, Any]]:
        return await self.get_last_ticks(symbol, 1, bidask=bidask, response_format=response_format)

    async def get_bhavcopy(
        self,
        segment: str,
        date: str,
        *,
        response_format: str = "csv",
    ) -> list[dict[str, Any]]:
        response = await self._history_get(
            "/getbhavcopy",
            {"segment": segment, "date": date, "response": response_format},
        )
        return self._records(
            response,
            response_format,
            ("symbolid", "symbol", "open", "high", "low", "close", "volume", "oi"),
        )

    async def get_bhavcopy_status(
        self,
        segment: str,
        date: str,
        *,
        response_format: str = "csv",
    ) -> list[dict[str, Any]]:
        response = await self._history_get(
            "/getbhavcopystatus",
            {"segment": segment, "date": date, "response": response_format},
        )
        return self._records(response, response_format, ("segment", "timestamp"))

    async def get_all_symbols(
        self,
        segment: str,
        *,
        search: str | None = None,
        csv_response: bool = False,
        allexpiry: bool = False,
    ) -> Any:
        params: dict[str, Any] = {
            "segment": segment,
            "user": self._username,
            "password": self._password,
            "allexpiry": str(allexpiry).lower(),
        }
        if search:
            params["search"] = search
        if csv_response:
            params["csv"] = "true"
        response = await self._client.get(
            f"{self.MARKET_API_BASE_URL}/getAllSymbols",
            params=params,
        )
        self._raise_market_error(response)
        return response.text if csv_response else self._json(response)

    async def get_option_chain(
        self,
        symbol: str,
        expiry: str,
        *,
        csv_response: bool = False,
    ) -> Any:
        params: dict[str, Any] = {
            "user": self._username,
            "password": self._password,
            "symbol": symbol,
            "expiry": expiry,
        }
        if csv_response:
            params["csv"] = "true"
        response = await self._client.get(
            f"{self.MARKET_API_BASE_URL}/getOptionChain",
            params=params,
        )
        self._raise_market_error(response)
        return response.text if csv_response else self._json(response)

    @staticmethod
    def _json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise TrueDataError(f"TrueData returned non-JSON response: {response.text[:500]}") from exc
        if not isinstance(payload, dict):
            raise TrueDataError("TrueData JSON response is not an object")
        return payload

    @classmethod
    def _records(
        cls,
        response: httpx.Response,
        response_format: str,
        headers: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        if response_format.lower() == "json":
            payload = cls._json(response)
            if payload.get("status") not in (None, "Success"):
                raise TrueDataError(str(payload))
            records = payload.get("Records", [])
            if not isinstance(records, list):
                raise TrueDataError("TrueData Records is not a list")
            return [
                row if isinstance(row, dict) else dict(zip(headers, row))
                for row in records
            ]

        rows = list(csv.reader(io.StringIO(response.text)))
        if not rows:
            return []
        actual_headers = tuple(item.strip() for item in rows[0])
        return [dict(zip(actual_headers, row)) for row in rows[1:] if row]

    @staticmethod
    def _raise_history_error(response: httpx.Response) -> None:
        if response.status_code >= 400:
            raise TrueDataError(
                f"TrueData history HTTP {response.status_code}: {response.text[:500]}"
            )
        text = response.text.strip().strip('"')
        lowered = text.lower()
        # v2.6 PDF: "No Data exists for <Symbol>". Live body uses "No data exists".
        if lowered.startswith("no data exists for"):
            raise TrueDataNoDataError(text)
        if "segment not subscribed" in lowered:
            raise TrueDataError(text)

    @staticmethod
    def _raise_market_error(response: httpx.Response) -> None:
        if response.status_code >= 400:
            raise TrueDataError(
                f"TrueData market API HTTP {response.status_code}: {response.text[:500]}"
            )
