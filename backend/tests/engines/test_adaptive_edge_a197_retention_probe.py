from __future__ import annotations

from datetime import date

import pytest

from app.engines.adaptive_edge.a197_retention_probe import probe_retention


@pytest.mark.asyncio
async def test_probe_records_available_and_empty_sessions() -> None:
    async def fetch(symbol: str, start: str, end: str):
        return [{"symbol": symbol, "from": start, "to": end}] if start.startswith("260814") else []

    report = await probe_retention("NIFTY-I", date(2026, 8, 13), date(2026, 8, 14), fetch)
    assert report.successful_days == (date(2026, 8, 14),)
    assert report.empty_days == (date(2026, 8, 13),)
    assert report.status == "A197_HISTORICAL_TICK_EVIDENCE_FOUND"


@pytest.mark.asyncio
async def test_probe_is_inconclusive_on_provider_error() -> None:
    async def fetch(symbol: str, start: str, end: str):
        raise TimeoutError("provider timeout")

    report = await probe_retention("NIFTY-I", date(2026, 8, 14), date(2026, 8, 14), fetch)
    assert report.error_days == (date(2026, 8, 14),)
    assert report.status == "A197_RETENTION_PROBE_INCONCLUSIVE"


@pytest.mark.asyncio
async def test_probe_rejects_reversed_date_range() -> None:
    async def fetch(symbol: str, start: str, end: str):
        return []

    with pytest.raises(ValueError, match="precede"):
        await probe_retention("NIFTY-I", date(2026, 8, 15), date(2026, 8, 14), fetch)
