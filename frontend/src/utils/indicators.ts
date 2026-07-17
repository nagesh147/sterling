export type TimePoint = { time: number; value: number };
export type BandPoint = { time: number; upper: number | null; middle: number | null; lower: number | null };
export type STPoint = { time: number; value: number; direction: 'up' | 'down' };
export type MACDPoint = { time: number; macd: number | null; signal: number | null; hist: number | null };

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export function heikinAshi(candles: Candle[]): Candle[] {
  if (!candles.length) return [];
  const ha: Candle[] = [];
  let prevHaOpen = (candles[0].open + candles[0].close) / 2;
  let prevHaClose = (candles[0].open + candles[0].high + candles[0].low + candles[0].close) / 4;

  for (let i = 0; i < candles.length; i++) {
    const c = candles[i];
    const haClose = (c.open + c.high + c.low + c.close) / 4;
    const haOpen = i === 0 ? prevHaOpen : (prevHaOpen + prevHaClose) / 2;
    const haHigh = Math.max(c.high, haOpen, haClose);
    const haLow = Math.min(c.low, haOpen, haClose);
    ha.push({
      time: c.time,
      open: haOpen,
      high: haHigh,
      low: haLow,
      close: haClose,
      volume: c.volume,
    });
    prevHaOpen = haOpen;
    prevHaClose = haClose;
  }
  return ha;
}

export function sma(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= period - 1) {
      out.push(sum / period);
      sum -= values[i - period + 1];
    } else {
      out.push(null);
    }
  }
  return out;
}

export function ema(values: number[], period: number): (number | null)[] {
  if (values.length === 0) return [];
  const k = 2 / (period + 1);
  const out: (number | null)[] = new Array(values.length).fill(null);
  let prev = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
  out[period - 1] = prev;
  for (let i = period; i < values.length; i++) {
    prev = values[i] * k + prev * (1 - k);
    out[i] = prev;
  }
  return out;
}

export function bollingerBands(closes: number[], period = 20, stdDev = 2): BandPoint[] {
  const out: BandPoint[] = [];
  const m = sma(closes, period);
  for (let i = 0; i < closes.length; i++) {
    if (m[i] == null) {
      // Warm-up bar - emit null (not a literal 0) so callers can filter it out,
      // matching the ema()/rsi() convention. A concrete 0 here previously got
      // plotted as a real data point, dragging the price-scale autoscale down
      // to 0 on first paint.
      out.push({ time: 0, upper: null, middle: null, lower: null });
      continue;
    }
    const slice = closes.slice(Math.max(0, i - period + 1), i + 1);
    const mean = m[i] as number;
    const variance = slice.reduce((s, v) => s + Math.pow(v - mean, 2), 0) / slice.length;
    const sd = Math.sqrt(variance);
    out.push({
      time: 0, // caller fills time
      upper: mean + stdDev * sd,
      middle: mean,
      lower: mean - stdDev * sd,
    });
  }
  return out;
}

export function vwap(candles: { time: number; high: number; low: number; close: number; volume: number }[]): TimePoint[] {
  let cumTPV = 0;
  let cumVol = 0;
  return candles.map((c) => {
    const tp = (c.high + c.low + c.close) / 3;
    cumTPV += tp * c.volume;
    cumVol += c.volume;
    const val = cumVol > 0 ? cumTPV / cumVol : c.close;
    return { time: c.time, value: val };
  });
}

export function rsi(closes: number[], period = 14): (number | null)[] {
  const out: (number | null)[] = new Array(closes.length).fill(null);
  if (closes.length < period + 1) return out;
  let gain = 0, loss = 0;
  for (let i = 1; i <= period; i++) {
    const ch = closes[i] - closes[i - 1];
    if (ch > 0) gain += ch; else loss -= ch;
  }
  let avgGain = gain / period;
  let avgLoss = loss / period;
  out[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);

  for (let i = period + 1; i < closes.length; i++) {
    const ch = closes[i] - closes[i - 1];
    const g = ch > 0 ? ch : 0;
    const l = ch < 0 ? -ch : 0;
    avgGain = (avgGain * (period - 1) + g) / period;
    avgLoss = (avgLoss * (period - 1) + l) / period;
    out[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }
  return out;
}

export function macd(closes: number[], fast = 12, slow = 26, signalP = 9): MACDPoint[] {
  const emaFast = ema(closes, fast);
  const emaSlow = ema(closes, slow);
  const macdLine: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    macdLine.push(emaFast[i] != null && emaSlow[i] != null ? (emaFast[i] as number) - (emaSlow[i] as number) : null);
  }
  const sig = ema(macdLine.map((v) => v ?? 0), signalP); // approximate on filled

  const out: MACDPoint[] = [];
  for (let i = 0; i < closes.length; i++) {
    const m = macdLine[i];
    const s = sig[i];
    if (m == null || s == null) {
      // Warm-up bar - emit null (not a literal 0); the render call sites
      // already filter with `!= null`, but a concrete 0 defeated that check
      // since `0 != null` is true in JS.
      out.push({ time: 0, macd: null, signal: null, hist: null });
    } else {
      out.push({ time: 0, macd: m, signal: s, hist: m - s });
    }
  }
  return out;
}

export function atr(highs: number[], lows: number[], closes: number[], period = 14): (number | null)[] {
  const n = closes.length;
  if (n < period + 1) return closes.map(() => null);
  const tr: number[] = new Array(n).fill(0);
  for (let i = 1; i < n; i++) {
    tr[i] = Math.max(highs[i] - lows[i], Math.abs(highs[i] - closes[i - 1]), Math.abs(lows[i] - closes[i - 1]));
  }
  const out: (number | null)[] = new Array(n).fill(null);
  let seed = 0;
  for (let i = 1; i <= period; i++) seed += tr[i];
  out[period] = seed / period;
  for (let i = period + 1; i < n; i++) {
    out[i] = ((out[i - 1] as number) * (period - 1) + tr[i]) / period;
  }
  return out;
}

// A lightweight-charts line datum, or a whitespace gap ({ time } only).
export type LinePointOrGap = { time: number; value?: number };

/**
 * Split a SuperTrend series into two FULL-LENGTH line datasets (up-trend green,
 * down-trend red) for two-colour rendering.
 *
 * Bars belonging to the OTHER trend are emitted as whitespace points ({ time }
 * with no `value`), which makes lightweight-charts BREAK the line at that bar
 * instead of drawing a straight segment across it. Handing a series only its
 * own-direction points (the old approach) makes it connect consecutive points
 * across the gaps, so BOTH the green and red series span the whole chart and you
 * see two crossing lines per indicator. Keeping both arrays full-length, with
 * whitespace on the inactive bars, yields a single visually-correct SuperTrend
 * line whose colour flips with the trend.
 */
export function supertrendSegments(
  stData: { value: number; direction: 'up' | 'down' }[],
  times: number[]
): { bull: LinePointOrGap[]; bear: LinePointOrGap[] } {
  const bull: LinePointOrGap[] = [];
  const bear: LinePointOrGap[] = [];
  for (let i = 0; i < stData.length; i++) {
    const time = times[i];
    if (stData[i].direction === 'up') {
      bull.push({ time, value: stData[i].value });
      bear.push({ time });
    } else {
      bull.push({ time });
      bear.push({ time, value: stData[i].value });
    }
  }
  return { bull, bear };
}

// SuperTrend (classic)
export function supertrend(
  highs: number[],
  lows: number[],
  closes: number[],
  period = 10,
  multiplier = 3
): STPoint[] {
  // Mirrors the backend engine (app/engines/indicators/supertrend.py) EXACTLY:
  // separate final upper/lower bands, standard clamping, trend seeded +1 at
  // `period`. The previous version reused the single ST value for both bands,
  // which produced a different (wrong) indicator — verified to disagree with the
  // engine on ~40-50% of bars — so charts never matched the engine's decisions.
  const n = closes.length;
  const atrVals = atr(highs, lows, closes, period);
  const out: STPoint[] = new Array(n);

  const basicUpper = new Array<number>(n);
  const basicLower = new Array<number>(n);
  const finalUpper = new Array<number>(n);
  const finalLower = new Array<number>(n);
  const trend = new Array<number>(n).fill(0);

  for (let i = 0; i < n; i++) {
    const atrV = atrVals[i] ?? 0; // 0 during warmup, matching backend compute_atr
    const mid = (highs[i] + lows[i]) / 2;
    basicUpper[i] = mid + multiplier * atrV;
    basicLower[i] = mid - multiplier * atrV;
    finalUpper[i] = basicUpper[i];
    finalLower[i] = basicLower[i];
  }

  const start = period;
  if (start >= n) {
    for (let i = 0; i < n; i++) out[i] = { time: 0, value: closes[i], direction: 'up' };
    return out;
  }
  // Warmup bars have no seeded trend yet — render neutral (green) on the lower band.
  for (let i = 0; i <= start; i++) out[i] = { time: 0, value: finalLower[i], direction: 'up' };
  trend[start] = 1;

  for (let i = start + 1; i < n; i++) {
    const prevClose = closes[i - 1];
    finalUpper[i] = (basicUpper[i] < finalUpper[i - 1] || prevClose > finalUpper[i - 1])
      ? basicUpper[i] : finalUpper[i - 1];
    finalLower[i] = (basicLower[i] > finalLower[i - 1] || prevClose < finalLower[i - 1])
      ? basicLower[i] : finalLower[i - 1];

    if (trend[i - 1] === 1) trend[i] = closes[i] < finalLower[i] ? -1 : 1;
    else trend[i] = closes[i] > finalUpper[i] ? 1 : -1;

    out[i] = {
      time: 0,
      value: trend[i] === 1 ? finalLower[i] : finalUpper[i],
      direction: trend[i] === 1 ? 'up' : 'down',
    };
  }
  return out;
}
