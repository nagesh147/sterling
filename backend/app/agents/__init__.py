"""
agents — thin, named facades over existing services, coordinated by the
Orchestrator and communicating via the EventBus.

Each agent has ONE responsibility and delegates to existing services (it moves
no business logic). See orchestrator.py for lifecycle.
"""
from app.agents.orchestrator import Orchestrator
from app.agents.broker_agent import BrokerAgent
from app.agents.market_agent import MarketAgent
from app.agents.strategy_agent import StrategyAgent
from app.agents.execution_agent import ExecutionAgent
from app.agents.risk_agent import RiskAgent
from app.agents.pnl_agent import PNLAgent
from app.agents.reconciliation_agent import ReconciliationAgent

__all__ = [
    "Orchestrator", "BrokerAgent", "MarketAgent", "StrategyAgent",
    "ExecutionAgent", "RiskAgent", "PNLAgent", "ReconciliationAgent",
]
