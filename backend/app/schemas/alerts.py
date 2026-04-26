from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class AlertCondition(str, Enum):
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    IVR_ABOVE = "ivr_above"
    IVR_BELOW = "ivr_below"
    SIGNAL_GREEN_ARROW = "signal_green_arrow"
    SIGNAL_RED_ARROW = "signal_red_arrow"
    STATE_IS = "state_is"         # e.g., state == ENTRY_ARMED_PULLBACK


class AlertStatus(str, Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    DISMISSED = "dismissed"


class AlertCreate(BaseModel):
    underlying: str
    condition: AlertCondition
    threshold: Optional[float] = None       # for price/IVR conditions
    target_state: Optional[str] = None     # for state_is condition
    cooldown_hours: float = Field(default=0.0, ge=0.0, le=168.0)  # 0 = fire once; >0 = auto-rearm after N hours
    notes: str = ""


class Alert(AlertCreate):
    id: str
    status: AlertStatus = AlertStatus.ACTIVE
    triggered_at_ms: Optional[int] = None
    trigger_value: Optional[float] = None
    fire_count: int = 0            # how many times this alert has fired
    created_at_ms: int


class AlertCheckResult(BaseModel):
    alert_id: str
    underlying: str
    condition: AlertCondition
    triggered: bool
    current_value: Optional[float]
    threshold: Optional[float]
    message: str


class AlertsCheckResponse(BaseModel):
    checked: int
    newly_triggered: int
    results: List[AlertCheckResult]
    timestamp_ms: int


class AlertListResponse(BaseModel):
    alerts: List[Alert]
    active_count: int
    triggered_count: int
