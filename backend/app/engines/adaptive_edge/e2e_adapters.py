"""Composed E2E adapters. Not isolated fixtures."""
from __future__ import annotations

from typing import Sequence

from .contracts import RiskAuthorization, RiskState
from .e2e import (
    AuthorizedTradeIntent,
    DecisionEligibility,
    LifecycleEvaluation,
    PositionState,
    PredictionEvidence,
    SelectedInstrument,
)
from .edge import EdgeAssessment
from .event_boundary import CanonicalMarketEvent
from .execution_adapter import CanonicalExecutionEvent, CanonicalOrderIntent
from .feature_engine import (
    FeatureInput,
    FeatureProvenance,
    FeatureSnapshot,
    FeatureStatus,
    InstrumentContext,
    build_feature_snapshot,
)
from .instrument_selection import (
    InstrumentSelectionError,
    ListedOptionCandidate,
    select_listed_instrument,
)
from .lifecycle_engine import A126LifecycleEngine
from .order_intent import CanonicalOrderIntentFactory
from .position_projector import DeterministicPositionProjector
from .risk_sizing import PositionSizingAssessment


class RiskAuthorizationError(ValueError):
    """Raised when a granted risk ceiling cannot issue a trade intent."""


_BAR_FIELDS = ("open", "high", "low", "close", "volume", "oi")


class BarFeatureBuilder:
    """F-001 snapshot from present bar fields only. Does not invent prices."""

    def __init__(
        self,
        *,
        strategy_version: str = "v2.0",
        feature_set_version: str = "fset-v1",
    ) -> None:
        self._strategy_version = strategy_version
        self._feature_set_version = feature_set_version

    def build(self, event: CanonicalMarketEvent) -> FeatureSnapshot:
        inputs: list[FeatureInput] = []
        provenance = FeatureProvenance(source_event_ids=(event.record_id,))
        for name in _BAR_FIELDS:
            if name not in event.payload or event.payload[name] is None:
                continue
            inputs.append(
                FeatureInput(
                    name,
                    float(event.payload[name]),
                    event.available_at,
                    FeatureStatus.VALID,
                    provenance,
                )
            )
        if not any(item.name == "close" for item in inputs):
            raise ValueError("bar feature builder requires close")
        return build_feature_snapshot(
            snapshot_id=f"SNAP-{event.record_id}",
            strategy_version=self._strategy_version,
            feature_set_version=self._feature_set_version,
            observation_cutoff_time=event.available_at,
            decision_time=event.available_at,
            instrument_context=InstrumentContext(event.instrument_id),
            inputs=inputs,
        )


class IdentityPredictionBinder:
    """Causal identity only. Does not invent an F-102 score."""

    def predict(self, snapshot: FeatureSnapshot) -> PredictionEvidence:
        return PredictionEvidence(
            prediction_id=f"PRED-{snapshot.snapshot_id}",
            snapshot_id=snapshot.snapshot_id,
            opportunity_id=f"OPP-{snapshot.snapshot_id}",
            strategy_version=snapshot.strategy_version,
            model_version="identity-v1",
            prediction_time=snapshot.decision_time,
            target_definition_version="unspecified",
            horizon_definition_version="unspecified",
            prediction_type="IDENTITY",
            prediction_value=None,
            uncertainty=None,
            calibration_reference=None,
            provenance={"binding": "identity-only"},
        )


class ExplicitGrossEdge:
    """Carrier for an explicit expected-gross input through the F-004 gate.

    Does not invent an F-102 score. expected_gross is required from the caller
    the same way ConservativeEV is required for F-110.
    """

    formula_id: str = "F-004"
    formula_version: str = "1.0"

    def __init__(self, expected_gross: float | None) -> None:
        self.expected_gross = expected_gross

    def evaluate(self, snapshot: FeatureSnapshot) -> EdgeAssessment:
        close = snapshot.values.get("close")
        inputs: dict[str, float] = {}
        if close is not None:
            inputs["close"] = float(close)
        return EdgeAssessment(
            opportunity_id=f"OPP-{snapshot.snapshot_id}",
            score=0.0,
            confidence=None,
            expected_gross_value=self.expected_gross,
            formula_id=self.formula_id,
            formula_version=self.formula_version,
            inputs=inputs,
        )


class ComposedRiskAuthorizer:
    """Bind an already-granted RiskAuthorization to a decision.

    Does not compute F-114 PortfolioRisk. authorized_risk is the ceiling
    already granted by the caller.
    """

    def __init__(
        self,
        authorization: RiskAuthorization,
        *,
        authorization_version: str = "risk-v1",
    ) -> None:
        if authorization.risk_state not in {RiskState.AUTHORIZED, RiskState.REDUCED}:
            raise RiskAuthorizationError("unauthorized risk state cannot issue a trade intent")
        if authorization.authorized_risk <= 0:
            raise RiskAuthorizationError("authorized_risk must be positive")
        if not authorization.issued_at:
            raise RiskAuthorizationError("issued_at is required")
        self._authorization = authorization
        self._authorization_version = authorization_version

    def authorize(self, decision: DecisionEligibility) -> AuthorizedTradeIntent:
        if not decision.eligible:
            raise RiskAuthorizationError("ineligible decision cannot be authorized")
        if not decision.decision_id:
            raise RiskAuthorizationError("decision identity is required")
        if not decision.opportunity_id:
            raise RiskAuthorizationError("opportunity identity is required")
        return AuthorizedTradeIntent(
            intent_id=f"AUTH-{decision.decision_id}",
            opportunity_id=decision.opportunity_id,
            decision_id=decision.decision_id,
            authorization_version=self._authorization_version,
            authorized_risk=self._authorization.authorized_risk,
            issued_at=self._authorization.issued_at,
        )


class ListedInstrumentSelector:
    """F-109 listed-only adapter. Empty/lookahead chain fails closed.

    Does not invent ATM when no listed universe is provided. Registry stays LOCKED.
    """

    def __init__(
        self,
        candidates: Sequence[ListedOptionCandidate],
        *,
        option_type: str,
        decision_time: str | None = None,
        selection_version: str = "listed-v1",
    ) -> None:
        self._candidates = tuple(candidates)
        self._option_type = option_type
        self._decision_time = decision_time
        self._selection_version = selection_version

    def select(self, intent: AuthorizedTradeIntent) -> SelectedInstrument:
        if not intent.intent_id:
            raise InstrumentSelectionError("authorization identity is required")
        decision_time = self._decision_time or intent.issued_at
        chosen = select_listed_instrument(
            self._candidates,
            decision_time=decision_time,
            option_type=self._option_type,
        )
        return SelectedInstrument(
            selection_id=f"SEL-{intent.intent_id}",
            intent_id=intent.intent_id,
            instrument_id=chosen.instrument_id,
            selection_version=self._selection_version,
            selected_at=decision_time,
        )


class ComposedOrderIntentFactory:
    def __init__(
        self,
        *,
        sizing: PositionSizingAssessment,
        side: str = "BUY",
        created_at: str,
        authorized_risk: float,
    ) -> None:
        self._sizing = sizing
        self._side = side
        self._created_at = created_at
        self._authorized_risk = authorized_risk

    def create(self, instrument: SelectedInstrument) -> CanonicalOrderIntent:
        authorization = AuthorizedTradeIntent(
            intent_id=instrument.intent_id,
            opportunity_id=instrument.intent_id,
            decision_id=instrument.intent_id,
            authorization_version="e2e-composed-v1",
            authorized_risk=self._authorized_risk,
            issued_at=self._created_at,
        )
        return CanonicalOrderIntentFactory(
            authorization=authorization,
            sizing=self._sizing,
            side=self._side,
            created_at=self._created_at,
        ).create(instrument)


class InstrumentAwarePositionProjector:
    def __init__(self, instrument_id: str, *, side: str = "BUY") -> None:
        self._instrument_id = instrument_id
        self._inner = DeterministicPositionProjector(
            position_id=f"POS-{instrument_id}",
            instrument_id=instrument_id,
            side=side,
        )

    def project(self, event: CanonicalExecutionEvent) -> PositionState:
        return self._inner.project(event)


class ComposedLifecycleEngine:
    def __init__(self) -> None:
        self._engine: A126LifecycleEngine | None = None

    def evaluate(self, position: PositionState, event: CanonicalMarketEvent) -> LifecycleEvaluation:
        if self._engine is None:
            self._engine = A126LifecycleEngine(position.position_id)
        return self._engine.evaluate(position, event)
