"""
Webhook management: Discord, Telegram, generic HTTP POST.
Webhooks fire when alerts are triggered.

POST /webhooks       — add webhook
GET  /webhooks       — list all
DELETE /webhooks/{id}— delete
POST /webhooks/{id}/test — send test message
POST /webhooks/{id}/toggle — enable / disable
"""
import time
from fastapi import APIRouter, HTTPException

from app.schemas.webhooks import WebhookConfig, WebhookCreate, WebhookListResponse, WebhookTestResponse
from app.services import webhook_store

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("", response_model=WebhookListResponse)
async def list_webhooks() -> WebhookListResponse:
    whs = webhook_store.list_webhooks()
    return WebhookListResponse(webhooks=whs, count=len(whs))


@router.post("", response_model=WebhookConfig)
async def add_webhook(body: WebhookCreate) -> WebhookConfig:
    return webhook_store.add_webhook(body)


@router.delete("/{wh_id}", status_code=204)
async def delete_webhook(wh_id: str) -> None:
    if not webhook_store.delete_webhook(wh_id.upper()):
        raise HTTPException(status_code=404, detail=f"Webhook {wh_id} not found")


@router.post("/{wh_id}/test", response_model=WebhookTestResponse)
async def test_webhook(wh_id: str) -> WebhookTestResponse:
    wh = webhook_store.get_webhook(wh_id.upper())
    if not wh:
        raise HTTPException(status_code=404, detail=f"Webhook {wh_id} not found")
    try:
        ok = await webhook_store._send(
            wh,
            subject="Test Notification",
            message="Sterling webhook test — connection verified ✓",
            data={"test": True, "timestamp_ms": int(time.time() * 1000)},
        )
        return WebhookTestResponse(id=wh_id, delivered=ok)
    except Exception as exc:
        return WebhookTestResponse(id=wh_id, delivered=False, error=str(exc))


@router.post("/{wh_id}/toggle", response_model=WebhookConfig)
async def toggle_webhook(wh_id: str) -> WebhookConfig:
    wh = webhook_store.get_webhook(wh_id.upper())
    if not wh:
        raise HTTPException(status_code=404, detail=f"Webhook {wh_id} not found")
    updated = webhook_store.update_webhook(wh_id.upper(), active=not wh.active)
    return updated
