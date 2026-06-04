"""
RiskEngine (Phase 4) — a separated, registry-driven risk evaluator.

Pulls the "should this be allowed?" decision out of the execution path into a
standalone, testable engine. Rules are callables(context) that return:
  * None / a RiskDecision(allowed=True)  → pass
  * a str                                → breach with that code
  * a RiskDecision(allowed=False, ...)   → explicit breach

Evaluation is FAIL-CLOSED and first-breach-wins (ordering matters). The engine
is additive: today nothing routes through it. The `shadow_compare` helper lets
it run log-only against the existing live_safety / OrderRouter decisions so any
disagreement can be reviewed BEFORE it is ever made authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Tuple, Union

RuleResult = Union[None, str, "RiskDecision"]
RiskRule = Callable[[Any], RuleResult]


@dataclass
class RiskDecision:
    allowed: bool
    code: str = ""
    reason: str = ""


class RiskEngine:
    def __init__(self, rules: Optional[List[Tuple[str, RiskRule]]] = None) -> None:
        self._rules: List[Tuple[str, RiskRule]] = list(rules or [])

    def register(self, name: str, rule: RiskRule) -> None:
        self._rules.append((name, rule))

    @property
    def rule_names(self) -> List[str]:
        return [name for name, _ in self._rules]

    @staticmethod
    def _coerce(name: str, result: RuleResult) -> RiskDecision:
        if result is None:
            return RiskDecision(allowed=True)
        if isinstance(result, RiskDecision):
            return result
        return RiskDecision(allowed=False, code=str(result), reason=f"{name}: {result}")

    def evaluate(self, context: Any) -> RiskDecision:
        """Run rules in order; return the first breach, else allow."""
        for name, rule in self._rules:
            decision = self._coerce(name, rule(context))
            if not decision.allowed:
                return decision
        return RiskDecision(allowed=True)

    def shadow_compare(self, context: Any, authoritative_allowed: bool) -> dict:
        """Compare this engine's decision to the authoritative one (log-only).

        Returns {agree, engine, authoritative_allowed}. Used during Phase 4 to
        validate parity before the engine is promoted to authoritative.
        """
        engine_decision = self.evaluate(context)
        return {
            "agree": engine_decision.allowed == authoritative_allowed,
            "engine": engine_decision,
            "authoritative_allowed": authoritative_allowed,
        }
