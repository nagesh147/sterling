"""
Market Replay Simulation endpoints.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from app.services.simulation import simulation_runner, SimConfig, SimState, SimStatus

router = APIRouter(prefix="/simulation", tags=["simulation"])


class SpeedBody(BaseModel):
    speed: float


class AvailableDatesResponse(BaseModel):
    dates: List[str]
    instrument: str


@router.post("/start", response_model=SimStatus)
async def start_sim(config: SimConfig):
    return await simulation_runner.start(config)


@router.post("/stop", response_model=SimStatus)
async def stop_sim():
    return await simulation_runner.stop()


@router.post("/pause", response_model=SimStatus)
async def pause_sim():
    if simulation_runner.status.state != SimState.RUNNING:
        raise HTTPException(400, "Not running")
    return await simulation_runner.pause()


@router.post("/resume", response_model=SimStatus)
async def resume_sim():
    if simulation_runner.status.state != SimState.PAUSED:
        raise HTTPException(400, "Not paused")
    return await simulation_runner.resume()


class SeekBody(BaseModel):
    bars_offset: Optional[int] = None
    action: Optional[str] = None  # "jump_start", "jump_end", "step"


@router.post("/speed", response_model=SimStatus)
async def set_speed(body: SpeedBody):
    return simulation_runner.set_speed(body.speed)


@router.post("/seek", response_model=SimStatus)
async def seek_sim(body: SeekBody):
    if simulation_runner.status.state == SimState.IDLE:
        raise HTTPException(400, "Simulation not running")
    if body.action == "jump_start":
        return simulation_runner.jump_start()
    elif body.action == "jump_end":
        return simulation_runner.jump_end()
    elif body.bars_offset is not None:
        return simulation_runner.step_bars(body.bars_offset)
    return simulation_runner.status


@router.get("/status", response_model=SimStatus)
async def get_status():
    return simulation_runner.status


@router.get("/available-dates")
async def available_dates(instrument: str = "NIFTY", resolution: str = "5m"):
    from app.services.ohlcv_store import get_status
    from datetime import datetime, timezone
    status = get_status()
    dates = set()
    for entry in status:
        if entry["symbol"].upper() == instrument.upper() and entry["resolution"] == resolution:
            # Generate dates between earliest and latest
            if entry["earliest"] and entry["latest"]:
                from datetime import timedelta
                current = datetime.fromtimestamp(entry["earliest"], tz=timezone.utc)
                end = datetime.fromtimestamp(entry["latest"], tz=timezone.utc)
                while current <= end:
                    # Skip weekends
                    if current.weekday() < 5:
                        dates.add(current.strftime("%Y-%m-%d"))
                    current += timedelta(days=1)
    # Fallback to last 30 business days if no stored candles found
    if not dates:
        try:
            from zoneinfo import ZoneInfo
            ist_tz = ZoneInfo("Asia/Kolkata")
        except ImportError:
            ist_tz = timezone.utc
        from datetime import timedelta
        today = datetime.now(tz=ist_tz)
        curr = today - timedelta(days=90)
        while curr <= today:
            if curr.weekday() < 5:
                dates.add(curr.strftime("%Y-%m-%d"))
            curr += timedelta(days=1)

    return AvailableDatesResponse(
        dates=sorted(dates)[-90:],  # Last 90 trading days
        instrument=instrument.upper(),
    )
