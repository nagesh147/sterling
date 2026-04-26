"""
Exchange configuration management.
POST /exchanges — add new exchange
GET  /exchanges — list all configured exchanges
GET  /exchanges/{id} — get single
PUT  /exchanges/{id} — update credentials/settings
DELETE /exchanges/{id} — remove
POST /exchanges/{id}/activate — set as active account exchange
POST /exchanges/{id}/test — test API credentials
"""
from fastapi import APIRouter, HTTPException
from app.schemas.exchange_config import (
    ExchangeConfig, ExchangeConfigCreate, ExchangeConfigResponse,
    ExchangeListResponse, ExchangeUpdateRequest, SUPPORTED_EXCHANGES,
)
from app.services import exchange_account_store as store
from app.services.exchanges.adapter_factory import create_account_adapter

router = APIRouter(prefix="/exchanges", tags=["exchanges"])


def _to_response(cfg: ExchangeConfig) -> ExchangeConfigResponse:
    return ExchangeConfigResponse(
        id=cfg.id,
        name=cfg.name,
        display_name=cfg.display_name,
        api_key_hint=cfg.api_key_hint(),
        is_paper=cfg.is_paper,
        is_active=cfg.is_active,
        supported=cfg.name in SUPPORTED_EXCHANGES,
        extra=cfg.extra,
    )


@router.get("", response_model=ExchangeListResponse)
async def list_exchanges() -> ExchangeListResponse:
    configs = store.list_exchanges()
    active = store.get_active()
    return ExchangeListResponse(
        exchanges=[_to_response(c) for c in configs],
        active_id=active.id if active else None,
        count=len(configs),
    )


@router.post("", response_model=ExchangeConfigResponse)
async def add_exchange(body: ExchangeConfigCreate) -> ExchangeConfigResponse:
    if body.name not in SUPPORTED_EXCHANGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported exchange: {body.name!r}. Supported: {list(SUPPORTED_EXCHANGES)}",
        )
    cfg = store.add_exchange(body)
    return _to_response(cfg)


@router.get("/supported")
async def supported_exchanges():
    return {"exchanges": [{"name": k, "display_name": v} for k, v in SUPPORTED_EXCHANGES.items()]}


@router.get("/{exchange_id}", response_model=ExchangeConfigResponse)
async def get_exchange(exchange_id: str) -> ExchangeConfigResponse:
    cfg = store.get_exchange(exchange_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Exchange {exchange_id} not found")
    return _to_response(cfg)


@router.put("/{exchange_id}", response_model=ExchangeConfigResponse)
async def update_exchange(exchange_id: str, body: ExchangeUpdateRequest) -> ExchangeConfigResponse:
    updated = store.update_exchange(
        exchange_id,
        **{k: v for k, v in body.model_dump().items() if v is not None},
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Exchange {exchange_id} not found")
    return _to_response(updated)


@router.delete("/{exchange_id}", status_code=204)
async def delete_exchange(exchange_id: str) -> None:
    if not store.delete_exchange(exchange_id):
        raise HTTPException(status_code=404, detail=f"Exchange {exchange_id} not found")


@router.post("/{exchange_id}/activate", response_model=ExchangeConfigResponse)
async def activate_exchange(exchange_id: str) -> ExchangeConfigResponse:
    cfg = store.set_active(exchange_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Exchange {exchange_id} not found")
    return _to_response(cfg)


@router.post("/{exchange_id}/test")
async def test_connection(exchange_id: str):
    cfg = store.get_exchange(exchange_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Exchange {exchange_id} not found")
    try:
        adapter = create_account_adapter(cfg)
        ok = await adapter.test_connection()
        await adapter.close()
        return {
            "exchange_id": exchange_id,
            "exchange_name": cfg.name,
            "connected": ok,
            "is_paper": cfg.is_paper,
            "message": "Paper mode — no real connection" if cfg.is_paper else ("OK" if ok else "Auth failed — check API key/secret"),
        }
    except Exception as exc:
        return {"exchange_id": exchange_id, "connected": False, "error": str(exc)}
