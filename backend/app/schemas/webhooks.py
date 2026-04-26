from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Dict, Any, List
from enum import Enum


class WebhookType(str, Enum):
    DISCORD = "discord"
    TELEGRAM = "telegram"
    GENERIC = "generic"


class WebhookCreate(BaseModel):
    name: str
    webhook_type: WebhookType = WebhookType.DISCORD
    url: str
    extra: Dict[str, Any] = {}   # telegram: {"chat_id": "xxx"}
    active: bool = True


class WebhookConfig(WebhookCreate):
    id: str
    created_at_ms: int
    last_triggered_ms: Optional[int] = None
    trigger_count: int = 0


class WebhookListResponse(BaseModel):
    webhooks: List[WebhookConfig]
    count: int


class WebhookTestResponse(BaseModel):
    id: str
    delivered: bool
    error: Optional[str] = None
