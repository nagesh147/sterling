import { useEffect, useMemo, useState } from 'react';
import { fetchPcrDesk } from '../../lib/pcr/fetchPcr';
import {
  BAND_COPY,
  bandTitle,
  buildGrid,
  expiryKind,
  formatDelta,
  formatExpiry,
  formatPcr,
  metricValue,
  pcrBand,
  putShare,
  readPcr,
} from '../../lib/pcr/slots';
import { PCR_INDICES, type PcrDeskPayload, type PcrIndex, type PcrMetric, type PcrSeries, type PcrSlot } from '../../lib/pcr/types';
import { formatIstIsoDate, getIstParts } from '../../lib/astro/time';

type View = "grid" | "board";

function istStamp(now: Date): string {
  const p = getIstParts(now);
  return `${String(p.day).padStart(2, "0")}/${String(p.month).padStart(2, "0")}/${p.year} ${String(p.hour).padStart(2, "0")}:${String(p.minute).padStart(2, "0")}:${String(p.second).padStart(2, "0")}`;
}

function nowMinutes(now: Date): number {
  const p = getIstParts(now);
  return p.hour * 60 + p.minute;
}

function fmtLtp(n: number | null): string {
  if (n == null) return "—";
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function Spark({ slots }: { slots: PcrSlot[] }) {
  const pts = slots.map((s) => s.pcr).filter((v): v is number => v != null);
  if (pts.length < 2) return null;
  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const pad = (max - min) * 0.15 || 0.05;
  const lo = min - pad;
  const hi = max + pad;
  const w = 160;
  const h = 36;
  const d = pts
    .map((v, i) => {
      const x = (i / (pts.length - 1)) * w;
      const y = h - ((v - lo) / (hi - lo || 1)) * (h - 4) - 2;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  const last = pts[pts.length - 1];
  const y1 = h - ((1 - lo) / (hi - lo || 1)) * (h - 4) - 2;
  return (
    <svg className="kp-spark" viewBox={`0 0 ${w} ${h}`} width={w} height={h} aria-hidden="true">
      <line x1="0" y1={y1} x2={w} y2={y1} className="kp-spark-ref" />
      <path d={d} />
      <circle cx={w} cy={h - ((last - lo) / (hi - lo || 1)) * (h - 4) - 2} r="2.2" />
    </svg>
  );
}

function Split({ pcr }: { pcr: number | null }) {
  const put = putShare(pcr);
  if (put == null) return null;
  const putPct = Math.round(put * 100);
  return (
    <div className="kp-split" title={`Puts ${putPct}% · Calls ${100 - putPct}% of OI`}>
      <span className="kp-split-put" style={{ width: `${putPct}%` }} />
      <span className="kp-split-call" style={{ width: `${100 - putPct}%` }} />
    </div>
  );
}

function livePcr(series: PcrSeries | undefined, slots: PcrSlot[], metric: PcrMetric): number | null {
  if (series?.latest) return metricValue(series.latest, metric);
  if (metric === "oi" && series?.livePcr != null) return series.livePcr;
  const live = slots.find((s) => s.live)?.pcr;
  if (live != null) return live;
  return [...slots].reverse().find((s) => s.pcr != null)?.pcr ?? null;
}


const CSS = `
.kite-pcr{display:flex;flex-direction:column;height:100%;min-height:100%;background:var(--k-bg);color:var(--k-text);font-family:inherit;font-size:14px}
.kite-pcr .ko{display:flex;flex-direction:column;height:100%;min-height:100%}
.kite-pcr .ko-head{padding:0 32px;border-bottom:1px solid var(--k-surface-hover);margin-top:12px}
.kite-pcr .ko-title-row{display:flex;align-items:center;gap:16px;margin:0 0 4px;min-height:32px}
.kite-pcr .ko-title-row h2{margin:0;font-size:24px;font-weight:400;color:var(--k-text);flex:1}
.kite-pcr .ko-tabs-row{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:-1px}
.kite-pcr .ko-tabs{display:flex;gap:32px;overflow-x:auto;min-width:0}
.kite-pcr .ko-tabs button{padding:0 0 12px;border:0;background:none;color:var(--k-text);font-size:14px;font-weight:400;border-bottom:2px solid transparent;white-space:nowrap;cursor:pointer;font-family:inherit}
.kite-pcr .ko-tabs button[data-on="true"]{color:var(--k-orange);border-bottom-color:var(--k-orange)}
.kite-pcr .ko-ins{display:flex;align-items:center;gap:16px;overflow-x:auto;padding-bottom:12px;flex-shrink:0}
.kite-pcr .ko-ins button{border:0;background:none;padding:0;font-size:13px;color:var(--k-text);white-space:nowrap;cursor:pointer;font-family:inherit}
.kite-pcr .ko-ins button:hover{color:var(--k-orange)}
.kite-pcr .ko-ins button[data-on="true"]{color:var(--k-orange);font-weight:500}
.kite-pcr .ko-body{flex:1;padding:20px 32px 40px;overflow:auto}
.kite-pcr .ko-sub{color:var(--k-dim);margin:0 0 16px;font-size:13px;line-height:1.5}
.kite-pcr .text-up{color:var(--k-green)}
.kite-pcr .text-down{color:var(--k-red)}
.kite-pcr .text-muted{color:var(--k-dim)}
.kp-clock{font-size:12px;color:var(--k-dim);font-variant-numeric:tabular-nums;white-space:nowrap}
.kp-chip-pcr{margin-left:6px;font-size:11px;font-weight:600;font-variant-numeric:tabular-nums;padding:1px 5px;border-radius:2px}
.kp-now{display:grid;grid-template-columns:minmax(140px,180px) 1fr auto;gap:16px 24px;align-items:center;padding:12px 0 16px;border-bottom:1px solid var(--k-surface-hover);margin-bottom:12px}
.kp-now-kicker{font-size:11px;color:var(--k-dim)}
.kp-now-val{font-size:32px;font-weight:600;font-variant-numeric:tabular-nums;line-height:1.1;margin:4px 0;padding:4px 10px;display:inline-block;border-radius:2px}
.kp-now-band{font-size:13px}
.kp-now-meta{display:grid;grid-template-columns:1fr 1fr;gap:10px 24px}
.kp-now-meta span{display:block;font-size:11px;color:var(--k-dim)}
.kp-now-meta b{font-size:13px;font-weight:500;font-variant-numeric:tabular-nums}
.kp-now-meta em{font-style:normal;font-size:12px;font-weight:500}
.kp-now-viz{display:flex;flex-direction:column;gap:8px;min-width:160px}
.kp-split{display:flex;height:6px;border-radius:2px;overflow:hidden;background:var(--k-surface-hover)}
.kp-split-put{background:#26a69a}
.kp-split-call{background:#ef5350}
.kp-spark{display:block}
.kp-spark path{fill:none;stroke:var(--k-blue);stroke-width:1.6}
.kp-spark circle{fill:var(--k-blue)}
.kp-spark-ref{stroke:var(--k-border);stroke-dasharray:3 3}
.kp-metric{display:flex;gap:16px;margin:0 0 14px}
.kp-metric button{border:0;background:none;padding:0 0 8px;font-size:13px;color:var(--k-text);border-bottom:2px solid transparent;cursor:pointer;font-family:inherit}
.kp-metric button[data-on="true"]{color:var(--k-orange);border-bottom-color:var(--k-orange);font-weight:500}
.kp-sheet{overflow-x:auto;max-width:560px}
.kp-board-wrap{max-width:100%}
.kp-table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
.kp-table thead th{background:#1565c0;color:#fff;font-weight:600;font-size:13px;padding:8px 12px;text-align:center;border:1px solid #0d47a1}
.kp-table thead th span{display:block;font-weight:500;font-size:12px;margin-top:2px}
.kp-table thead .kp-colhead th{background:#1976d2;font-weight:500;font-size:12px}
.kp-table tbody th{width:88px;padding:5px 10px;font-size:13px;font-weight:400;color:var(--k-text);background:var(--k-surface);border:1px solid var(--k-border);text-align:center}
.kp-cell{text-align:center;font-size:13px;font-weight:500;padding:5px 10px;border:1px solid #e8d0d0;color:#222}
.kp-delta{width:64px;text-align:right;font-size:12px;color:var(--k-dim);padding:5px 10px;border:1px solid var(--k-border)}
.kp-table tbody tr[data-live="true"] th{box-shadow:inset 3px 0 0 var(--k-orange);font-weight:600}
.kp-band-extreme-positive{background:#1b7a3a;color:#fff}
.kp-band-highly-positive{background:#43a047;color:#fff}
.kp-band-positive{background:#c8e6c9;color:#1b5e20}
.kp-band-negative{background:#f8d0d0;color:#222}
.kp-band-highly-negative{background:#f0a8a8;color:#222}
.kp-band-extreme-negative{background:#ff2a2a;color:#111}
.kp-band-empty{background:var(--k-bg)}
.kp-now-val.kp-band-empty{background:transparent;padding-left:0}
.kp-legend{margin:20px 0 8px;max-width:560px;padding:14px 16px;background:var(--k-surface);border:1px solid var(--k-border)}
.kp-legend h3{margin:0 0 10px;font-size:14px;font-weight:500}
.kp-legend ul{margin:0;padding:0;list-style:none}
.kp-legend li{display:flex;align-items:center;gap:8px;font-size:13px;line-height:1.55;margin:3px 0}
.kp-swatch{width:14px;height:14px;border-radius:2px;flex-shrink:0;display:inline-block;border:1px solid rgba(0,0,0,.08)}
.kp-legend p{margin:12px 0 0;font-size:12px;color:var(--k-dim);line-height:1.5}
.kp-feed{font-size:11px;color:var(--k-green);font-weight:500;margin-left:8px}
.kp-read{margin:0 0 16px;max-width:560px}
.kp-read h3{margin:0 0 4px;font-size:16px;font-weight:500}
.kp-read p{margin:0;font-size:13px;color:var(--k-dim);line-height:1.5}
.kp-tape{margin:16px 0 0;max-width:560px}
.kp-tape h3{margin:0 0 8px;font-size:13px;font-weight:500;color:var(--k-dim)}
.kp-tape ul{margin:0;padding:0;list-style:none}
.kp-tape li{font-size:13px;line-height:1.45;margin:4px 0;color:var(--k-text)}
.kp-tape .text-up,.kp-tape .text-down{font-weight:500}
@media (max-width:800px){
  .kite-pcr .ko-head,.kite-pcr .ko-body{padding-left:16px;padding-right:16px}
  .kp-now{grid-template-columns:1fr;gap:12px}
  .kp-sheet{max-width:none}
}
`;

export function PcrPane() {
  const [payload, setPayload] = useState<PcrDeskPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState<PcrIndex>("NIFTY");
  const [view, setView] = useState<View>("grid");
  const [metric, setMetric] = useState<PcrMetric>("oi");
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const tick = () => setNow(new Date());
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetchPcrDesk()
        .then((data) => {
          if (cancelled) return;
          setPayload(data);
          setError(null);
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setError(err instanceof Error ? err.message : "PCR feed unavailable");
        });
    };
    load();
    const id = window.setInterval(load, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const series = payload?.series[index];
  const nowMin = now ? nowMinutes(now) : null;
  const stamp = now ? istStamp(now) : "";
  const boards = useMemo(() => {
    if (!payload) return null;
    const out = {} as Record<PcrIndex, PcrSlot[]>;
    for (const u of PCR_INDICES) {
      const row = payload.series[u.id];
      if (!row) continue;
      out[u.id] = buildGrid(row.marks, row.latest, nowMin, metric);
    }
    return out;
  }, [payload, nowMin, metric]);
  const grid = boards?.[index] ?? [];
  const current = livePcr(series, grid, metric);
  const lastFilled = [...grid].reverse().find((s) => s.pcr != null);
  const band = (grid.find((s) => s.live) ?? lastFilled)?.band ?? "empty";
  const sessionIso = series?.spot.timestamp?.slice(0, 10) ?? "";
  const kindNow = series ? expiryKind(series.expiry, sessionIso || (now ? formatIstIsoDate(now) : "2026-08-27")) : "weekly";
  const insight = useMemo(
    () => readPcr(grid, series?.spot.changePer ?? null),
    [grid, series?.spot.changePer],
  );
  const tape = useMemo(() => {
    const out: { id: string; title: string; up: boolean }[] = [];
    for (const u of PCR_INDICES) {
      const row = boards?.[u.id] ?? [];
      for (const s of row) {
        if (s.delta == null || Math.abs(s.delta) < 0.06) continue;
        out.push({
          id: `${u.id}-${s.hhmm}`,
          title: `${u.short} ${s.delta > 0 ? "+" : ""}${s.delta.toFixed(2)} at ${s.label} → ${formatPcr(s.pcr)}`,
          up: s.delta > 0,
        });
      }
    }
    return out.slice(-8).reverse();
  }, [boards]);

  return (
    <div className="kite-pcr"><style>{CSS}</style>
      <div className="ko kp">
      <div className="ko-head">
        <div className="ko-title-row">
          <h2>PCR {payload?.source === "live" ? <span className="kp-feed">Live F&O</span> : null}</h2>
          <div className="kp-clock">{stamp ? `${stamp} IST` : ""}</div>
        </div>
        <div className="ko-tabs-row">
          <div className="ko-tabs" role="tablist" aria-label="View">
            <button type="button" role="tab" data-on={view === "grid"} aria-selected={view === "grid"} onClick={() => setView("grid")}>
              Grid
            </button>
            <button type="button" role="tab" data-on={view === "board"} aria-selected={view === "board"} onClick={() => setView("board")}>
              All indices
            </button>
          </div>
          <div className="ko-ins" role="tablist" aria-label="Underlying">
            {PCR_INDICES.map((u) => {
              const val = payload?.series[u.id]?.livePcr ?? payload?.series[u.id]?.latest?.pcr ?? null;
              const chipBand = pcrBand(val);
              return (
                <button key={u.id} type="button" role="tab" data-on={index === u.id} aria-selected={index === u.id} onClick={() => { setIndex(u.id); setView("grid"); }}>
                  {u.short}
                  {val != null ? <span className={`kp-chip-pcr kp-band-${chipBand}`}>{formatPcr(val)}</span> : null}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="ko-body">
        {error && !payload ? <p className="ko-sub">{error}</p> : null}

        {series ? (
          <div className="kp-now">
            <div className="kp-now-main">
              <div className="kp-now-kicker">Intraday + Weekly PCR</div>
              <div className={`kp-now-val kp-band-${band}`}>{formatPcr(current) || "—"}</div>
              <div className="kp-now-band">{bandTitle(band) || "Waiting for print"}</div>
            </div>
            <div className="kp-now-meta">
              <div>
                <span>Δ 15 min</span>
                <b className={(lastFilled?.delta ?? 0) > 0 ? "text-up" : (lastFilled?.delta ?? 0) < 0 ? "text-down" : "text-muted"}>
                  {formatDelta(lastFilled?.delta ?? null)}
                </b>
              </div>
              <div>
                <span>Expiry</span>
                <b>
                  {kindNow === "today" ? "Today" : kindNow === "weekly" ? "Weekly" : "Monthly"} · {formatExpiry(series.expiry)}
                </b>
              </div>
              <div>
                <span>Spot</span>
                <b>
                  {fmtLtp(series.spot.ltp)}
                  {series.spot.changePer != null ? (
                    <em className={series.spot.changePer >= 0 ? "text-up" : "text-down"}>
                      {" "}
                      {series.spot.changePer >= 0 ? "+" : ""}
                      {series.spot.changePer.toFixed(2)}%
                    </em>
                  ) : null}
                </b>
              </div>
              <div>
                <span>Max pain</span>
                <b>{fmtLtp(series.spot.maxPain)}</b>
              </div>
            </div>
            <div className="kp-now-viz">
              <Split pcr={current} />
              <Spark slots={grid} />
            </div>
          </div>
        ) : (
          <p className="ko-sub">Loading put-call prints…</p>
        )}

        {series ? (
          <div className="kp-read">
            <h3>{insight.headline}</h3>
            <p>
              {insight.bias} · {insight.reason}
            </p>
          </div>
        ) : null}

        <div className="kp-metric" role="tablist" aria-label="PCR metric">
          {(
            [
              ["oi", "OI PCR"],
              ["volume", "Volume PCR"],
              ["changeOi", "ΔOI PCR"],
            ] as const
          ).map(([id, label]) => (
            <button key={id} type="button" role="tab" data-on={metric === id} aria-selected={metric === id} onClick={() => setMetric(id)}>
              {label}
            </button>
          ))}
        </div>

        {view === "grid" ? (
          <div className="kp-sheet">
            <table className="kp-table">
              <thead>
                <tr>
                  <th>{stamp}</th>
                  <th colSpan={2}>
                    Intraday + Weekly PCR
                    <span>{PCR_INDICES.find((u) => u.id === index)?.label}</span>
                  </th>
                </tr>
                <tr className="kp-colhead">
                  <th>Time</th>
                  <th>PCR</th>
                  <th>Δ</th>
                </tr>
              </thead>
              <tbody>
                {grid.map((slot) => (
                  <tr key={slot.hhmm} data-live={slot.live} data-empty={slot.pcr == null}>
                    <th>{slot.label}</th>
                    <td className={`kp-cell kp-band-${slot.band}`}>{slot.pcr == null ? "" : formatPcr(slot.pcr)}</td>
                    <td className="kp-delta">{formatDelta(slot.delta)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="kp-sheet kp-board-wrap">
            <table className="kp-table kp-board">
              <thead>
                <tr>
                  <th>{stamp}</th>
                  {PCR_INDICES.map((u) => (
                    <th key={u.id}>{u.short}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {grid.map((slot, row) => (
                  <tr key={slot.hhmm}>
                    <th>{slot.label}</th>
                    {PCR_INDICES.map((u) => {
                      const s = boards?.[u.id]?.[row];
                      return (
                        <td key={u.id} className={`kp-cell kp-band-${s?.band ?? "empty"}`}>
                          {s?.pcr == null ? "" : formatPcr(s.pcr)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {tape.length ? (
          <div className="kp-tape">
            <h3>Flow tape</h3>
            <ul>
              {tape.map((e) => (
                <li key={e.id} className={e.up ? "text-up" : "text-down"}>{e.title}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <section className="kp-legend" aria-label="How to read PCR">
          <h3>How to read Put Call Ratio (PCR)</h3>
          <ul>
            {(["positive", "highly-positive", "extreme-positive", "negative", "highly-negative", "extreme-negative"] as const).map((id) => (
              <li key={id}>
                <i className={`kp-swatch kp-band-${id}`} />
                {BAND_COPY[id].hint}
              </li>
            ))}
          </ul>
          <p>
            Keep note of changes every 15 minutes. OI PCR is put open interest ÷ call open interest on the front weekly expiry
            (monthly when that is the listed series).
          </p>
        </section>
      </div>
    </div>
    </div>
  );
}
