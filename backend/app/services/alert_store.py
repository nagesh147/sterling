"""
In-memory alert store + SQLite persistence.
Alerts are checked against snapshot data.
"""
import time
import uuid
from typing import Dict, List, Optional

from app.schemas.alerts import Alert, AlertCreate, AlertCondition, AlertStatus, AlertCheckResult
from app.core.logging import get_logger

log = get_logger(__name__)

_alerts: Dict[str, Alert] = {}
_loaded = False


def _new_id() -> str:
    return uuid.uuid4().hex[:8].upper()


# ─── SQLite persistence ───────────────────────────────────────────────────────

def _persist(alert: Alert) -> None:
    from app.services import db
    if not db._available:
        return
    try:
        with db._conn() as c:
            c.execute("""
                INSERT OR REPLACE INTO alerts
                    (id, underlying, condition, threshold, target_state,
                     cooldown_hours, notes, status, triggered_at_ms, trigger_value,
                     created_at_ms, fire_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.id, alert.underlying, alert.condition.value,
                alert.threshold, alert.target_state,
                alert.cooldown_hours, alert.notes,
                alert.status.value, alert.triggered_at_ms, alert.trigger_value,
                alert.created_at_ms, alert.fire_count,
            ))
    except Exception as exc:
        log.warning("alert persist failed: %s", exc)


def _delete_db(alert_id: str) -> None:
    from app.services import db
    if not db._available:
        return
    try:
        with db._conn() as c:
            c.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
    except Exception as exc:
        log.warning("alert delete failed: %s", exc)


def _load_from_db() -> List[Alert]:
    from app.services import db
    if not db._available:
        return []
    try:
        with db._conn() as c:
            rows = c.execute("SELECT * FROM alerts").fetchall()
        result = []
        for r in rows:
            try:
                result.append(Alert(
                    id=r["id"],
                    underlying=r["underlying"],
                    condition=AlertCondition(r["condition"]),
                    threshold=r["threshold"],
                    target_state=r["target_state"],
                    cooldown_hours=r["cooldown_hours"] or 0.0,
                    notes=r["notes"] or "",
                    status=AlertStatus(r["status"]),
                    triggered_at_ms=r["triggered_at_ms"],
                    trigger_value=r["trigger_value"],
                    created_at_ms=r["created_at_ms"],
                    fire_count=r["fire_count"] or 0,
                ))
            except Exception:
                continue
        return result
    except Exception as exc:
        log.warning("alert load failed: %s", exc)
        return []


def bootstrap() -> None:
    """Load persisted alerts from DB at startup."""
    global _loaded
    if _loaded:
        return
    for alert in _load_from_db():
        _alerts[alert.id] = alert
    if _alerts:
        log.info("Loaded %d alerts from DB", len(_alerts))
    _loaded = True


# ─── CRUD ─────────────────────────────────────────────────────────────────────

def add_alert(data: AlertCreate) -> Alert:
    alert = Alert(
        id=_new_id(),
        underlying=data.underlying.upper(),
        condition=data.condition,
        threshold=data.threshold,
        target_state=data.target_state,
        cooldown_hours=data.cooldown_hours,
        notes=data.notes,
        status=AlertStatus.ACTIVE,
        created_at_ms=int(time.time() * 1000),
    )
    _alerts[alert.id] = alert
    _persist(alert)
    return alert


def get_alert(alert_id: str) -> Optional[Alert]:
    return _alerts.get(alert_id)


def list_alerts(underlying: Optional[str] = None) -> List[Alert]:
    alerts = list(_alerts.values())
    if underlying:
        alerts = [a for a in alerts if a.underlying == underlying.upper()]
    return sorted(alerts, key=lambda a: a.created_at_ms, reverse=True)


def dismiss_alert(alert_id: str) -> Optional[Alert]:
    alert = _alerts.get(alert_id)
    if not alert:
        return None
    updated = alert.model_copy(update={"status": AlertStatus.DISMISSED})
    _alerts[alert_id] = updated
    _persist(updated)
    return updated


def delete_alert(alert_id: str) -> bool:
    if alert_id not in _alerts:
        return False
    del _alerts[alert_id]
    _delete_db(alert_id)
    return True


def clear(underlying: Optional[str] = None) -> None:
    if underlying:
        keys = [k for k, v in _alerts.items() if v.underlying == underlying.upper()]
        for k in keys:
            del _alerts[k]
    else:
        _alerts.clear()


def check_alert(
    alert: Alert,
    spot_price: Optional[float] = None,
    ivr: Optional[float] = None,
    green_arrow: bool = False,
    red_arrow: bool = False,
    current_state: Optional[str] = None,
) -> AlertCheckResult:
    """Evaluate one alert against current market data. Returns result but does NOT mutate."""
    cond = alert.condition
    triggered = False
    current_value = None
    msg = ""

    if cond == AlertCondition.PRICE_ABOVE and spot_price is not None:
        current_value = spot_price
        triggered = spot_price > (alert.threshold or 0)
        msg = f"Price {spot_price:.2f} {'>' if triggered else '<='} {alert.threshold}"

    elif cond == AlertCondition.PRICE_BELOW and spot_price is not None:
        current_value = spot_price
        triggered = spot_price < (alert.threshold or float("inf"))
        msg = f"Price {spot_price:.2f} {'<' if triggered else '>='} {alert.threshold}"

    elif cond == AlertCondition.IVR_ABOVE and ivr is not None:
        current_value = ivr
        triggered = ivr > (alert.threshold or 0)
        msg = f"IVR {ivr:.1f} {'>' if triggered else '<='} {alert.threshold}"

    elif cond == AlertCondition.IVR_BELOW and ivr is not None:
        current_value = ivr
        triggered = ivr < (alert.threshold or float("inf"))
        msg = f"IVR {ivr:.1f} {'<' if triggered else '>='} {alert.threshold}"

    elif cond == AlertCondition.SIGNAL_GREEN_ARROW:
        triggered = green_arrow
        msg = "Green arrow fired" if triggered else "No green arrow"

    elif cond == AlertCondition.SIGNAL_RED_ARROW:
        triggered = red_arrow
        msg = "Red arrow fired" if triggered else "No red arrow"

    elif cond == AlertCondition.STATE_IS and current_state:
        triggered = current_state == alert.target_state
        msg = f"State {current_state} {'==' if triggered else '!='} {alert.target_state}"

    return AlertCheckResult(
        alert_id=alert.id,
        underlying=alert.underlying,
        condition=cond,
        triggered=triggered,
        current_value=current_value,
        threshold=alert.threshold,
        message=msg,
    )


def fire_alert(alert_id: str, trigger_value: Optional[float] = None) -> Optional[Alert]:
    """Mark alert as triggered. If cooldown_hours > 0, status stays TRIGGERED until cooldown elapses."""
    alert = _alerts.get(alert_id)
    if not alert or alert.status != AlertStatus.ACTIVE:
        return None
    updated = alert.model_copy(update={
        "status": AlertStatus.TRIGGERED,
        "triggered_at_ms": int(time.time() * 1000),
        "trigger_value": trigger_value,
        "fire_count": alert.fire_count + 1,
    })
    _alerts[alert_id] = updated
    _persist(updated)
    return updated


def rearm_if_cooldown_elapsed(alert_id: str) -> bool:
    """
    If alert has cooldown_hours > 0 and enough time has passed since trigger,
    resets status to ACTIVE so it can fire again. Returns True if rearmed.
    """
    alert = _alerts.get(alert_id)
    if not alert or alert.status != AlertStatus.TRIGGERED:
        return False
    if alert.cooldown_hours <= 0:
        return False  # fire-once alert — stays triggered until dismissed
    if alert.triggered_at_ms is None:
        return False
    elapsed_hours = (int(time.time() * 1000) - alert.triggered_at_ms) / 3_600_000
    if elapsed_hours >= alert.cooldown_hours:
        updated = alert.model_copy(update={"status": AlertStatus.ACTIVE})
        _alerts[alert_id] = updated
        _persist(updated)
        return True
    return False


def active_count() -> int:
    return sum(1 for a in _alerts.values() if a.status == AlertStatus.ACTIVE)


def triggered_count() -> int:
    return sum(1 for a in _alerts.values() if a.status == AlertStatus.TRIGGERED)
