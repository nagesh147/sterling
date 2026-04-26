from fastapi import APIRouter, HTTPException
from app.schemas.instruments import InstrumentListResponse, InstrumentDetailResponse
from app.services.exchanges import instrument_registry as registry

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("", response_model=InstrumentListResponse)
async def list_instruments() -> InstrumentListResponse:
    instruments = registry.list_instruments()
    return InstrumentListResponse(instruments=instruments, count=len(instruments))


@router.get("/{underlying}", response_model=InstrumentDetailResponse)
async def get_instrument(underlying: str) -> InstrumentDetailResponse:
    inst = registry.get_instrument(underlying)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Instrument '{underlying}' not found")
    return InstrumentDetailResponse(
        instrument=inst,
        supported=True,
        options_available=inst.has_options,
        perp_symbol=inst.perp_symbol,
    )
