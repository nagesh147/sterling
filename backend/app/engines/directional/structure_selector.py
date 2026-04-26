from typing import List
from app.schemas.execution import CandidateContract, TradeStructure
from app.schemas.directional import Direction, PolicyResult


def _net_debit(long_leg: CandidateContract, short_leg: CandidateContract) -> float:
    return long_leg.ask - short_leg.bid


def _net_credit(sell_leg: CandidateContract, buy_leg: CandidateContract) -> float:
    return sell_leg.bid - buy_leg.ask


def _width(leg_a: CandidateContract, leg_b: CandidateContract) -> float:
    return abs(leg_a.strike - leg_b.strike)


def build_structures(
    calls: List[CandidateContract],
    puts: List[CandidateContract],
    direction: Direction,
    policy: PolicyResult,
) -> List[TradeStructure]:
    structures: List[TradeStructure] = []
    allowed = set(policy.allowed_structures)

    calls_asc = sorted(calls, key=lambda c: c.strike)
    puts_asc = sorted(puts, key=lambda c: c.strike)

    # ── LONG direction ───────────────────────────────────────────────────────
    if direction == Direction.LONG:

        # Naked call (debit)
        if "naked_call" in allowed:
            for leg in calls:
                structures.append(TradeStructure(
                    structure_type="naked_call", direction=direction, legs=[leg],
                    max_loss=leg.ask, max_gain=None,
                    net_premium=leg.ask, risk_reward=None,
                    score=0.0, score_breakdown={},
                ))

        # Bull call spread (debit): buy lower call, sell higher call
        if "bull_call_spread" in allowed and len(calls_asc) >= 2:
            for i in range(len(calls_asc) - 1):
                long_leg, short_leg = calls_asc[i], calls_asc[i + 1]
                if long_leg.dte != short_leg.dte:
                    continue
                debit = _net_debit(long_leg, short_leg)
                if debit <= 0:
                    continue
                width = _width(long_leg, short_leg)
                max_gain = width - debit
                if max_gain <= 0:
                    continue
                structures.append(TradeStructure(
                    structure_type="bull_call_spread", direction=direction,
                    legs=[long_leg, short_leg],
                    max_loss=debit, max_gain=max_gain,
                    net_premium=debit, risk_reward=round(max_gain / debit, 2),
                    score=0.0, score_breakdown={},
                ))

        # Bull put spread (credit): sell higher put, buy lower put
        if "bull_put_spread" in allowed and len(puts_asc) >= 2:
            for i in range(len(puts_asc) - 1):
                buy_leg, sell_leg = puts_asc[i], puts_asc[i + 1]  # lower buy, higher sell
                if buy_leg.dte != sell_leg.dte:
                    continue
                credit = _net_credit(sell_leg, buy_leg)
                if credit <= 0:
                    continue
                width = _width(sell_leg, buy_leg)
                max_loss = width - credit
                if max_loss <= 0:
                    continue
                structures.append(TradeStructure(
                    structure_type="bull_put_spread", direction=direction,
                    legs=[sell_leg, buy_leg],
                    max_loss=max_loss, max_gain=credit,
                    net_premium=-credit,  # negative = credit received
                    risk_reward=round(credit / max_loss, 2),
                    score=0.0, score_breakdown={},
                ))

    # ── SHORT direction ──────────────────────────────────────────────────────
    elif direction == Direction.SHORT:

        # Naked put (debit)
        if "naked_put" in allowed:
            for leg in puts:
                structures.append(TradeStructure(
                    structure_type="naked_put", direction=direction, legs=[leg],
                    max_loss=leg.ask, max_gain=None,
                    net_premium=leg.ask, risk_reward=None,
                    score=0.0, score_breakdown={},
                ))

        # Bear put spread (debit): buy higher put, sell lower put
        if "bear_put_spread" in allowed and len(puts_asc) >= 2:
            for i in range(len(puts_asc) - 1):
                sell_leg, long_leg = puts_asc[i], puts_asc[i + 1]  # sell lower, buy higher
                if sell_leg.dte != long_leg.dte:
                    continue
                debit = _net_debit(long_leg, sell_leg)
                if debit <= 0:
                    continue
                width = _width(long_leg, sell_leg)
                max_gain = width - debit
                if max_gain <= 0:
                    continue
                structures.append(TradeStructure(
                    structure_type="bear_put_spread", direction=direction,
                    legs=[long_leg, sell_leg],
                    max_loss=debit, max_gain=max_gain,
                    net_premium=debit, risk_reward=round(max_gain / debit, 2),
                    score=0.0, score_breakdown={},
                ))

        # Bear call spread (credit): sell lower call, buy higher call
        if "bear_call_spread" in allowed and len(calls_asc) >= 2:
            for i in range(len(calls_asc) - 1):
                sell_leg, buy_leg = calls_asc[i], calls_asc[i + 1]  # sell lower, buy higher
                if sell_leg.dte != buy_leg.dte:
                    continue
                credit = _net_credit(sell_leg, buy_leg)
                if credit <= 0:
                    continue
                width = _width(sell_leg, buy_leg)
                max_loss = width - credit
                if max_loss <= 0:
                    continue
                structures.append(TradeStructure(
                    structure_type="bear_call_spread", direction=direction,
                    legs=[sell_leg, buy_leg],
                    max_loss=max_loss, max_gain=credit,
                    net_premium=-credit,
                    risk_reward=round(credit / max_loss, 2),
                    score=0.0, score_breakdown={},
                ))

    return structures
