"""
Market Replay Simulation endpoints.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Literal
from app.services.simulation import simulation_runner, SimConfig, SimState, SimStatus

router = APIRouter(prefix="/simulation", tags=["simulation"])


class SpeedBody(BaseModel):
    speed: float


class AvailableDatesResponse(BaseModel):
    dates: List[str]
    instrument: str
    resolution: str
    # Whether these dates came from the candle store or were synthesised. The
    # endpoint invents 90 business days when the store is empty, and a client
    # that presents those as "sessions with data" is lying on its behalf.
    source: Literal["store", "fallback"]
    earliest: Optional[str] = None
    latest: Optional[str] = None
    # The store walk skips weekends but NOT exchange holidays, so a date in this
    # list is "plausibly a session", not "confirmed to have candles".
    holidays_filtered: bool = False


@router.post("/start", response_model=SimStatus)
async def start_sim(config: SimConfig, force: bool = Query(False)):
    # Starting over a live replay used to happen silently, so the client could
    # not tell "your replay restarted" from "your replay was already running".
    if simulation_runner.status.state != SimState.IDLE and not force:
        raise HTTPException(
            409,
            detail={
                "code": "already_running",
                "message": "A replay is already running. Stop it, or start with force=true to restart.",
            },
        )
    return await simulation_runner.start(config)


@router.post("/stop", response_model=SimStatus)
async def stop_sim():
    return await simulation_runner.stop()


@router.post("/pause", response_model=SimStatus)
async def pause_sim():
    if simulation_runner.status.state != SimState.RUNNING:
        raise HTTPException(400, detail={"code": "not_running", "message": "Replay is not running."})
    return await simulation_runner.pause()


@router.post("/resume", response_model=SimStatus)
async def resume_sim():
    if simulation_runner.status.state != SimState.PAUSED:
        raise HTTPException(400, detail={"code": "not_paused", "message": "Replay is not paused."})
    return await simulation_runner.resume()


class SeekBody(BaseModel):
    bars_offset: Optional[int] = None
    bar_index: Optional[int] = None      # absolute bar
    to_pct: Optional[float] = None       # 0..100 through the session
    to_time: Optional[str] = None        # "HH:MM:SS" IST
    action: Optional[str] = None         # "jump_start", "jump_end", "step"


@router.post("/speed", response_model=SimStatus)
async def set_speed(body: SpeedBody):
    return simulation_runner.set_speed(body.speed)


@router.post("/seek", response_model=SimStatus)
async def seek_sim(body: SeekBody):
    if simulation_runner.status.state == SimState.IDLE:
        raise HTTPException(400, detail={"code": "not_running", "message": "Replay is not running."})
    # Precedence: named action, then the absolute forms, then the relative one.
    if body.action == "jump_start":
        return simulation_runner.jump_start()
    if body.action == "jump_end":
        return simulation_runner.jump_end()
    if body.bar_index is not None or body.to_pct is not None or body.to_time is not None:
        return simulation_runner.seek_to(
            bar_index=body.bar_index, to_pct=body.to_pct, to_time=body.to_time
        )
    if body.bars_offset is not None:
        return simulation_runner.step_bars(body.bars_offset)
    return simulation_runner.status


@router.get("/status", response_model=SimStatus)
async def get_status(
    since_events: Optional[int] = Query(None, ge=0),
    since_trades: Optional[int] = Query(None, ge=0),
):
    # Omitting both offsets returns the full payload, exactly as before.
    return simulation_runner.status_since(since_events, since_trades)


@router.get("/available-dates", response_model=AvailableDatesResponse)
async def available_dates(instrument: str = "NIFTY", resolution: str = "5m"):
    from app.services.ohlcv_store import get_status
    from datetime import datetime, timezone, timedelta

    status = get_status()
    dates = set()
    earliest_iso: Optional[str] = None
    latest_iso: Optional[str] = None

    for entry in status:
        if entry["symbol"].upper() == instrument.upper() and entry["resolution"] == resolution:
            if entry["earliest"] and entry["latest"]:
                current = datetime.fromtimestamp(entry["earliest"], tz=timezone.utc)
                end = datetime.fromtimestamp(entry["latest"], tz=timezone.utc)
                earliest_iso = current.strftime("%Y-%m-%d")
                latest_iso = end.strftime("%Y-%m-%d")
                while current <= end:
                    if current.weekday() < 5:
                        dates.add(current.strftime("%Y-%m-%d"))
                    current += timedelta(days=1)

    source: Literal["store", "fallback"] = "store"

    # Fallback to the last 90 business days when the store holds nothing. These
    # dates are INVENTED — `source` is how the client knows not to present them
    # as evidence that candles exist.
    if not dates:
        source = "fallback"
        try:
            from zoneinfo import ZoneInfo
            ist_tz = ZoneInfo("Asia/Kolkata")
        except ImportError:
            ist_tz = timezone.utc
        today = datetime.now(tz=ist_tz)
        curr = today - timedelta(days=90)
        while curr <= today:
            if curr.weekday() < 5:
                dates.add(curr.strftime("%Y-%m-%d"))
            curr += timedelta(days=1)

    ordered = sorted(dates)[-90:]
    return AvailableDatesResponse(
        dates=ordered,
        instrument=instrument.upper(),
        resolution=resolution,
        source=source,
        earliest=earliest_iso or (ordered[0] if ordered else None),
        latest=latest_iso or (ordered[-1] if ordered else None),
        holidays_filtered=False,
    )
