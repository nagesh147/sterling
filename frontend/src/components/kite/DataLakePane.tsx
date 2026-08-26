/**
 * DATA tab — a visual browser for the offline market-data lake.
 *
 * Answers, in order of how often they get asked: is the data reachable, how much of it is
 * there, which instruments do I actually have, and what does one of them look like.
 *
 * The chart is hand-drawn SVG rather than a charting library. It only ever renders a
 * pre-downsampled series (the backend strides the range down to the requested point
 * budget, so the whole period stays visible), which makes a dependency unnecessary — and
 * it sidesteps the lightweight-charts v5 pitfall where a single line series connects
 * straight across gaps, which would silently paint over missing data. Here a gap is drawn
 * as a gap.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { c, tint } from '../../styles/terminalUI';
import {
  useDataLake,
  type LakeBars,
  type LakeSymbol,
  type TierPlan,
} from '../../hooks/useDataLake';
import FolderPicker from '../datalake/FolderPicker';

const MONO = 'ui-monospace, SFMono-Regular, Menlo, monospace';

const card: React.CSSProperties = {
  background: c.surface,
  border: `1px solid ${c.border}`,
  borderRadius: 14,
  padding: 16,
  fontFamily: c.fontFamily,
};

const btn = (tone: string, solid = false): React.CSSProperties => ({
  background: solid ? tone : 'transparent',
  color: solid ? c.bg : tone,
  border: `1px solid ${tone}`,
  borderRadius: 9,
  padding: '6px 12px',
  fontSize: 12,
  fontWeight: 600,
  cursor: 'pointer',
  fontFamily: c.fontFamily,
});

function nf(n: number | undefined | null): string {
  return (n ?? 0).toLocaleString();
}

function Stat({ label, value, tone, sub }: { label: string; value: string; tone?: string; sub?: string }) {
  return (
    <div style={{ background: c.raised, border: `1px solid ${c.border}`, borderRadius: 11, padding: '10px 13px', minWidth: 118 }}>
      <div style={{ color: c.dim, fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</div>
      <div style={{ color: tone || c.bright, fontSize: 17, fontWeight: 750, marginTop: 3 }}>{value}</div>
      {sub && <div style={{ color: c.dim, fontSize: 10.5, marginTop: 1 }}>{sub}</div>}
    </div>
  );
}

/** Chunk-status breakdown. Each status means something different, so it is not one bar. */
function StatusBar({ counts, total }: { counts: Record<string, number>; total: number }) {
  const order: Array<[string, string, string]> = [
    ['done', c.green, 'fetched with data'],
    ['empty', c.blue, 'no trades in the window — normal for illiquid scrips'],
    ['skipped', c.muted, 'Kite will never serve these (SME scrips)'],
    ['failed', c.red, 'errored — recoverable with --retry-failed'],
    ['pending', c.raised, 'not fetched yet'],
  ];
  if (!total) return null;
  return (
    <div>
      <div style={{ display: 'flex', height: 9, borderRadius: 5, overflow: 'hidden', border: `1px solid ${c.border}` }}>
        {order.map(([k, tone]) => {
          const n = counts[k] ?? 0;
          if (!n) return null;
          return <div key={k} title={`${k}: ${nf(n)}`} style={{ width: `${(100 * n) / total}%`, background: tone }} />;
        })}
      </div>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 8 }}>
        {order.map(([k, tone, why]) => {
          const n = counts[k] ?? 0;
          if (!n) return null;
          return (
            <span key={k} title={why} style={{ color: c.dim, fontSize: 11, display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: tone, display: 'inline-block' }} />
              {k} {nf(n)}
            </span>
          );
        })}
      </div>
    </div>
  );
}

/** Close-price line + volume, drawn straight to SVG. Gaps stay gaps. */
function BarChart({ data }: { data: LakeBars }) {
  const W = 900;
  const H = 260;
  const VH = 46;
  const pad = { l: 52, r: 10, t: 10, b: 18 };

  const geom = useMemo(() => {
    const bars = data.bars;
    if (bars.length < 2) return null;
    const xs = bars.map((b) => new Date(b.t).getTime());
    const lo = Math.min(...bars.map((b) => b.l));
    const hi = Math.max(...bars.map((b) => b.h));
    const vMax = Math.max(...bars.map((b) => b.v), 1);
    const x0 = xs[0];
    const span = xs[xs.length - 1] - x0 || 1;
    const plotW = W - pad.l - pad.r;
    const plotH = H - VH - pad.t - pad.b;
    const px = (t: number) => pad.l + ((t - x0) / span) * plotW;
    const py = (p: number) => pad.t + plotH - ((p - lo) / (hi - lo || 1)) * plotH;

    // Break the path wherever the gap between samples is far larger than typical — an
    // overnight or missing stretch. Drawing through it would invent prices.
    const deltas = xs.slice(1).map((t, i) => t - xs[i]);
    const median = [...deltas].sort((a, b) => a - b)[Math.floor(deltas.length / 2)] || 1;
    const breakAt = median * 4;
    const segments: string[] = [];
    let cur = `M ${px(xs[0])} ${py(bars[0].c)}`;
    for (let i = 1; i < bars.length; i += 1) {
      if (xs[i] - xs[i - 1] > breakAt) {
        segments.push(cur);
        cur = `M ${px(xs[i])} ${py(bars[i].c)}`;
      } else {
        cur += ` L ${px(xs[i])} ${py(bars[i].c)}`;
      }
    }
    segments.push(cur);

    const vy0 = H - pad.b;
    const vols = bars.map((b, i) => ({
      x: px(xs[i]),
      h: (b.v / vMax) * VH,
      up: i === 0 ? true : b.c >= bars[i - 1].c,
    }));
    const first = bars[0].c;
    const last = bars[bars.length - 1].c;
    return { segments, lo, hi, vols, vy0, px, py, xs, first, last, up: last >= first, plotH };
  }, [data]);

  if (!geom) {
    return <div style={{ color: c.dim, fontSize: 12 }}>Not enough bars to plot.</div>;
  }

  const stroke = geom.up ? c.green : c.red;
  const ticks = [geom.hi, (geom.hi + geom.lo) / 2, geom.lo];
  const fmtDate = (t: number) =>
    new Date(t).toLocaleDateString(undefined, { day: '2-digit', month: 'short' });

  return (
    <div style={{ overflowX: 'auto' }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', minWidth: 520, display: 'block' }}>
        {ticks.map((p, i) => {
          const y = geom.py(p);
          return (
            <g key={i}>
              <line x1={pad.l} x2={W - pad.r} y1={y} y2={y} stroke={c.border} strokeWidth={1} strokeDasharray="3 4" />
              <text x={pad.l - 7} y={y + 3.5} textAnchor="end" fill={c.dim} fontSize={10} fontFamily={MONO}>
                {p.toFixed(2)}
              </text>
            </g>
          );
        })}
        {geom.vols.map((v, i) => (
          <rect key={i} x={v.x} y={geom.vy0 - v.h} width={Math.max(0.6, (W - pad.l - pad.r) / geom.vols.length - 0.3)}
                height={v.h} fill={v.up ? c.green : c.red} opacity={0.32} />
        ))}
        {geom.segments.map((d, i) => (
          <path key={i} d={d} fill="none" stroke={stroke} strokeWidth={1.4} strokeLinejoin="round" />
        ))}
        <text x={pad.l} y={H - 4} fill={c.dim} fontSize={10} fontFamily={MONO}>{fmtDate(geom.xs[0])}</text>
        <text x={W - pad.r} y={H - 4} textAnchor="end" fill={c.dim} fontSize={10} fontFamily={MONO}>
          {fmtDate(geom.xs[geom.xs.length - 1])}
        </text>
      </svg>
    </div>
  );
}

export function DataLakePane() {
  const {
    summary, loading, error, refresh, listSymbols, fetchBars, tierPlan,
    listVolumes, browse, setRoot, activateRoot,
  } = useDataLake('minute');

  const [symbols, setSymbols] = useState<LakeSymbol[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<string>('');
  const [bars, setBars] = useState<LakeBars | null>(null);
  const [barsError, setBarsError] = useState('');
  const [plan, setPlan] = useState<TierPlan | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const debounce = useRef<number | undefined>(undefined);

  const available = summary?.available ?? false;
  const stats = summary?.stats ?? {};

  const loadSymbols = useCallback(
    async (needle: string) => {
      try {
        const page = await listSymbols({ search: needle, limit: 300 });
        setSymbols(page.symbols ?? []);
        setTotal(page.total ?? 0);
      } catch {
        setSymbols([]);
        setTotal(0);
      }
    },
    [listSymbols],
  );

  useEffect(() => {
    if (!available) return;
    void loadSymbols('');
    const today = new Date();
    const start = new Date(today.getTime() - 182 * 86_400_000);
    const iso = (d: Date) => d.toISOString().slice(0, 10);
    tierPlan(iso(start), iso(today)).then(setPlan).catch(() => setPlan(null));
  }, [available, loadSymbols, tierPlan]);

  // Debounced search so typing does not fire a request per keystroke.
  useEffect(() => {
    if (!available) return;
    window.clearTimeout(debounce.current);
    debounce.current = window.setTimeout(() => void loadSymbols(search), 250);
    return () => window.clearTimeout(debounce.current);
  }, [search, available, loadSymbols]);

  const openSymbol = useCallback(
    async (sym: LakeSymbol) => {
      const key = String(sym.instrument_token);
      setSelected(key);
      setBars(null);
      setBarsError('');
      try {
        setBars(await fetchBars(key, { limit: 1200 }));
      } catch (e) {
        setBarsError(e instanceof Error ? e.message : 'could not load bars');
      }
    },
    [fetchBars],
  );

  const counts = (stats.chunks_by_status ?? {}) as Record<string, number>;
  const chunkTotal = stats.chunks_total ?? 0;

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14, fontFamily: c.fontFamily }}>
      {/* ── header ─────────────────────────────────────────────────────── */}
      <div style={{ ...card, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ color: c.bright, fontSize: 16, fontWeight: 750, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: 4, background: loading ? c.muted : available ? c.green : c.amber }} />
            Offline Market Data
          </div>
          <div style={{ color: c.dim, fontSize: 11.5, marginTop: 3, overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {loading ? 'checking…' : available ? `${summary?.label || 'data folder'} · ${summary?.root}` : 'no data folder available'}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => void refresh()} style={btn(c.muted)}>Refresh</button>
          <button onClick={() => setPickerOpen(true)} style={btn(c.blue, !available)}>
            {available ? 'Change folder' : 'Choose folder'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ ...card, color: c.red, background: tint(c.red, 9), borderColor: tint(c.red, 35), fontSize: 12 }}>
          Cannot reach the backend: {error}
        </div>
      )}

      {/* ── drive missing: guidance, never a red error ──────────────────── */}
      {!loading && !available && summary && (
        <div style={{ ...card, background: tint(c.amber, 8), borderColor: tint(c.amber, 32) }}>
          <div style={{ color: c.amber, fontSize: 13.5, fontWeight: 700 }}>
            {summary.volume_present_unmounted ? 'The drive is connected but not mounted' : summary.reason || 'The data folder is not available'}
          </div>
          <ul style={{ margin: '10px 0 0', paddingLeft: 18, color: c.text, fontSize: 12 }}>
            {(summary.guidance ?? []).map((g, i) => <li key={i} style={{ marginBottom: 4 }}>{g}</li>)}
          </ul>
          {(summary.known ?? []).length > 0 && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
              {summary.known.slice(0, 4).map((k) => (
                <button key={k.lake_id} onClick={() => void activateRoot(k.lake_id).catch(() => setPickerOpen(true))}
                        style={btn(c.muted)} title={k.last_path}>
                  {k.label || k.last_path}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {available && (
        <>
          {/* ── totals ───────────────────────────────────────────────── */}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Stat label="Instruments" value={nf(stats.symbols)} />
            <Stat label="Bars stored" value={nf(stats.candles)} />
            <Stat label="On disk" value={`${stats.gib ?? 0} GiB`} sub={`${summary?.free_gib ?? 0} GiB free`} />
            <Stat label="Complete" value={`${stats.pct_complete ?? 0}%`}
                  tone={(stats.pct_complete ?? 0) >= 99.5 ? c.green : c.amber}
                  sub={`${nf(stats.chunks_remaining)} chunks left`} />
            <Stat label="Universe" value={nf(stats.instruments_known)} sub="known to the master" />
          </div>

          {/* ── chunk status ─────────────────────────────────────────── */}
          <div style={card}>
            <div style={{ color: c.bright, fontSize: 13, fontWeight: 700, marginBottom: 10 }}>
              Download coverage · {nf(stats.chunks_settled)} of {nf(chunkTotal)} chunks settled
            </div>
            <StatusBar counts={counts} total={chunkTotal} />
            {plan && (
              <div style={{ color: c.dim, fontSize: 11, marginTop: 12, lineHeight: 1.6 }}>
                Plan: {plan.tiers.map((t) => `${t.tier}. ${t.universe} (${nf(t.instruments)})`).join('  ·  ')}
                <br />
                {nf(plan.total_requests)} requests total · {plan.total_eta} at {plan.rate} req/s · ~{plan.total_gib.toFixed(1)} GiB
              </div>
            )}
          </div>

          {/* ── instruments + chart ──────────────────────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 340px) 1fr', gap: 14, alignItems: 'start' }}>
            <div style={{ ...card, padding: 0, overflow: 'hidden' }}>
              <div style={{ padding: 12, borderBottom: `1px solid ${c.border}` }}>
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search symbol or token…"
                  style={{
                    width: '100%', boxSizing: 'border-box', background: c.raised,
                    border: `1px solid ${c.border}`, borderRadius: 8, color: c.bright,
                    padding: '7px 10px', fontSize: 12, fontFamily: c.fontFamily,
                  }}
                />
                <div style={{ color: c.dim, fontSize: 10.5, marginTop: 6 }}>
                  {nf(symbols.length)} shown of {nf(total)} stored
                </div>
              </div>
              <div style={{ maxHeight: 420, overflowY: 'auto' }}>
                {symbols.length === 0 && (
                  <div style={{ color: c.dim, fontSize: 12, padding: 14 }}>
                    {search ? 'No match.' : 'Nothing downloaded yet.'}
                  </div>
                )}
                {symbols.map((s) => {
                  const on = selected === String(s.instrument_token);
                  return (
                    <button
                      key={`${s.instrument_token}-${s.exchange}`}
                      onClick={() => void openSymbol(s)}
                      // The row is built from nested divs, so without this it has no
                      // accessible name at all — a screen reader would announce an
                      // anonymous button, and the a11y tree showed exactly that.
                      aria-label={`${s.tradingsymbol} on ${s.exchange}, ${nf(s.rows)} bars`}
                      aria-pressed={on}
                      title={`${s.tradingsymbol} · ${s.exchange} · ${nf(s.rows)} bars`}
                      style={{
                        display: 'block', width: '100%', textAlign: 'left', cursor: 'pointer',
                        background: on ? tint(c.green, 13) : 'transparent',
                        border: 'none', borderBottom: `1px solid ${c.border2}`,
                        padding: '8px 12px', fontFamily: c.fontFamily,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                        <span style={{ color: c.bright, fontSize: 12, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {s.tradingsymbol}
                        </span>
                        <span style={{ color: c.dim, fontSize: 10.5, fontFamily: MONO, whiteSpace: 'nowrap' }}>{nf(s.rows)}</span>
                      </div>
                      <div style={{ color: c.dim, fontSize: 10, marginTop: 1 }}>
                        {s.exchange} · {(s.first_ts || '').slice(0, 10)} → {(s.last_ts || '').slice(0, 10)}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            <div style={card}>
              {!selected && (
                <div style={{ color: c.dim, fontSize: 12.5 }}>
                  Pick an instrument to plot its stored history.
                </div>
              )}
              {selected && !bars && !barsError && (
                <div style={{ color: c.dim, fontSize: 12.5 }}>Loading bars…</div>
              )}
              {barsError && (
                <div style={{ color: c.amber, fontSize: 12 }}>{barsError}</div>
              )}
              {bars && (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
                    <div>
                      <span style={{ color: c.bright, fontSize: 15, fontWeight: 750 }}>{bars.symbol}</span>
                      <span style={{ color: c.dim, fontSize: 11, marginLeft: 8 }}>{bars.exchange} · {bars.interval}</span>
                    </div>
                    <div style={{ color: c.dim, fontSize: 11, fontFamily: MONO }}>
                      {nf(bars.rows_total)} bars
                      {bars.downsampled_every > 1 && ` · plotted every ${bars.downsampled_every}th`}
                    </div>
                  </div>
                  <BarChart data={bars} />
                  {bars.downsampled_every > 1 && (
                    <div style={{ color: c.dim, fontSize: 10.5, marginTop: 8 }}>
                      Thinned for display — the full range is covered, and every stored bar is
                      still on disk.
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </>
      )}

      <FolderPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onChoose={(path, label) => setRoot(path, label)}
        listVolumes={listVolumes}
        browse={browse}
      />
    </div>
  );
}

export default DataLakePane;
