/**
 * Pure Black-Scholes option greeks — self-contained port of
 * backend/app/services/kite_engine/greeks.py.
 *
 * IV is a decimal (0.18 = 18%), DTE in calendar days; theta is per-day,
 * vega per 1% vol move.
 */
const R = 0.065; // India ~risk-free

function normCdf(x: number): number {
  // Abramowitz & Stegun 7.1.26 approximation
  const a1 = 0.254829592;
  const a2 = -0.284496736;
  const a3 = 1.421413741;
  const a4 = -1.453152027;
  const a5 = 1.061405429;
  const p = 0.3275911;
  const sign = x < 0 ? -1 : 1;
  x = Math.abs(x) / Math.sqrt(2);
  const t = 1.0 / (1.0 + p * x);
  const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
  return 0.5 * (1.0 + sign * y);
}

function normPdf(x: number): number {
  return Math.exp(-0.5 * x * x) / Math.sqrt(2.0 * Math.PI);
}

export interface BSGreeks {
  delta: number;
  gamma: number;
  theta: number; // per calendar day
  vega: number;  // per 1% vol move
}

export interface BSInputs {
  spot: number;
  strike: number;
  dteDays: number;
  iv: number;       // decimal (0.18 = 18%)
  optionType: string; // "CE"/"call" or "PE"/"put"
  rate?: number;
}

export function blackScholesGreeks(inputs: BSInputs): BSGreeks {
  const { spot, strike, dteDays, iv, optionType } = inputs;
  const rate = inputs.rate ?? R;
  const isCall = optionType.toUpperCase().startsWith('C');
  const t = Math.max(dteDays, 0) / 365;

  if (t <= 0 || iv <= 0 || spot <= 0 || strike <= 0) {
    let delta: number;
    if (isCall) {
      delta = spot > strike ? 1.0 : 0.0;
    } else {
      delta = spot < strike ? -1.0 : 0.0;
    }
    return { delta, gamma: 0, theta: 0, vega: 0 };
  }

  const sigRt = iv * Math.sqrt(t);
  const d1 = (Math.log(spot / strike) + (rate + 0.5 * iv * iv) * t) / sigRt;
  const d2 = d1 - sigRt;
  const pdf = normPdf(d1);

  const delta = isCall ? normCdf(d1) : normCdf(d1) - 1.0;
  const gamma = pdf / (spot * sigRt);
  const vega = spot * pdf * Math.sqrt(t) / 100.0;

  let theta: number;
  if (isCall) {
    theta = (-spot * pdf * iv / (2 * Math.sqrt(t))
      - rate * strike * Math.exp(-rate * t) * normCdf(d2)) / 365.0;
  } else {
    theta = (-spot * pdf * iv / (2 * Math.sqrt(t))
      + rate * strike * Math.exp(-rate * t) * normCdf(-d2)) / 365.0;
  }

  return { delta, gamma, theta, vega };
}

export function bsPrice(inputs: BSInputs): number {
  const { spot, strike, dteDays, iv, optionType } = inputs;
  const rate = inputs.rate ?? R;
  const isCall = optionType.toUpperCase().startsWith('C');
  const t = Math.max(dteDays, 0) / 365;

  if (t <= 0 || iv <= 0 || spot <= 0 || strike <= 0) {
    return Math.max(0, isCall ? spot - strike : strike - spot);
  }

  const sigRt = iv * Math.sqrt(t);
  const d1 = (Math.log(spot / strike) + (rate + 0.5 * iv * iv) * t) / sigRt;
  const d2 = d1 - sigRt;
  const disc = strike * Math.exp(-rate * t);

  if (isCall) {
    return spot * normCdf(d1) - disc * normCdf(d2);
  }
  return disc * normCdf(-d2) - spot * normCdf(-d1);
}

/**
 * Backsolve IV from market price via bisection.
 * Mirrors backend app/services/kite_engine/greeks.py:implied_vol.
 */
export function impliedVol(inputs: Omit<BSInputs, 'iv'> & { price: number }): number {
  const { spot, strike, dteDays, optionType, price } = inputs;
  const rate = inputs.rate ?? R;
  const t = Math.max(dteDays, 0) / 365;
  const isCall = optionType.toUpperCase().startsWith('C');
  const intrinsic = Math.max(0, isCall ? spot - strike : strike - spot);

  if (price <= 0 || t <= 0 || spot <= 0 || strike <= 0 || price < intrinsic - 1e-6) {
    return 0;
  }

  let lo = 0.001;
  let hi = 5.0;
  for (let i = 0; i < 64; i++) {
    const mid = 0.5 * (lo + hi);
    if (bsPrice({ spot, strike, dteDays, iv: mid, optionType, rate }) > price) {
      hi = mid;
    } else {
      lo = mid;
    }
  }
  return 0.5 * (lo + hi);
}
