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
    try:
        return await simulation_runner.start(config)
    except RuntimeError as e:
        raise HTTPException(409, str(e))


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


@router.post("/speed", response_model=SimStatus)
async def set_speed(body: SpeedBody):
    return simulation_runner.set_speed(body.speed)


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
    return AvailableDatesResponse(
        dates=sorted(dates)[-90:],  # Last 90 trading days
        instrument=instrument.upper(),
    )
