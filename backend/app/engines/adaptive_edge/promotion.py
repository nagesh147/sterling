"""Promotion state for Adaptive Edge strategy definitions.

Implementation and production authorization are intentionally separate. A
fully implemented strategy remains non-executable until a versioned promotion
record is explicitly approved by the research/promotion process.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PromotionStatus(str, Enum):
    RESEARCH_ONLY = "research_only"
    APPROVED = "approved"
    REVOKED = "revoked"


@dataclass(frozen=True)
class StrategyPromotion:
    strategy_version: str
    status: PromotionStatus
    promotion_id: str | None = None
    promoted_at: str | None = None
    validation_report_id: str | None = None
    approver: str | None = None
    reason: str = ""


CURRENT_STRATEGY_PROMOTION = StrategyPromotion(
    strategy_version="2.1.0-proposed",
    status=PromotionStatus.RESEARCH_ONLY,
    reason="New strategy definition implemented; walk-forward validation and promotion are still required.",
)


def is_promoted(strategy_version: str) -> bool:
    return (
        CURRENT_STRATEGY_PROMOTION.strategy_version == strategy_version
        and CURRENT_STRATEGY_PROMOTION.status is PromotionStatus.APPROVED
    )


def require_promoted(strategy_version: str) -> StrategyPromotion:
    if not is_promoted(strategy_version):
        raise RuntimeError(
            f"Adaptive Edge strategy {strategy_version} is not production-promoted: "
            f"{CURRENT_STRATEGY_PROMOTION.status.value}"
        )
    return CURRENT_STRATEGY_PROMOTION
