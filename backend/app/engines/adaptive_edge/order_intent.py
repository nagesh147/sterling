"""Canonical order-intent construction.

This module composes already-authorized research objects into a
CanonicalOrderIntent. It does not invent sizing, side, or instrument
selection mathematics. Quantity must come from F-108. Side must come
from the F-110 decision. Instrument identity must come from F-109.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import RiskAuthorization, RiskState
from .e2e import AuthorizedTradeIntent, ReplayContext, SelectedInstrument
from .execution_adapter import CanonicalOrderIntent
from .risk_sizing import PositionSizingAssessment

Authorization = AuthorizedTradeIntent | RiskAuthorization


class OrderIntentError(ValueError):
    """Raised when an order intent cannot be constructed fail-closed."""


def authorization_reference(authorization: Authorization) -> str:
    if isinstance(authorization, AuthorizedTradeIntent):
        return authorization.intent_id
    return authorization.opportunity_id


def authorization_match_id(authorization: Authorization) -> str:
    """Identity that SelectedInstrument.intent_id must equal."""
    return authorization_reference(authorization)


def _is_authorized(authorization: Authorization) -> bool:
    if isinstance(authorization, AuthorizedTradeIntent):
        return bool(authorization.intent_id) and authorization.authorized_risk > 0
    return authorization.risk_state in {RiskState.AUTHORIZED, RiskState.REDUCED}


def _parent_ids(
    authorization: Authorization,
    instrument: SelectedInstrument,
    extra: tuple[str, ...],
    authorization_id: str,
) -> tuple[str, ...]:
    parents: list[str] = [authorization_id, instrument.selection_id]
    if isinstance(authorization, AuthorizedTradeIntent):
        parents.extend((authorization.decision_id, authorization.opportunity_id))
    else:
        parents.append(authorization.opportunity_id)
    parents.extend(extra)
    seen: set[str] = set()
    ordered: list[str] = []
    for item in parents:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return tuple(ordered)


@dataclass(frozen=True)
class CanonicalOrderIntentFactory:
    """Build a fully populated CanonicalOrderIntent from authorized inputs."""

    authorization: Authorization
    sizing: PositionSizingAssessment
    side: str
    created_at: str
    order_type: str = "MARKET"
    limit_price: float | None = None
    causal_parent_ids: tuple[str, ...] = ()
    replay_context: ReplayContext | None = None
    intent_version: str = "order-v1"

    def __post_init__(self) -> None:
        if not _is_authorized(self.authorization):
            raise OrderIntentError("unauthorized risk state cannot create an order intent")
        if not self.sizing.valid or self.sizing.final_quantity <= 0:
            raise OrderIntentError("sizing is not executable")
        if self.side not in {"BUY", "SELL"}:
            raise OrderIntentError("side must be BUY or SELL")
        if self.order_type not in {"MARKET", "LIMIT"}:
            raise OrderIntentError("order_type must be MARKET or LIMIT")
        if self.order_type == "LIMIT" and (self.limit_price is None or self.limit_price <= 0):
            raise OrderIntentError("LIMIT orders require a positive limit_price")
        if self.order_type == "MARKET" and self.limit_price is not None:
            raise OrderIntentError("MARKET orders cannot carry limit_price")
        if not self.created_at:
            raise OrderIntentError("created_at is required")

    def create(self, instrument: SelectedInstrument) -> CanonicalOrderIntent:
        expected = authorization_match_id(self.authorization)
        if instrument.intent_id != expected:
            raise OrderIntentError("instrument authorization identity mismatch")
        if not instrument.instrument_id or not instrument.selection_id:
            raise OrderIntentError("selected instrument identity is required")

        authorization_id = authorization_reference(self.authorization)
        suffix = f"{instrument.selection_id}:{instrument.instrument_id}:{self.sizing.final_quantity}"
        if self.replay_context is not None:
            order_intent_id = self.replay_context.deterministic_id("ORDER", suffix)
            idempotency_key = self.replay_context.deterministic_id("IDEM", order_intent_id)
        else:
            order_intent_id = f"ORDER-{instrument.selection_id}"
            idempotency_key = f"IDEM-{instrument.selection_id}"

        intent = CanonicalOrderIntent(
            order_intent_id=order_intent_id,
            selection_id=instrument.selection_id,
            instrument_id=instrument.instrument_id,
            side=self.side,
            quantity=self.sizing.final_quantity,
            intent_version=self.intent_version,
            idempotency_key=idempotency_key,
            created_at=self.created_at,
            order_type=self.order_type,
            limit_price=self.limit_price,
            authorization_id=authorization_id,
            causal_parent_ids=_parent_ids(
                self.authorization,
                instrument,
                self.causal_parent_ids,
                authorization_id,
            ),
        )
        intent.validate()
        return intent
