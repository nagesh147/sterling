import os
import json
import asyncio
from fastapi import APIRouter
from typing import Any

router = APIRouter(prefix="/wfo", tags=["wfo"])

WHITELIST_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "engines", "sterling_engine", "whitelist.json"
)
IMPACT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "engines", "sterling_engine", "impact.json"
)
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "optimizer_cron.log")


def _read_json(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _tail_log(path: str, lines: int) -> list[str]:
    if not os.path.exists(path):
        return ["Log file not found."]
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines_list = f.readlines()
        return lines_list[-lines:]
    except Exception as e:
        return [f"Error reading logs: {e}"]


def _launch_optimizer() -> None:
    import subprocess

    cron_script = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "optimizer_cron.py"
    )
    with open(LOG_PATH, "a", encoding="utf-8") as logf:
        subprocess.Popen(
            ["python3", cron_script],
            stdout=logf,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


@router.get("/state")
async def get_wfo_state():
    whitelist, impact = await asyncio.gather(
        asyncio.to_thread(_read_json, WHITELIST_PATH),
        asyncio.to_thread(_read_json, IMPACT_PATH),
    )
    return {"whitelist": whitelist, "impact": impact}


@router.get("/logs")
async def get_wfo_logs(lines: int = 100):
    logs = await asyncio.to_thread(_tail_log, LOG_PATH, lines)
    return {"logs": logs}


@router.post("/run")
async def run_wfo():
    # Start the optimizer off the event loop so open/Popen never block async workers.
    await asyncio.to_thread(_launch_optimizer)
    return {"status": "started", "message": "Walk-Forward Optimizer launched in background."}
