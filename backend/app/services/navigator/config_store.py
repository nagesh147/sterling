"""Navigator config persistence: validation, transactional save, activation
watermark semantics, and optimistic-concurrency revision checks.

This module is the only place allowed to decide when
`activation_watermark_ms` changes. `NavigatorConfigModel` (the client-
editable payload) has no watermark field at all, so a client cannot smuggle
one in — the server derives it purely from the enabled-state transition.
"""
from __future__ import annotations

import json
import time

from app.core.logging import get_logger
from app.engines.navigator.schemas import (
    NavigatorConfigModel,
    NavigatorConfigRecord,
    canonical_json_hash,
)
from app.services.navigator import repository as repo
from app.services.navigator.repository import NavigatorStorageError, RevisionConflict

log = get_logger(__name__)

__all__ = [
    "NavigatorStorageError",
    "RevisionConflict",
    "get",
    "save",
    "reset",
    "validate",
    "promote_calibration",
    "demote_calibration",
    "audit_history",
]

_SCHEMA_VERSION = 1


def _now_ms() -> int:
    return int(time.time() * 1000)


def _row_to_record(row: dict) -> NavigatorConfigRecord:
    payload = json.loads(row["payload_json"])
    config = NavigatorConfigModel.model_validate(payload)
    return NavigatorConfigRecord(
        user_id=row["user_id"],
        config=config,
        revision=row["revision"],
        activation_watermark_ms=row["activation_watermark_ms"],
        calibration_readiness=row["calibration_readiness"],
        calibration_report_id=row["calibration_report_id"],
        created_at_ms=row["created_at_ms"],
        updated_at_ms=row["updated_at_ms"],
    )


def get(user_id: str, *, default_underlyings: list[str]) -> NavigatorConfigRecord:
    """Load the user's Navigator config, lazily creating the off-by-default
    row (revision=1, `enabled=False`) the first time this user is seen."""
    row = repo.fetch_config_row(user_id)
    if row is not None:
        return _row_to_record(row)

    default_cfg = NavigatorConfigModel.default_for(default_underlyings)
    row = repo.insert_default_config_if_absent(
        user_id,
        schema_version=_SCHEMA_VERSION,
        payload_json=default_cfg.model_dump_json(),
        activation_watermark_ms=0,
        calibration_readiness="not_ready",
        now_ms=_now_ms(),
    )
    return _row_to_record(row)


def validate(new_config_payload: dict) -> NavigatorConfigModel:
    """Dry-run validation only — no state change. Raises pydantic
    `ValidationError` (the API layer maps this to HTTP 400 INVALID_CONFIG)."""
    return NavigatorConfigModel.model_validate(new_config_payload)


def _apply(
    user_id: str,
    new_config: NavigatorConfigModel,
    *,
    current: NavigatorConfigRecord,
    expected_revision: int,
) -> NavigatorConfigRecord:
    now = _now_ms()
    # Enabling (OFF -> ON) always stamps a fresh watermark; staying enabled,
    # staying disabled, or disabling never moves it. This is the only place
    # in the whole system that sets this field.
    if new_config.enabled and not current.config.enabled:
        activation_watermark_ms = now
    else:
        activation_watermark_ms = current.activation_watermark_ms

    previous_hash = canonical_json_hash(current.config.model_dump(mode="json"))
    new_hash = canonical_json_hash(new_config.model_dump(mode="json"))

    row = repo.compare_and_swap_config(
        user_id,
        expected_revision=expected_revision,
        new_revision=current.revision + 1,
        schema_version=_SCHEMA_VERSION,
        payload_json=new_config.model_dump_json(),
        activation_watermark_ms=activation_watermark_ms,
        # Reset/save never move calibration readiness or its report id —
        # only an explicit, separate promotion path (outside this build's
        # scope) is allowed to do that.
        calibration_readiness=current.calibration_readiness,
        calibration_report_id=current.calibration_report_id,
        now_ms=now,
        previous_hash=previous_hash,
        new_hash=new_hash,
    )
    log.info(
        "navigator.config.saved user=%s revision=%s enabled=%s operating_mode=%s",
        user_id, row["revision"], new_config.enabled, new_config.operating_mode,
    )
    return _row_to_record(row)


def save(
    user_id: str,
    new_config: NavigatorConfigModel,
    *,
    expected_revision: int,
    default_underlyings: list[str],
) -> NavigatorConfigRecord:
    """Validate + atomically save `new_config` iff `expected_revision`
    still matches the stored revision. Raises `RevisionConflict` (mapped to
    HTTP 409) on a stale writer; on any failure the prior config remains
    active untouched, per spec §3.2.C."""
    if new_config.schema_version != _SCHEMA_VERSION:
        raise ValueError(
            f"unsupported schema_version {new_config.schema_version!r} "
            f"(this server only accepts {_SCHEMA_VERSION})"
        )
    current = get(user_id, default_underlyings=default_underlyings)
    return _apply(user_id, new_config, current=current, expected_revision=expected_revision)


def reset(user_id: str, *, default_underlyings: list[str]) -> NavigatorConfigRecord:
    """Restore defaults. Always lands on `enabled=False` — restoring
    defaults can never re-enable Navigator on its own (spec §17.3)."""
    current = get(user_id, default_underlyings=default_underlyings)
    defaults = NavigatorConfigModel.default_for(default_underlyings)
    assert not defaults.enabled, "default config must always be disabled"
    return _apply(user_id, defaults, current=current, expected_revision=current.revision)


def promote_calibration(
    user_id: str,
    *,
    report_id: str,
    expected_revision: int,
    default_underlyings: list[str],
) -> NavigatorConfigRecord:
    """The ONLY writer of `calibration_readiness="ready"` in the system.

    Deliberately separate from `save`/`reset` (which always carry the
    existing readiness forward untouched) so that promotion can never be a
    side effect of an ordinary settings edit — it takes a distinct, explicit
    call naming the reviewed report. Callers are responsible for having
    checked the §19.5 criteria first; this records the decision, it does not
    make it.

    Promotion records the evidence and unlocks `gate` mode as a CHOICE. It
    does not switch the operating mode, and it does not touch
    `auto_execute_originated` — spec §19.5: "Promotion never turns on
    auto_execute." Both remain separate, explicit user actions.
    """
    current = get(user_id, default_underlyings=default_underlyings)
    now = _now_ms()
    config_hash = canonical_json_hash(current.config.model_dump(mode="json"))
    row = repo.compare_and_swap_config(
        user_id,
        expected_revision=expected_revision,
        new_revision=current.revision + 1,
        schema_version=_SCHEMA_VERSION,
        # The editable payload is untouched — only the server-owned
        # readiness metadata changes.
        payload_json=current.config.model_dump_json(),
        activation_watermark_ms=current.activation_watermark_ms,
        calibration_readiness="ready",
        calibration_report_id=report_id,
        now_ms=now,
        previous_hash=config_hash,
        new_hash=config_hash,
    )
    log.info(
        "navigator.calibration.promoted user=%s revision=%s report_id=%s",
        user_id, row["revision"], report_id,
    )
    return _row_to_record(row)


def demote_calibration(
    user_id: str, *, expected_revision: int, default_underlyings: list[str],
) -> NavigatorConfigRecord:
    """Revoke a promotion — back to `not_ready`, clearing the report id.

    The escape hatch for "we promoted this and it's behaving badly". Also
    forces `operating_mode` off `gate`, because leaving a gate selected that
    can no longer be satisfied would silently block every order instead of
    obviously reverting to advisory.
    """
    current = get(user_id, default_underlyings=default_underlyings)
    now = _now_ms()
    new_config = current.config
    if new_config.operating_mode == "gate":
        new_config = new_config.model_copy(update={"operating_mode": "advisory"})
    previous_hash = canonical_json_hash(current.config.model_dump(mode="json"))
    new_hash = canonical_json_hash(new_config.model_dump(mode="json"))
    row = repo.compare_and_swap_config(
        user_id,
        expected_revision=expected_revision,
        new_revision=current.revision + 1,
        schema_version=_SCHEMA_VERSION,
        payload_json=new_config.model_dump_json(),
        activation_watermark_ms=current.activation_watermark_ms,
        calibration_readiness="not_ready",
        calibration_report_id=None,
        now_ms=now,
        previous_hash=previous_hash,
        new_hash=new_hash,
    )
    log.info("navigator.calibration.demoted user=%s revision=%s", user_id, row["revision"])
    return _row_to_record(row)


def audit_history(user_id: str, limit: int = 50) -> list[dict]:
    return repo.fetch_config_audit(user_id, limit=limit)
