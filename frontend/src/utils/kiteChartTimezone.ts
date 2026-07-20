import { createChart } from 'lightweight-charts';

const PATCH_FLAG = Symbol.for('sterling.kiteChartIstPatched');
const IST_ZONE = 'Asia/Kolkata';

function toDate(time: unknown): Date | null {
  if (typeof time === 'number' && Number.isFinite(time)) return new Date(time * 1000);
  if (time && typeof time === 'object') {
    const value = time as { year?: number; month?: number; day?: number };
    if (value.year && value.month && value.day) {
      return new Date(Date.UTC(value.year, value.month - 1, value.day));
    }
  }
  return null;
}

function formatIst(time: unknown, options: Intl.DateTimeFormatOptions): string {
  const date = toDate(time);
  if (!date) return '';
  return new Intl.DateTimeFormat('en-IN', { timeZone: IST_ZONE, ...options }).format(date);
}

export function formatKiteChartTime(time: unknown): string {
  return formatIst(time, {
    day: '2-digit',
    month: 'short',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function formatTick(time: unknown, tickMarkType: number): string {
  if (tickMarkType === 0) return formatIst(time, { year: 'numeric' });
  if (tickMarkType === 1) return formatIst(time, { month: 'short' });
  if (tickMarkType === 2) return formatIst(time, { day: 'numeric' });
  return formatIst(time, { hour: '2-digit', minute: '2-digit', hour12: false });
}

/**
 * Lightweight Charts otherwise formats timestamps in the browser/OS timezone.
 * Kite candles carry canonical Unix epochs, so only the presentation layer must
 * be fixed to Asia/Kolkata; shifting candle data would break indicator/marker
 * alignment. The prototype hook covers every chart instance, including the
 * legacy advanced chart and its indicator sub-panes.
 */
export function installKiteChartTimezone(): void {
  if (typeof document === 'undefined') return;

  const host = document.createElement('div');
  Object.assign(host.style, {
    position: 'fixed',
    left: '-10000px',
    top: '-10000px',
    width: '2px',
    height: '2px',
  });
  (document.body || document.documentElement).appendChild(host);

  let probe: any;
  try {
    probe = createChart(host, { width: 2, height: 2 });
    const prototype: any = Object.getPrototypeOf(probe);
    if (!prototype || prototype[PATCH_FLAG]) return;

    const originalAddSeries = prototype.addSeries;
    if (typeof originalAddSeries !== 'function') return;

    prototype.addSeries = function patchedAddSeries(...args: any[]) {
      this.applyOptions({
        localization: { timeFormatter: formatKiteChartTime },
        timeScale: {
          tickMarkFormatter: (time: unknown, tickMarkType: number) => formatTick(time, tickMarkType),
        },
      });
      return originalAddSeries.apply(this, args);
    };
    prototype[PATCH_FLAG] = true;
  } finally {
    try { probe?.remove(); } catch {}
    host.remove();
  }
}
