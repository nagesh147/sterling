"""
Centralised alert evaluation and delivery.

Both the SSE stream and the background poller call check_and_fire() with a
pre-computed snapshot so no duplicate exchange requests are made.
"""
import asyncio
import time
from typing import List, Optional

from app.services import alert_store, webhook_store
from app.core.logging import get_logger

log = get_logger(__name__)


def _fired_payload(alert, result) -> dict:
    return {
        "id": alert.id,
        "condition": alert.condition.value,
        "message": result.message,
    }


async def check_and_fire(
    sym: str,
    spot_price: float,
    ivr: Optional[float],
    green_arrow: bool,
    red_arrow: bool,
    current_state: str,
) -> List[dict]:
    """
    Check every active alert for *sym* against the supplied snapshot.

    - Rearms any alert whose cooldown has elapsed.
    - Fires (marks TRIGGERED) all alerts whose condition is met.
    - Delivers webhooks via asyncio.create_task (non-blocking, fail-safe).
    - Returns a list of fired-alert dicts for embedding in SSE payloads.

    Idempotent: if an alert is already TRIGGERED it won't fire again until
    rearmed (enforced by alert_store.fire_alert).
    """
    fired: List[dict] = []

    try:
        # Rearm before checking — order matters
        for a in alert_store.list_alerts(sym):
            alert_store.rearm_if_cooldown_elapsed(a.id)

        for alert in alert_store.list_alerts(sym):
            if alert.status.value != "active":
                continue

            result = alert_store.check_alert(
                alert,
                spot_price=spot_price,
                ivr=ivr,
                green_arrow=green_arrow,
                red_arrow=red_arrow,
                current_state=current_state,
            )

            if not result.triggered:
                continue

            fired_alert = alert_store.fire_alert(alert.id, trigger_value=result.current_value)
            if fired_alert is None:
                # Already fired (race condition) — skip webhook
                continue

            fired.append(_fired_payload(alert, result))

            subject = f"{sym} Alert: {alert.condition.value}"
            data = {
                "underlying": sym,
                "condition": alert.condition.value,
                "threshold": alert.threshold,
                "value": result.current_value,
                "message": result.message,
            }
            # Non-blocking: a webhook failure must never crash the caller
            asyncio.create_task(_deliver_safe(subject, result.message, data))
            log.info("Alert fired: %s (%s) %s", alert.id, sym, result.message)

    except Exception as exc:
        log.warning("check_and_fire error for %s: %s", sym, exc)

    return fired


async def _deliver_safe(subject: str, message: str, data: dict) -> None:
    try:
        await webhook_store.deliver_all(subject, message, data)
    except Exception as exc:
        log.warning("Webhook delivery failed (suppressed): %s", exc)
