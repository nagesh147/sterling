import { useEffect, useMemo, useState } from "react";
import { fetchPcrDesk, sessionIsoOf } from "../../lib/pcr/fetchPcr";
import {
  SESSION_CLOSE_MIN,
  SESSION_OPEN_MIN,
  buildGrid,
  buildIdea,
  expiryKind,
  flowPath,
  formatDelta,
  formatDeskStamp,
  formatExpiry,
  formatHhmm12,
  formatPcr,
  metricValue,
  pcrBand,
  putShare,
  readPcr,
  shiftSession,
  type PcrAction,
} from "../../lib/pcr/slots";
import {
  PCR_INDICES,
  type PcrDeskPayload,
  type PcrIndex,
  type PcrMetric,
  type PcrSeries,
  type PcrSlot,
} from "../../lib/pcr/types";
import { formatIstIsoDate, getIstParts } from "../../lib/astro/time";

const PCR_LO = 0.4;
const PCR_HI = 1.6;

function nowMinutes(now: Date): number {
  const p = getIstParts(now);
  return p.hour * 60 + p.minute;
}

function pad(n: number) {
  return String(n).padStart(2, "0");
}

function fmtLtp(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function ideaKind(action: PcrAction): "ce" | "pe" | "wait" {
  if (action === "Buy CE") return "ce";
  if (action === "Buy PE") return "pe";
  return "wait";
}

function ideaTag(action: PcrAction): string {
  if (action === "Buy CE") return "CE";
  if (action === "Buy PE") return "PE";
  return "Wait";
}

function lastPcr(slots: PcrSlot[]): number | null {
  return [...slots].reverse().find((s) => s.pcr != null)?.pcr ?? null;
}

function meterPct(pcr: number | null): number {
  if (pcr == null || !Number.isFinite(pcr)) return 50;
  return Math.min(100, Math.max(0, ((pcr - PCR_LO) / (PCR_HI - PCR_LO)) * 100));
}

function livePcr(series: PcrSeries | undefined, slots: PcrSlot[], metric: PcrMetric): number | null {
  const last = lastPcr(slots);
  if (last != null) return last;
  if (series?.latest) return metricValue(series.latest, metric);
  if (metric === "oi" && series?.livePcr != null) return series.livePcr;
  return null;
}

function Gauge({ pcr }: { pcr: number | null }) {
  const pct = meterPct(pcr);
  return (
    <div className="kp-gauge">
      <div className="kp-gauge-track" aria-hidden>
        <i className="kp-gauge-ref" />
        {pcr != null ? (
          <i
            className={`kp-gauge-nub kp-band-${pcrBand(pcr)}`}
            style={{ left: `${pct}%` }}
          />
        ) : null}
      </div>
      <div className="kp-gauge-lab">
        <span>Buy PE</span>
        <span>1.00</span>
        <span>Buy CE</span>
      </div>
    </div>
  );
}

function Split({ pcr }: { pcr: number | null }) {
  const put = putShare(pcr);
  if (put == null) return <div className="kp-split empty" />;
  const putPct = Math.round(put * 100);
  return (
    <div className="kp-split" title={`Puts ${putPct}% · Calls ${100 - putPct}%`}>
      <span className="kp-split-put" style={{ width: `${putPct}%` }} />
      <span className="kp-split-call" style={{ width: `${100 - putPct}%` }} />
    </div>
  );
}

function DayStrip({ slots, dense }: { slots: PcrSlot[]; dense?: boolean }) {
  return (
    <div className={`kp-day${dense ? " dense" : ""}`} role="img" aria-label="Session PCR">
      {slots.map((s) => (
        <span
          key={s.hhmm}
          className={`kp-day-cell kp-band-${s.band}${s.live ? " live" : ""}`}
          title={`${formatHhmm12(s.hhmm)}  ${s.pcr == null ? "—" : formatPcr(s.pcr)}${s.delta != null ? `  ${formatDelta(s.delta)}` : ""}`}
        />
      ))}
    </div>
  );
}

function Spark({ slots }: { slots: PcrSlot[] }) {
  const pts = slots.filter((s) => s.pcr != null) as Array<PcrSlot & { pcr: number }>;
  if (pts.length < 2) return null;
  const w = 560;
  const h = 72;
  const min = Math.min(...pts.map((s) => s.pcr), 0.6);
  const max = Math.max(...pts.map((s) => s.pcr), 1.2);
  const x = (i: number) => (i / (pts.length - 1)) * w;
  const y = (v: number) => h - 8 - ((v - min) / (max - min || 1)) * (h - 16);
  const d = pts.map((s, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)} ${y(s.pcr).toFixed(1)}`).join(" ");
  const y1 = y(1);
  const last = pts[pts.length - 1];
  const up = last.pcr >= 1;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={`kp-spark ${up ? "ce" : "pe"}`} aria-hidden>
      <line x1="0" y1={y1} x2={w} y2={y1} className="kp-spark-ref" />
      <path d={d} />
      <circle cx={w} cy={y(last.pcr)} r="3" />
    </svg>
  );
}

const CSS = `
.kite-pcr{display:flex;flex-direction:column;height:100%;min-height:100%;background:var(--k-bg);color:var(--k-text);font-family:inherit;font-size:13px}
.kite-pcr *{box-sizing:border-box}
.kite-pcr .kp-desk{display:flex;flex-direction:column;min-height:100%}
.kite-pcr .kp-head{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;padding:8px 16px;border-bottom:1px solid var(--k-border)}
.kite-pcr h1.kp-title{margin:0;font-size:15px;font-weight:600;letter-spacing:-.02em}
.kite-pcr .kp-tools{display:flex;flex-wrap:wrap;align-items:center;gap:6px}
.kite-pcr .kp-chip{border:1px solid var(--k-border);background:var(--k-surface);color:var(--k-dim);border-radius:3px;padding:4px 8px;font-size:11px}
.kite-pcr .kp-live{color:var(--k-green);border-color:color-mix(in srgb,var(--k-green) 35%, var(--k-border))}
.kite-pcr .kp-date{display:flex;align-items:center;border:1px solid var(--k-border);background:var(--k-surface);border-radius:3px;overflow:hidden;height:28px}
.kite-pcr .kp-date button{border:0;background:none;color:var(--k-text);width:26px;height:28px;cursor:pointer;font-size:14px;font-family:inherit}
.kite-pcr .kp-date button:disabled{opacity:.35;cursor:default}
.kite-pcr .kp-date button:hover:not(:disabled){background:var(--k-surface-hover)}
.kite-pcr .kp-date-lab{position:relative;display:flex;align-items:center;padding:0 8px;min-width:158px;justify-content:center;font-size:12px;font-weight:500;font-variant-numeric:tabular-nums;cursor:pointer}
.kite-pcr .kp-date-lab input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%;border:0}
.kite-pcr .kp-seg{display:flex;border:1px solid var(--k-border);background:var(--k-surface);border-radius:3px;overflow:hidden;height:28px}
.kite-pcr .kp-seg button{border:0;background:none;color:var(--k-dim);padding:0 10px;font-size:12px;cursor:pointer;font-family:inherit}
.kite-pcr .kp-seg button[data-on="true"]{background:var(--k-surface-hover);color:var(--k-text);font-weight:500}
.kite-pcr .kp-body{flex:1;padding:12px 16px 16px;overflow:auto;display:flex;flex-direction:column;gap:12px}
.kite-pcr .kp-sub{margin:0;font-size:12px;color:var(--k-dim);line-height:1.45}
.kite-pcr .text-up{color:var(--k-green)}
.kite-pcr .text-down{color:var(--k-red)}
.kite-pcr .kp-map{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}
.kite-pcr .kp-tile{display:flex;flex-direction:column;gap:8px;text-align:left;border:1px solid var(--k-border);background:var(--k-surface);border-radius:6px;padding:10px 12px;cursor:pointer;color:inherit;font-family:inherit}
.kite-pcr .kp-tile:hover{background:var(--k-surface-hover)}
.kite-pcr .kp-tile[data-on="true"]{border-color:var(--k-orange)}
.kite-pcr .kp-tile-top{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:11px;color:var(--k-dim)}
.kite-pcr .kp-tile-tag{font-size:10px;font-weight:700;letter-spacing:.06em}
.kite-pcr .kp-tile-tag.ce{color:var(--k-green)}
.kite-pcr .kp-tile-tag.pe{color:var(--k-red)}
.kite-pcr .kp-tile-tag.wait{color:var(--k-dim)}
.kite-pcr .kp-tile-pcr{font-size:28px;font-weight:600;font-variant-numeric:tabular-nums;letter-spacing:-.03em;line-height:1}
.kite-pcr .kp-split{display:flex;height:4px;border-radius:99px;overflow:hidden;background:var(--k-surface-hover)}
.kite-pcr .kp-split.empty{background:var(--k-border)}
.kite-pcr .kp-split-put{background:var(--k-green)}
.kite-pcr .kp-split-call{background:var(--k-red)}
.kite-pcr .kp-day{display:flex;gap:2px;height:22px}
.kite-pcr .kp-day.dense{height:8px;gap:1px}
.kite-pcr .kp-day-cell{flex:1;min-width:0;border-radius:1px}
.kite-pcr .kp-day-cell.live{box-shadow:inset 0 0 0 1px var(--k-orange)}
.kite-pcr .kp-hours{display:flex;justify-content:space-between;margin-top:4px;font-size:10px;color:var(--k-dim);font-variant-numeric:tabular-nums}
.kite-pcr .kp-band-extreme-positive{background:var(--k-green);color:var(--k-on-accent)}
.kite-pcr .kp-band-highly-positive{background:color-mix(in srgb,var(--k-green) 38%, var(--k-surface));color:var(--k-green-deep)}
.kite-pcr .kp-band-positive{background:var(--k-tint-green);color:var(--k-green-deep)}
.kite-pcr .kp-band-negative{background:var(--k-tint-red);color:var(--k-red-deep)}
.kite-pcr .kp-band-highly-negative{background:color-mix(in srgb,var(--k-red) 38%, var(--k-surface));color:var(--k-red-deep)}
.kite-pcr .kp-band-extreme-negative{background:var(--k-red);color:var(--k-on-accent)}
.kite-pcr .kp-band-empty{background:color-mix(in srgb,var(--k-border) 55%, var(--k-surface));color:var(--k-dim)}
.kite-pcr .kp-focus{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(240px,.75fr);gap:10px;align-items:stretch}
.kite-pcr .kp-panel{border:1px solid var(--k-border);background:var(--k-surface);border-radius:6px;padding:14px 16px}
.kite-pcr .kp-hero{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:12px}
.kite-pcr .kp-hero-pcr{font-size:48px;font-weight:600;font-variant-numeric:tabular-nums;letter-spacing:-.04em;line-height:1;padding:4px 10px;border-radius:4px}
.kite-pcr .kp-hero-meta{text-align:right;font-size:12px;color:var(--k-dim);line-height:1.45}
.kite-pcr .kp-hero-meta b{display:block;color:var(--k-text);font-size:14px;font-weight:500;font-variant-numeric:tabular-nums}
.kite-pcr .kp-gauge{margin:4px 0 14px}
.kite-pcr .kp-gauge-track{position:relative;height:10px;border-radius:99px;background:linear-gradient(90deg,var(--k-red) 0%,var(--k-tint-red) 38%,var(--k-surface-hover) 48%,var(--k-surface-hover) 52%,var(--k-tint-green) 62%,var(--k-green) 100%)}
.kite-pcr .kp-gauge-ref{position:absolute;top:-3px;bottom:-3px;left:50%;width:1px;background:var(--k-text);opacity:.45}
.kite-pcr .kp-gauge-nub{position:absolute;top:50%;width:14px;height:14px;border-radius:50%;transform:translate(-50%,-50%);box-shadow:0 0 0 2px var(--k-surface);border:0}
.kite-pcr .kp-gauge-lab{display:flex;justify-content:space-between;margin-top:6px;font-size:10px;letter-spacing:.04em;text-transform:uppercase;color:var(--k-dim)}
.kite-pcr .kp-spark{display:block;width:100%;height:72px;margin:2px 0 10px}
.kite-pcr .kp-spark path{fill:none;stroke-width:1.8}
.kite-pcr .kp-spark.ce path{stroke:var(--k-green)}
.kite-pcr .kp-spark.pe path{stroke:var(--k-red)}
.kite-pcr .kp-spark.ce circle{fill:var(--k-green)}
.kite-pcr .kp-spark.pe circle{fill:var(--k-red)}
.kite-pcr .kp-spark-ref{stroke:var(--k-border);stroke-dasharray:3 3}
.kite-pcr .kp-buy{margin:0;font-size:28px;font-weight:600;letter-spacing:-.03em;line-height:1.1}
.kite-pcr .kp-buy.ce{color:var(--k-green)}
.kite-pcr .kp-buy.pe{color:var(--k-red)}
.kite-pcr .kp-buy.wait{color:var(--k-dim)}
.kite-pcr .kp-play{margin:8px 0 0;font-size:13px;line-height:1.45;color:var(--k-text)}
.kite-pcr .kp-move{margin:12px 0 0;font-size:18px;font-weight:500;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.kite-pcr .kp-move .mv{margin-left:8px;font-size:13px;font-weight:400}
.kite-pcr .kp-clock{margin:2px 0 0;font-size:12px;color:var(--k-dim)}
.kite-pcr .kp-share{display:flex;justify-content:space-between;margin:14px 0 6px;font-size:11px;color:var(--k-dim);font-variant-numeric:tabular-nums}
.kite-pcr .kp-facts{display:grid;grid-template-columns:1fr 1fr;gap:10px 12px;margin-top:16px;padding-top:12px;border-top:1px solid var(--k-border)}
.kite-pcr .kp-facts dt{margin:0;font-size:10px;color:var(--k-dim)}
.kite-pcr .kp-facts dd{margin:2px 0 0;font-size:13px;font-variant-numeric:tabular-nums;font-weight:500}
.kite-pcr .kp-ev{margin-top:14px;padding-top:12px;border-top:1px solid var(--k-border)}
.kite-pcr .kp-ev-lab{margin:0 0 8px;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--k-dim)}
.kite-pcr .kp-ev-row{display:flex;align-items:center;gap:8px;padding:6px 0;font-size:12px;font-variant-numeric:tabular-nums}
.kite-pcr .kp-ev-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.kite-pcr .kp-ev-dot.ce{background:var(--k-green)}
.kite-pcr .kp-ev-dot.pe{background:var(--k-red)}
.kite-pcr .kp-ev-clock{color:var(--k-dim);width:72px}
.kite-pcr .kp-ev-path{flex:1}
.kite-pcr .kp-ev-tag{font-size:11px;font-weight:700;letter-spacing:.04em}
.kite-pcr .kp-ev-tag.ce{color:var(--k-green)}
.kite-pcr .kp-ev-tag.pe{color:var(--k-red)}
.kite-pcr .kp-foot{margin:0;font-size:11px;color:var(--k-dim)}
@media (max-width:980px){
  .kite-pcr .kp-map{grid-template-columns:repeat(2,minmax(0,1fr))}
  .kite-pcr .kp-focus{grid-template-columns:1fr}
  .kite-pcr .kp-hero-pcr{font-size:36px}
  .kite-pcr .kp-head,.kite-pcr .kp-body{padding-left:10px;padding-right:10px}
}
`;

export function PcrPane() {
  const [payload, setPayload] = useState<PcrDeskPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState<PcrIndex>("NIFTY");
  const [metric, setMetric] = useState<PcrMetric>("oi");
  const [now, setNow] = useState<Date | null>(null);
  const [liveIso, setLiveIso] = useState("");
  const [sessionIso, setSessionIso] = useState("");
  const [followLive, setFollowLive] = useState(true);

  useEffect(() => {
    const tick = () => {
      const d = new Date();
      setNow((prev) => {
        if (!prev) return d;
        const a = getIstParts(prev);
        const b = getIstParts(d);
        if (a.hour === b.hour && a.minute === b.minute) return prev;
        return d;
      });
    };
    tick();
    const id = window.setInterval(tick, 5_000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetchPcrDesk(followLive ? null : sessionIso)
        .then((data) => {
          if (cancelled) return;
          setPayload(data);
          setError(null);
          const iso = sessionIsoOf(data);
          if (data.source === "live" && iso) setLiveIso(iso);
          if (followLive && iso) setSessionIso(iso);
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setError(err instanceof Error ? err.message : "PCR feed unavailable");
        });
    };
    load();
    const id = followLive ? window.setInterval(load, 30_000) : 0;
    return () => {
      cancelled = true;
      if (id) window.clearInterval(id);
    };
  }, [followLive, followLive ? "live" : sessionIso]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      const map: Record<string, PcrIndex> = { "1": "NIFTY", "2": "BANKNIFTY", "3": "FINNIFTY", "4": "SENSEX", "5": "MIDCPNIFTY" };
      const pick = map[e.key];
      if (pick) setIndex(pick);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const todayIso = now ? formatIstIsoDate(now) : liveIso;
  const capIso = liveIso || todayIso;
  let dateMin = capIso || "2026-06-01";
  for (let i = 0; i < 40; i++) dateMin = shiftSession(dateMin, -1);

  const pickSession = (next: string) => {
    if (!next) return;
    let iso = next;
    if (capIso && iso > capIso) iso = capIso;
    setSessionIso(iso);
    setFollowLive(Boolean(capIso) && iso === capIso);
  };

  const series = payload?.series[index];
  const nowMin = now ? nowMinutes(now) : null;
  const viewingLive = followLive || (capIso && sessionIso === capIso);
  const inLiveSession = Boolean(
    viewingLive && nowMin != null && nowMin >= SESSION_OPEN_MIN && nowMin < SESSION_CLOSE_MIN,
  );
  const gridNowMin = viewingLive && inLiveSession ? nowMin : SESSION_CLOSE_MIN;
  const boards = useMemo(() => {
    if (!payload) return null;
    const out = {} as Record<PcrIndex, PcrSlot[]>;
    for (const u of PCR_INDICES) {
      const row = payload.series[u.id];
      if (!row) continue;
      out[u.id] = buildGrid(row.marks, row.latest, gridNowMin, metric);
    }
    return out;
  }, [payload, gridNowMin, metric]);
  const grid = boards?.[index] ?? [];
  const current = livePcr(series, grid, metric);
  const lastFilled = [...grid].reverse().find((s) => s.pcr != null);
  const prevFilled = grid.filter((s) => s.pcr != null);
  const prev = prevFilled.length >= 2 ? prevFilled[prevFilled.length - 2] : null;
  const delta =
    current != null && prev?.pcr != null ? Math.round((current - prev.pcr) * 100) / 100 : (lastFilled?.delta ?? null);
  const band = lastFilled?.band ?? (current != null ? pcrBand(current) : "empty");
  const kindNow = series ? expiryKind(series.expiry, sessionIso || todayIso) : "weekly";
  const insight = useMemo(() => readPcr(grid, series?.spot.changePer ?? null), [grid, series?.spot.changePer]);
  const ideaName = PCR_INDICES.find((u) => u.id === index)?.short ?? index;
  const idea = useMemo(() => buildIdea(ideaName, grid), [ideaName, grid]);
  const tiles = useMemo(() => {
    return PCR_INDICES.map((u) => {
      const slots = boards?.[u.id] ?? [];
      const pcr = lastPcr(slots);
      const board = buildIdea(u.short, slots);
      const action = board.idea?.action ?? "Wait";
      return { u, slots, pcr, action, kind: ideaKind(action) };
    });
  }, [boards]);
  const putPct = putShare(current);
  const live = payload?.source === "live" && viewingLive;
  const expiryLabel = series
    ? `${kindNow === "today" ? "Today" : kindNow === "weekly" ? "Weekly" : "Monthly"} · ${formatExpiry(series.expiry)}`
    : "—";
  const stampHhmm = lastFilled?.hhmm
    ?? (inLiveSession && nowMin != null ? `${pad(Math.floor(nowMin / 60))}:${pad(nowMin % 60)}` : "09:15");
  const deskStamp = formatDeskStamp(sessionIso || capIso, stampHhmm);
  const hasSeries = Boolean(series?.marks?.length || current != null);
  const prevIso = sessionIso ? shiftSession(sessionIso, -1) : "";
  const nextIso = sessionIso ? shiftSession(sessionIso, 1) : "";
  const canNext = Boolean(capIso && nextIso && nextIso <= capIso);
  const action = idea.idea?.action && idea.idea.action !== "Wait" ? idea.idea.action : insight.action;
  const kind = ideaKind(action);
  const putLab = putPct == null ? "—" : `${Math.round(putPct * 100)}%`;
  const callLab = putPct == null ? "—" : `${100 - Math.round(putPct * 100)}%`;

  return (
    <div className="kite-pcr">
      <style>{CSS}</style>
      <div className="kp-desk">
        <header className="kp-head">
          <h1 className="kp-title">PCR</h1>
          <div className="kp-tools">
            <div className="kp-date">
              <button type="button" aria-label="Previous session" onClick={() => prevIso && pickSession(prevIso)}>‹</button>
              <label className="kp-date-lab">
                <span>{deskStamp}</span>
                <input
                  type="date"
                  value={sessionIso}
                  min={dateMin}
                  max={capIso}
                  onChange={(e) => pickSession(e.target.value)}
                  aria-label="Session date"
                />
              </label>
              <button type="button" aria-label="Next session" disabled={!canNext} onClick={() => canNext && pickSession(nextIso)}>›</button>
            </div>
            <div className={`kp-chip ${live ? "kp-live" : ""}`}>{live ? "Live" : "Stored"}</div>
            <div className="kp-seg" role="tablist" aria-label="PCR metric">
              {([["oi", "OI"], ["volume", "Volume"], ["changeOi", "ΔOI"]] as const).map(([id, label]) => (
                <button key={id} type="button" role="tab" data-on={metric === id} onClick={() => setMetric(id)}>{label}</button>
              ))}
            </div>
          </div>
        </header>

        <div className="kp-body">
          {error && !payload ? <p className="kp-sub">{error}</p> : null}

          <div className="kp-map" role="tablist" aria-label="Underlying">
            {tiles.map((t) => (
              <button
                key={t.u.id}
                type="button"
                role="tab"
                className="kp-tile"
                data-on={index === t.u.id}
                onClick={() => setIndex(t.u.id)}
              >
                <div className="kp-tile-top">
                  <span>{t.u.short}</span>
                  <span className={`kp-tile-tag ${t.kind}`}>{ideaTag(t.action)}</span>
                </div>
                <div className={`kp-tile-pcr ${t.pcr != null && t.pcr >= 1 ? "text-up" : t.pcr != null ? "text-down" : ""}`}>
                  {t.pcr == null ? "—" : formatPcr(t.pcr)}
                </div>
                <Split pcr={t.pcr} />
                <DayStrip slots={t.slots} dense />
              </button>
            ))}
          </div>

          {hasSeries ? (
            <section className="kp-focus">
              <div className="kp-panel">
                <div className="kp-hero">
                  <div className={`kp-hero-pcr kp-band-${band}`}>{formatPcr(current) || "—"}</div>
                  <div className="kp-hero-meta">
                    <b>{PCR_INDICES.find((u) => u.id === index)?.label}</b>
                    {formatDelta(delta)} · {lastFilled ? formatHhmm12(lastFilled.hhmm) : "—"}
                  </div>
                </div>
                <Gauge pcr={current} />
                <Spark slots={grid} />
                <DayStrip slots={grid} />
                <div className="kp-hours">
                  <span>09:15</span>
                  <span>11:00</span>
                  <span>12:30</span>
                  <span>14:00</span>
                  <span>15:30</span>
                </div>
              </div>

              <aside className="kp-panel">
                <p className={`kp-buy ${kind}`}>{action}</p>
                <p className="kp-play">{insight.play}</p>
                {idea.idea ? (
                  <>
                    <div className="kp-move">
                      {flowPath(idea.idea)}
                      <span className={`mv ${(idea.idea.move ?? 0) > 0 ? "text-up" : (idea.idea.move ?? 0) < 0 ? "text-down" : ""}`}>
                        {formatDelta(idea.idea.move)}
                      </span>
                    </div>
                    <p className="kp-clock">{idea.idea.clock}</p>
                  </>
                ) : null}
                <div className="kp-share">
                  <span>Puts {putLab}</span>
                  <span>Calls {callLab}</span>
                </div>
                <Split pcr={current} />
                <dl className="kp-facts">
                  <div>
                    <dt>Spot</dt>
                    <dd>
                      {fmtLtp(series?.spot.ltp)}
                      {series?.spot.changePer != null ? (
                        <span className={series.spot.changePer >= 0 ? "text-up" : "text-down"}>
                          {" "}{series.spot.changePer >= 0 ? "+" : ""}{series.spot.changePer.toFixed(2)}%
                        </span>
                      ) : null}
                    </dd>
                  </div>
                  <div>
                    <dt>Max pain</dt>
                    <dd>{fmtLtp(series?.spot.maxPain)}</dd>
                  </div>
                  <div>
                    <dt>Expiry</dt>
                    <dd>{expiryLabel}</dd>
                  </div>
                  <div>
                    <dt>Δ 15m</dt>
                    <dd className={(delta ?? 0) > 0 ? "text-up" : (delta ?? 0) < 0 ? "text-down" : ""}>{formatDelta(delta)}</dd>
                  </div>
                </dl>
                {idea.earlier.length ? (
                  <div className="kp-ev">
                    <p className="kp-ev-lab">Earlier</p>
                    {idea.earlier.map((e) => (
                      <div key={e.hhmm} className="kp-ev-row">
                        <i className={`kp-ev-dot ${ideaKind(e.action)}`} />
                        <span className="kp-ev-clock">{e.clock}</span>
                        <span className="kp-ev-path">{flowPath(e)}</span>
                        <span className={`kp-ev-tag ${ideaKind(e.action)}`}>{ideaTag(e.action)}</span>
                      </div>
                    ))}
                  </div>
                ) : null}
              </aside>
            </section>
          ) : (
            <p className="kp-sub">{payload ? `No F&O prints stored for ${deskStamp}. Live feed keeps the current session.` : "Loading put-call prints…"}</p>
          )}

          <p className="kp-foot">Green ≥ 1.00 Buy CE · Red ≤ 0.80 Buy PE · click a tile · 1–5</p>
        </div>
      </div>
    </div>
  );
}
