from pydantic import BaseModel, Field, model_validator
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
    threshold: Optional[float] = None
    target_state: Optional[str] = None
    cooldown_hours: float = Field(default=0.0, ge=0.0, le=168.0)
    notes: str = ""

    @model_validator(mode="after")
    def validate_threshold(self) -> "AlertCreate":
        price_conds = {AlertCondition.PRICE_ABOVE, AlertCondition.PRICE_BELOW}
        ivr_conds = {AlertCondition.IVR_ABOVE, AlertCondition.IVR_BELOW}
        if self.condition in price_conds:
            if self.threshold is None or self.threshold <= 0:
                raise ValueError(f"{self.condition.value} requires threshold > 0")
        if self.condition in ivr_conds:
            if self.threshold is None or not (0 <= self.threshold <= 100):
                raise ValueError(f"{self.condition.value} requires threshold 0–100")
        if self.condition == AlertCondition.STATE_IS and not self.target_state:
            raise ValueError("state_is requires target_state")
        return self


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
