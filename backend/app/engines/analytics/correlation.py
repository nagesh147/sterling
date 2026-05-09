"""
Real-time cross-asset correlation using EWM (span=48 bars, 1H).
"""
import numpy as np
from collections import deque


class CorrelationTracker:
    SPAN = 48  # EWM span in bars

    def __init__(self, assets: list):
        self.assets = assets
        self._closes: dict = {a: deque(maxlen=200) for a in assets}

    def update(self, asset: str, close: float) -> None:
        if asset not in self._closes:
            self._closes[asset] = deque(maxlen=200)
            self.assets.append(asset)
        self._closes[asset].append(close)

    def _ewm_returns(self, asset: str) -> np.ndarray:
        closes = list(self._closes.get(asset, []))
        if len(closes) < 2:
            return np.array([])
        arr = np.array(closes, dtype=float)
        rets = np.diff(arr) / arr[:-1]
        return rets

    def _ewm_corr(self, r1: np.ndarray, r2: np.ndarray) -> float:
        n = min(len(r1), len(r2))
        if n < 5:
            return 0.0
        r1, r2 = r1[-n:], r2[-n:]
        alpha = 2.0 / (self.SPAN + 1)
        weights = np.array([(1 - alpha) ** i for i in range(n - 1, -1, -1)])
        weights /= weights.sum()
        m1 = np.sum(weights * r1)
        m2 = np.sum(weights * r2)
        cov = np.sum(weights * (r1 - m1) * (r2 - m2))
        v1  = np.sum(weights * (r1 - m1) ** 2)
        v2  = np.sum(weights * (r2 - m2) ** 2)
        denom = np.sqrt(v1 * v2)
        if denom < 1e-12:
            return 0.0
        return float(np.clip(cov / denom, -1.0, 1.0))

    def matrix(self) -> dict:
        """EWM Pearson correlation for all pairs. Returns {(a,b): corr}."""
        result = {}
        assets = self.assets
        for i, a in enumerate(assets):
            for j, b in enumerate(assets):
                if i == j:
                    result[(a, b)] = 1.0
                elif (b, a) in result:
                    result[(a, b)] = result[(b, a)]
                else:
                    r1 = self._ewm_returns(a)
                    r2 = self._ewm_returns(b)
                    result[(a, b)] = self._ewm_corr(r1, r2)
        return result

    def portfolio_correlation_penalty(self, new_asset: str, open_positions: list) -> float:
        """
        Returns scaling factor 0.0–1.0 applied to new position size.
        max_corr < 0.6 → 1.0, < 0.8 → 0.7, else → 0.4.
        """
        if not open_positions:
            return 1.0
        mat = self.matrix()
        max_corr = 0.0
        for pos_asset in open_positions:
            key = (new_asset, pos_asset)
            c = abs(mat.get(key, mat.get((pos_asset, new_asset), 0.0)))
            if c > max_corr:
                max_corr = c
        if max_corr < 0.6:
            return 1.0
        elif max_corr < 0.8:
            return 0.7
        return 0.4
