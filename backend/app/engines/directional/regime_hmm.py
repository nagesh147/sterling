import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
import warnings

# Suppress sklearn/hmmlearn warnings
warnings.filterwarnings("ignore")

try:
    from hmmlearn.hmm import GaussianHMM
except ImportError:
    GaussianHMM = None

class RegimeHMMModel:
    """
    Gaussian Hidden Markov Model for predicting market regimes.
    Typically uses 3 or 4 hidden states representing different market conditions 
    (e.g., bull, bear, volatile, ranging).
    """
    def __init__(self, n_components: int = 3, random_state: int = 42):
        self.n_components = n_components
        self.random_state = random_state
        if GaussianHMM is not None:
            self.model = GaussianHMM(n_components=n_components, covariance_type="full", n_iter=100, random_state=random_state)
        else:
            self.model = None
        self.is_fitted = False

    def _prepare_features(self, df: pd.DataFrame) -> np.ndarray:
        """
        Extract features for HMM (e.g., returns, volatility).
        """
        if "close" not in df.columns:
            raise ValueError("DataFrame must contain 'close' column")
            
        returns = np.log(df["close"] / df["close"].shift(1)).fillna(0)
        
        # Calculate rolling volatility
        if len(df) > 10:
            volatility = returns.rolling(window=10).std().fillna(0)
        else:
            volatility = np.zeros_like(returns)
            
        features = np.column_stack([returns, volatility])
        return features

    def fit(self, df: pd.DataFrame) -> bool:
        if self.model is None or len(df) < 50:
            return False
            
        features = self._prepare_features(df)
        try:
            self.model.fit(features)
            self.is_fitted = True
            return True
        except Exception as e:
            print(f"HMM fit failed: {e}")
            return False

    def predict(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        if not self.is_fitted or self.model is None:
            return None
            
        features = self._prepare_features(df)
        try:
            hidden_states = self.model.predict(features)
            log_prob = self.model.score(features)
            
            # Predict next regime based on last state and transition matrix
            last_state = hidden_states[-1]
            transition_probs = self.model.transmat_[last_state]
            predicted_state = int(np.argmax(transition_probs))
            confidence = float(np.max(transition_probs))
            
            return {
                "regime": predicted_state,
                "confidence": confidence,
                "log_prob": float(log_prob)
            }
        except Exception as e:
            print(f"HMM predict failed: {e}")
            return None
