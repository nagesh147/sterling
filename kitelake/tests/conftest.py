"""Shared fixtures. No test may touch the network or need credentials."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def lake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated, stamped lake plus an isolated config dir.

    Both env vars matter: KITELAKE_ROOT pins the data, KITELAKE_CONFIG_DIR keeps the
    registry out of the developer's real ~/.config.
    """
    root = tmp_path / "SterlingLake"
    root.mkdir()
    monkeypatch.setenv("KITELAKE_ROOT", str(root))
    monkeypatch.setenv("KITELAKE_CONFIG_DIR", str(tmp_path / "cfg"))
    from kitelake.volume import ensure_layout

    ensure_layout(root)
    return root


@pytest.fixture
def no_lake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No data folder configured anywhere — the 'drive is out' state."""
    monkeypatch.delenv("KITELAKE_ROOT", raising=False)
    monkeypatch.setenv("KITELAKE_CONFIG_DIR", str(tmp_path / "cfg"))


@pytest.fixture
def instrument() -> Any:
    from kitelake.universe import Instrument

    return Instrument(
        token=738561, tradingsymbol="RELIANCE", exchange="NSE", segment="NSE",
        instrument_type="EQ", lot_size=1, tick_size=0.05,
    )


@pytest.fixture
def option() -> Any:
    from kitelake.universe import Instrument

    return Instrument(
        token=12345678, tradingsymbol="NIFTY26AUG25000CE", exchange="NFO", segment="NFO-OPT",
        instrument_type="CE", strike=25000.0, lot_size=75,
    )


def make_candles(
    n: int, *, day: str = "2026-02-03", start: tuple[int, int] = (9, 15), base: float = 100.0,
    with_oi: bool = False,
) -> list[list[Any]]:
    """Well-formed candles: high/low always bracket open/close."""
    year, month, dom = (int(p) for p in day.split("-"))
    origin = datetime(year, month, dom, *start)
    out: list[list[Any]] = []
    for i in range(n):
        price = base + i * 0.05
        row: list[Any] = [
            (origin + timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%S+0530"),
            price, price + 0.60, price - 0.40, price + 0.25, 1000 + i,
        ]
        if with_oi:
            row.append(50_000 + i)
        out.append(row)
    return out


@pytest.fixture
def candles():
    return make_candles
