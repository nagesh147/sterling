import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any
import asyncio

from app.engines.edge.comprehensive_backtest import run_full_backtest
from app.engines.edge.robustness import run_robustness_gate
from app.engines.edge.registry import STRATEGIES, TIMEFRAMES, PROFILE_CONFIG
from app.services.execution.order_router import OrderRouter, OrderRouterRequest


class LiveArbitrator:
    """
    LiveArbitrator sits between the edge-discovery backtesting framework and the 
    OrderRouter. It qualifies edges through the robustness gate, determines position 
    sizing, checks exposure, and submits safe trades to the execution layer.
    """

    def __init__(
        self,
        order_router: OrderRouter,
        account_balance: float,
        max_risk_per_trade: float = 0.01,
        max_total_exposure: float = 0.06,
    ):
        self.order_router = order_router
        self.account_balance = account_balance
        self.max_risk_per_trade = max_risk_per_trade
        self.max_total_exposure = max_total_exposure

        self.qualified_edges: Dict[str, Dict] = {}
        self.current_positions: Dict[str, Dict] = {}

    def qualify_edge(
        self, tf: str, strategy: str, profile: str, data: pd.DataFrame
    ) -> Optional[Dict]:
        """
        Runs a full backtest and passes the results through the robustness gate.
        Returns the edge definition if it passes all statistical hurdles.
        """
        # Note: Backtest uses the symbol 'BTC' by default in run_full_backtest if not overridden,
        # but for qualification, the exact historical trace on the timeframe is enough to qualify the edge.
        result = run_full_backtest(data, tf, strategy, profile)

        # Require a minimum sample size to have any statistical significance
        if len(result.get("trades", [])) < 30:
            return None

        robustness = run_robustness_gate(result)

        # Strict statistical qualification thresholds based on the CPCV / Monte Carlo suite
        if (
            robustness.get("sharpe", 0) < 1.2
            or robustness.get("oos_sharpe", 0) < 0.8
            or robustness.get("dsr", 0) < 0.85
            or robustness.get("p_loss", 1.0) > 0.15
            or robustness.get("p_sup", 0.0) < 0.65
            or not robustness.get("wfa_passed", False)
        ):
            return None

        edge_id = f"{tf}_{strategy}_{profile}"

        return {
            "edge_id": edge_id,
            "tf": tf,
            "strategy": strategy,
            "profile": profile,
            "metrics": robustness,
            "config": PROFILE_CONFIG.get(profile, {}),
            "last_qualified": datetime.utcnow(),
            "avg_bars_held": result.get("avg_bars_held", 0),
        }

    def scan_and_qualify(self, market_data: Dict[str, pd.DataFrame]) -> List[Dict]:
        """
        Given a universe of market data keyed by timeframe, discovers all viable edges.
        """
        self.qualified_edges.clear()
        qualified_list = []

        for tf in TIMEFRAMES:
            for strat_name in STRATEGIES.keys():
                for prof_name in PROFILE_CONFIG.keys():
                    df = market_data.get(tf)
                    if df is None or df.empty:
                        continue

                    edge = self.qualify_edge(tf, strat_name, prof_name, df)
                    if edge:
                        qualified_list.append(edge)

        # Sort descending by Deflated Sharpe Ratio
        qualified_list.sort(key=lambda x: x["metrics"]["dsr"], reverse=True)
        
        # Apply correlation filtering to remove redundant edges
        final_edges = self.filter_correlated_edges(qualified_list)
        
        for edge in final_edges:
            self.qualified_edges[edge["edge_id"]] = edge
            
        return final_edges

    def filter_correlated_edges(
        self, qualified_edges: List[Dict], max_correlation: float = 0.5
    ) -> List[Dict]:
        """
        Greedy selection of edges starting from the highest Deflated Sharpe Ratio.
        Edges highly correlated to already-selected edges are discarded.
        Assumes 'return_stream' (pd.Series) is attached to the edge.
        """
        selected_edges = []
        
        for edge in qualified_edges:
            is_uncorrelated = True
            
            # If the edge doesn't have a return stream, we can't correlate it. 
            # We'll allow it by default, or you can choose to reject it.
            if "return_stream" not in edge:
                selected_edges.append(edge)
                continue
                
            for selected in selected_edges:
                if "return_stream" not in selected:
                    continue
                    
                # Calculate Pearson correlation between the two return streams
                corr = edge["return_stream"].corr(selected["return_stream"])
                
                if pd.notna(corr) and corr >= max_correlation:
                    is_uncorrelated = False
                    break
                    
            if is_uncorrelated:
                selected_edges.append(edge)
                
        return selected_edges

    def calculate_position_size(self, edge: Dict, price: float, atr: float) -> float:
        """
        Volatility-adjusted position sizing using the ATR and configured SL multiple.
        """
        risk_amount = self.account_balance * self.max_risk_per_trade
        sl_mult = edge["config"].get("sl_mult", 2.0)
        stop_distance = sl_mult * atr

        if stop_distance <= 0 or price <= 0:
            return 0.0

        # Dollars risked per unit of underlying
        dollars_per_unit = stop_distance

        size = risk_amount / dollars_per_unit
        # Return properly rounded size depending on typical exchange precision
        return max(round(size, 4), 0.0)

    def should_trade_signal(self, edge_id: str) -> bool:
        """
        Risk checks: ensures we don't breach portfolio exposure limits.
        """
        total_exposure = sum(
            pos["risk_pct"] for pos in self.current_positions.values()
        )
        if total_exposure >= self.max_total_exposure:
            return False

        # In a fully-fledged system, correlation penalties would also be applied here
        return True

    async def handle_signal(self, signal: Dict) -> bool:
        """
        Processes a real-time signal, applies arbitration logic, handles sizing, 
        and delegates to the OrderRouter for safe execution.
        
        signal is expected to contain:
        {
            'edge_id': str,
            'symbol': str,
            'direction': str,       # 'long' | 'short'
            'instrument_type': str, # 'futures' | 'options' | 'spot'
            'price': float,
            'atr': float,
            'sl': float,
            'tp': float,
            'leverage': float       # optional
        }
        """
        edge_id = signal["edge_id"]
        edge = self.qualified_edges.get(edge_id)

        if not edge or not self.should_trade_signal(edge_id):
            return False

        # Volatility-based sizing
        size = self.calculate_position_size(edge, signal["price"], signal["atr"])
        
        if size <= 0.0:
            return False

        req = OrderRouterRequest(
            underlying=signal["symbol"],
            direction=signal["direction"],
            instrument_type=signal.get("instrument_type", "futures"),
            size=size,
            leverage=signal.get("leverage", 1.0),
            order_type="market",
            stop_loss=signal.get("sl"),
            take_profit=signal.get("tp"),
            mode_name=edge["profile"],
            score=edge["metrics"].get("dsr", 0.0),
        )

        # Delegate execution to the unified OrderRouter
        resp = await self.order_router.submit(req)

        if resp.accepted:
            self.current_positions[resp.symbol] = {
                "edge_id": edge_id,
                "entry_price": signal["price"],
                "size": size,
                "risk_pct": self.max_risk_per_trade,
                "order_id": resp.order_id,
            }
            return True

        return False
