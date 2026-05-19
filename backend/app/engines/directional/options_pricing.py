import math

def sabr_implied_vol(alpha: float, beta: float, rho: float, nu: float, f: float, k: float, t: float) -> float:
    """
    SABR model approximation for implied volatility.
    
    Parameters:
    - alpha: initial variance
    - beta: CEV parameter (typically 0.5 for stochastic volatility, 1.0 for lognormal)
    - rho: correlation between forward rate and volatility
    - nu: volatility of volatility
    - f: forward price
    - k: strike price
    - t: time to maturity
    """
    if f <= 0 or k <= 0 or t <= 0:
        return 0.0
        
    try:
        if math.isclose(f, k, rel_tol=1e-5):
            # ATM Volatility
            term1 = ((1 - beta) ** 2 / 24) * (alpha ** 2) / (f ** (2 - 2 * beta))
            term2 = (rho * beta * nu * alpha) / (4 * (f ** (1 - beta)))
            term3 = ((2 - 3 * rho ** 2) / 24) * (nu ** 2)
            
            sigma_atm = (alpha / (f ** (1 - beta))) * (1 + (term1 + term2 + term3) * t)
            return sigma_atm
            
        else:
            fk_beta = (f * k) ** ((1 - beta) / 2)
            log_fk = math.log(f / k)
            
            z = (nu / alpha) * fk_beta * log_fk
            
            # Avoid division by zero in x(z) calculation
            xz = math.log((math.sqrt(1 - 2 * rho * z + z ** 2) + z - rho) / (1 - rho))
            if math.isclose(xz, 0, abs_tol=1e-8):
                # When z is close to 0, use Taylor expansion
                xz = z
                
            term1 = ((1 - beta) ** 2 / 24) * (alpha ** 2) / ((f * k) ** (1 - beta))
            term2 = (rho * beta * nu * alpha) / (4 * fk_beta)
            term3 = ((2 - 3 * rho ** 2) / 24) * (nu ** 2)
            
            denominator = fk_beta * (1 + ((1 - beta) ** 2 / 24) * (log_fk ** 2) + ((1 - beta) ** 4 / 1920) * (log_fk ** 4))
            
            sigma = (alpha / denominator) * (z / xz) * (1 + (term1 + term2 + term3) * t)
            return sigma
    except Exception as e:
        print(f"SABR calculation failed: {e}")
        return alpha # fallback to initial vol
