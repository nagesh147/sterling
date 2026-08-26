from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .execution_adapter import CanonicalOrderIntent


@dataclass(frozen=True)
class OrderIntentInputs:
    selection_id: str
    instrument_id: str
    side: str
    quantity: int
    intent_version: str
    created_at: str
    deterministic_namespace: str = "adaptive-edge"


class OrderIntentFactory:
    """Create validated, deterministic canonical order intents.

    This factory constructs intent only. It neither authorizes execution nor
    submits to a broker. Execution remains the responsibility of
    ExecutionGateway, which enforces the execution gate.
    """

    @staticmethod
    def create(inputs: OrderIntentInputs) -> CanonicalOrderIntent:
        if not inputs.selection_id:
            raise ValueError("selection_id is required")
        if not inputs.instrument_id:
            raise ValueError("instrument_id is required")
        if inputs.side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if inputs.quantity <= 0:
            raise ValueError("quantity must be positive")
        if not inputs.intent_version:
            raise ValueError("intent_version is required")
        if not inputs.created_at:
            raise ValueError("created_at is required")

        seed = "|".join(
            (
                inputs.deterministic_namespace,
                inputs.selection_id,
                inputs.instrument_id,
                inputs.side,
                str(inputs.quantity),
                inputs.intent_version,
                inputs.created_at,
            )
        )
        digest = sha256(seed.encode("utf-8")).hexdigest()
        order_intent_id = f"ae-order-{digest[:24]}"
        idempotency_key = f"ae-idem-{digest}"

        intent = CanonicalOrderIntent(
            order_intent_id=order_intent_id,
            selection_id=inputs.selection_id,
            instrument_id=inputs.instrument_id,
            side=inputs.side,
            quantity=inputs.quantity,
            intent_version=inputs.intent_version,
            idempotency_key=idempotency_key,
            created_at=inputs.created_at,
        )
        intent.validate()
        return intent
