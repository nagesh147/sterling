"""
Robustness Validation Module

Implements statistical gates to filter out overfit trading strategies.
Key components:
1. Monte Carlo Trade Permutation: Shuffles trade returns to measure Probability of Loss (P_Loss).
2. Combinatorial Purged Cross-Validation (CPCV): Estimates worst-case out-of-sample (OOS) Sharpe.
3. Deflated Sharpe Ratio (DSR): Adjusts Sharpe for multiple-testing bias.
4. Walk-Forward Analysis: (Placeholder for advanced sequential testing).
"""

import math
import numpy as np

from app.engines.analytics.performance import _inverse_normal_cdf, _phi


def monte_carlo_p_loss(trade_returns: list[float], iterations: int = 1000, max_drawdown_limit: float = -0.2) -> tuple[float, float]:
    """
    Shuffles trade returns to compute the probability of loss (P(Loss)) or ruining drawdown,
    as well as the Probability of Superiority (P(Sup)) — fraction of paths that beat the original return.
    Returns (p_loss, p_sup).
    """
    if not trade_returns or len(trade_returns) < 10:
        return 1.0, 0.0
        
    returns = np.array(trade_returns)
    n_trades = len(returns)
    orig_cum_ret = np.sum(returns)
    
    failed_paths = 0
    superior_paths = 0
    
    for _ in range(iterations):
        # Sample with replacement for robust bootstrap
        path = np.random.choice(returns, size=n_trades, replace=True)
        cum_ret = np.cumsum(path)
        final_ret = cum_ret[-1]
        
        # Did we end up negative?
        if final_ret <= 0:
            failed_paths += 1
            continue
            
        if final_ret > orig_cum_ret:
            superior_paths += 1
            
        # Did we breach the drawdown limit?
        roll_max = np.maximum.accumulate(cum_ret)
        drawdown = cum_ret - roll_max
        if np.min(drawdown) <= max_drawdown_limit:
            failed_paths += 1
            
    return failed_paths / iterations, superior_paths / iterations


def cpcv_sharpe(equity_curve: np.ndarray, splits: int = 4, purge_bars: int = 20) -> float:
    """
    Combinatorial Purged Cross-Validation (CPCV) estimation using block sampling with purging.
    Drops `purge_bars` around the edges of the splits to ensure temporal independence.
    """
    n = len(equity_curve)
    if n < splits * purge_bars * 2:
        return -float('inf')
        
    split_len = n // splits
    sharpes = []
    
    for i in range(splits):
        start_idx = i * split_len + (purge_bars // 2)
        end_idx = (i + 1) * split_len - (purge_bars // 2)
        
        if start_idx >= end_idx:
            continue
            
        chunk = equity_curve[start_idx:end_idx]
        active_returns = chunk[chunk != 0]
        if len(active_returns) < 2:
            sharpes.append(-np.inf)
            continue
            
        mean_ret = np.mean(active_returns)
        std_ret = np.std(active_returns)
        sharpe = (mean_ret / std_ret) if std_ret > 1e-9 else -np.inf
        sharpes.append(sharpe)
        
    # OOS Sharpe is the minimum (worst-case) out-of-sample period
    return float(np.min(sharpes))


def deflated_sharpe_ratio(trade_returns: list[float], num_trials: int = 100) -> float:
    """
    Calculates the Deflated Sharpe Ratio (DSR) using Lopez de Prado's rigorous formulation.
    Adjusts Sharpe for multiple-testing bias, non-normal skewness, and kurtosis.
    Returns a probability score [0, 1].
    """
    if not trade_returns or len(trade_returns) < 10:
        return 0.0
        
    returns = np.array(trade_returns)
    t = len(returns)
    mean_ret = np.mean(returns)
    std_ret = np.std(returns) + 1e-9
    sharpe = mean_ret / std_ret  # per-trade (per-observation) Sharpe

    # Calculate Skewness and Kurtosis
    diffs = returns - mean_ret
    variance = np.mean(diffs**2) + 1e-9
    skewness = np.mean(diffs**3) / (variance**1.5)
    kurtosis = np.mean(diffs**4) / (variance**2)  # Non-excess kurtosis

    # Expected maximum Sharpe of `num_trials` independent strategies under the
    # null, expressed in standard-error (t-stat) units — i.e. the max of
    # num_trials standard normals (Bailey & Lopez de Prado, 2014). The
    # inverse-normal form is more accurate for small num_trials than the
    # asymptotic sqrt(2 ln N) approximation, which over-estimates the hurdle.
    euler_mascheroni = 0.5772156649015329
    n_trials = max(int(num_trials), 2)
    inv_phi_first  = _inverse_normal_cdf(1.0 - 1.0 / n_trials)
    inv_phi_second = _inverse_normal_cdf(1.0 - 1.0 / (n_trials * math.e))
    expected_max = (
        (1.0 - euler_mascheroni) * inv_phi_first
        + euler_mascheroni       * inv_phi_second
    )

    # Variance of the Sharpe ratio estimate (Lo, 2002 / Lopez de Prado, 2014)
    var_sr = 1 - skewness * sharpe + ((kurtosis - 1) / 4.0) * (sharpe ** 2)
    var_sr = max(var_sr, 1e-9)

    # DSR Z-score: convert the observed per-trade Sharpe to its t-stat
    # (standard-error units) FIRST, THEN deflate by the expected max under the
    # null. The prior version multiplied (sharpe - expected_max) together by
    # sqrt(t-1)/sqrt(var_sr), scaling the standard-normal benchmark (~2.9) by
    # the sample size as well — which pitted a per-trade Sharpe (~0.2) against
    # an inflated hurdle and saturated DSR to ~0 for every config.
    z_score = sharpe * np.sqrt(t - 1) / np.sqrt(var_sr) - expected_max

    return float(_phi(z_score))


def walk_forward_analysis(trades: list[dict], equity_curve: np.ndarray) -> dict:
    """
    Time-Series Stability Analysis (Proxy for Walk-Forward Analysis).
    Slices the raw return stream into rolling chronological windows to ensure
    performance isn't overly dependent on a single market regime.
    """
    n = len(equity_curve)
    
    if n < 100:
        return {"wfa_passed": False, "wfa_consistency": 0.0}
        
    splits = 5
    split_len = n // splits
    profitable_chunks = 0
    
    for i in range(splits):
        # We expect equity_curve to be the raw return stream here.
        chunk = equity_curve[i * split_len : (i + 1) * split_len]
        if np.sum(chunk) > 0:
            profitable_chunks += 1
            
    wfa_consistency = profitable_chunks / splits
    return {
        "wfa_passed": wfa_consistency >= 0.6,
        "wfa_consistency": wfa_consistency
    }


def run_robustness_gate(trades: list[dict], equity_curve: np.ndarray, num_trials: int = 100) -> dict:
    """
    Runs all robustness checks on a single configuration's results.
    Returns a dictionary of robustness metrics.
    """
    if len(trades) < 10:
        return {"oos_sharpe": -float('inf'), "p_loss": 1.0, "p_sup": 0.0, "dsr": 0.0}
        
    trade_returns = [t['return'] for t in trades]
    
    p_loss, p_sup = monte_carlo_p_loss(trade_returns, iterations=1000)
    oos_sharpe = cpcv_sharpe(equity_curve, splits=4, purge_bars=20)
    dsr = deflated_sharpe_ratio(trade_returns, num_trials=num_trials)
    
    # Walk-Forward / Regime Stability
    wfa = walk_forward_analysis(trades, equity_curve)
    
    return {
        "oos_sharpe": float(oos_sharpe),
        "p_loss": float(p_loss),
        "p_sup": float(p_sup),
        "dsr": float(dsr),
        "wfa_passed": wfa["wfa_passed"],
        "wfa_consistency": wfa["wfa_consistency"]
    }
