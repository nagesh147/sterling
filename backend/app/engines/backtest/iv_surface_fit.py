import numpy as np

class IVSurface:
    def __init__(self):
        self.coeffs = None

    def fit(self, strikes, dtes, ivs, spot):
        strikes = np.array(strikes)
        dtes = np.array(dtes)
        ivs = np.array(ivs)
        
        valid = (ivs > 0) & (strikes > 0) & (dtes > 0)
        strikes = strikes[valid]
        dtes = dtes[valid]
        ivs = ivs[valid]

        if len(ivs) < 5:
            # Fallback flat 60% if not enough data
            self.coeffs = np.array([0.6, 0.0, 0.0, 0.0, 0.0])
            return

        M = np.log(strikes / spot)
        T = np.maximum(dtes, 1.0) / 365.0

        # Features: 1, M, M^2, T, sqrt(T)
        A = np.column_stack([
            np.ones_like(M),
            M,
            M**2,
            T,
            np.sqrt(T)
        ])
        
        # Least squares fit
        self.coeffs, _, _, _ = np.linalg.lstsq(A, ivs, rcond=None)

    def predict(self, strike, spot, dte):
        if self.coeffs is None:
            if isinstance(strike, np.ndarray):
                return np.full_like(strike, 0.6, dtype=np.float64)
            return 0.6
            
        M = np.log(strike / spot)
        T = np.maximum(dte, 1.0) / 365.0
        
        c = self.coeffs
        iv = c[0] + c[1]*M + c[2]*(M**2) + c[3]*T + c[4]*np.sqrt(T)
        
        # Clip to sane bounds (e.g., 10% to 300%)
        return np.clip(iv, 0.1, 3.0)
