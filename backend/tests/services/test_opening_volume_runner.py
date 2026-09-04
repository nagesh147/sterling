from types import SimpleNamespace

import pytest

from app.services import opening_volume_execution, opening_volume_leaders
from app.services import opening_volume_runner as runner
from app.services.kite_engine import state as engine_state


@pytest.mark.asyncio
async def test_runner_does_not_scan_while_shared_auto_execute_is_off(monkeypatch):
    monkeypatch.setattr(
        opening_volume_execution,
        "get_config",
        lambda _uid: opening_volume_execution.OpeningExecutionConfig(enabled=True),
    )
    monkeypatch.setattr(
        engine_state,
        "get_config",
        lambda _uid: SimpleNamespace(auto_execute=False),
    )

    async def forbidden_scan(_uid):
        raise AssertionError("manual mode must stop before the broker scan")

    monkeypatch.setattr(opening_volume_leaders, "scan_kite_leaders", forbidden_scan)

    assert await runner.run_user("tenant-a") == {"status": "manual"}
