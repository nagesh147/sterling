export type TimePoint = { time: number; value: number };
export type BandPoint = { time: number; upper: number; middle: number; lower: number };
export type STPoint = { time: number; value: number; direction: 'up' | 'down' };
export type MACDPoint = { time: number; macd: number; signal: number; hist: number };

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
      out.push({ time: 0, upper: 0, middle: 0, lower: 0 });
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
      out.push({ time: 0, macd: 0, signal: 0, hist: 0 });
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

// SuperTrend (classic)
export function supertrend(
  highs: number[],
  lows: number[],
  closes: number[],
  period = 10,
  multiplier = 3
): STPoint[] {
  const n = closes.length;
  const atrVals = atr(highs, lows, closes, period);
  const out: STPoint[] = [];
  let prevSt = 0;
  let direction: 'up' | 'down' = 'up';

  for (let i = 0; i < n; i++) {
    const atrV = atrVals[i];
    if (atrV == null) {
      out.push({ time: 0, value: closes[i], direction: 'up' });
      continue;
    }
    const mid = (highs[i] + lows[i]) / 2;
    let upper = mid + multiplier * atrV;
    let lower = mid - multiplier * atrV;

    if (i > 0) {
      const prevClose = closes[i - 1];
      const prevUpper = out[i - 1]?.value ?? upper; // fallback
      upper = closes[i - 1] > prevUpper ? Math.min(upper, prevUpper) : upper;
      const prevLower = out[i - 1]?.value ?? lower;
      lower = closes[i - 1] < prevLower ? Math.max(lower, prevLower) : lower;
    }

    let st = direction === 'up' ? lower : upper;
    if (closes[i] > st) {
      direction = 'up';
      st = lower;
    } else if (closes[i] < st) {
      direction = 'down';
      st = upper;
    } else {
      // maintain
    }
    prevSt = st;
    out.push({ time: 0, value: st, direction });
  }
  return out;
}
