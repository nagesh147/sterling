import { useEffect, useMemo, useState } from "react";
import { fetchPcrDesk, sessionIsoOf } from "../../lib/pcr/fetchPcr";
import {
  BAND_COPY,
  SESSION_CLOSE_MIN,
  SESSION_OPEN_MIN,
  bandTitle,
  buildGrid,
  buildIdea,
  expiryKind,
  flowPath,
  formatDelta,
  formatDeskStamp,
  formatExpiry,
  formatPcr,
  isValidPrint,
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

type View = "grid" | "board" | "path";

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

function moveTxt(n: number): string {
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}`;
}

function Spark({ slots }: { slots: PcrSlot[] }) {
  const pts = slots.map((s) => s.pcr).filter((v): v is number => v != null);
  if (pts.length < 2) return null;
  const min = Math.min(...pts, 0.7);
  const max = Math.max(...pts, 1.3);
  const w = 220;
  const h = 56;
  const d = pts
    .map((v, i) => {
      const x = (i / (pts.length - 1)) * w;
      const y = h - ((v - min) / (max - min || 1)) * (h - 8) - 4;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  const y1 = h - ((1 - min) / (max - min || 1)) * (h - 8) - 4;
  const last = pts[pts.length - 1];
  const ly = h - ((last - min) / (max - min || 1)) * (h - 8) - 4;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="kp-spark" aria-hidden>
      <line x1="0" y1={y1} x2={w} y2={y1} className="kp-spark-ref" />
      <path d={d} />
      <circle cx={w} cy={ly} r="2.4" />
    </svg>
  );
}

function Split({ pcr }: { pcr: number | null }) {
  const put = putShare(pcr);
  if (put == null) return null;
  const putPct = Math.round(put * 100);
  return (
    <div className="kp-split-wrap">
      <div className="kp-split-lab">
        <span>Puts {putPct}%</span>
        <span>Calls {100 - putPct}%</span>
      </div>
      <div className="kp-split">
        <span className="kp-split-put" style={{ width: `${putPct}%` }} />
        <span className="kp-split-call" style={{ width: `${100 - putPct}%` }} />
      </div>
    </div>
  );
}

function Path({ slots, marks }: { slots: PcrSlot[]; marks: { hhmm: string; indexClose: number }[] }) {
  const by = new Map(marks.map((m) => [m.hhmm, m.indexClose]));
  const pts = slots.filter((s) => s.pcr != null);
  if (pts.length < 2) {
    return <p className="kp-muted">Path fills as 15-minute prints land.</p>;
  }
  const w = 640;
  const h = 220;
  const pcrs = pts.map((s) => s.pcr as number);
  const spots = pts.map((s) => by.get(s.hhmm)).filter((v): v is number => v != null && v > 0);
  const pLo = Math.min(...pcrs, 0.5);
  const pHi = Math.max(...pcrs, 1.4);
  const sLo = spots.length ? Math.min(...spots) : 0;
  const sHi = spots.length ? Math.max(...spots) : 1;
  const py = (v: number) => h - 16 - ((v - pLo) / (pHi - pLo || 1)) * (h - 32);
  const sy = (v: number) => h - 16 - ((v - sLo) / (sHi - sLo || 1)) * (h - 32);
  const x = (i: number) => 8 + (i / (pts.length - 1)) * (w - 16);
  const pPath = pts.map((s, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)} ${py(s.pcr as number).toFixed(1)}`).join(" ");
  const sPath = pts
    .map((s, i) => {
      const sp = by.get(s.hhmm);
      if (sp == null) return null;
      return `${i === 0 ? "M" : "L"}${x(i).toFixed(1)} ${sy(sp).toFixed(1)}`;
    })
    .filter(Boolean)
    .join(" ");
  return (
    <div className="kp-card kp-path">
      <p className="kp-kicker">PCR vs spot</p>
      <svg viewBox={`0 0 ${w} ${h}`} className="kp-path-svg" role="img" aria-label="PCR versus spot">
        <path d={pPath} className="kp-path-pcr" />
        {sPath ? <path d={sPath} className="kp-path-spot" /> : null}
      </svg>
      <div className="kp-path-key">
        <span><i className="kp-key-pcr" /> PCR</span>
        <span><i className="kp-key-spot" /> Spot</span>
      </div>
    </div>
  );
}

function livePcr(series: PcrSeries | undefined, slots: PcrSlot[], metric: PcrMetric): number | null {
  const last = [...slots].reverse().find((s) => s.pcr != null)?.pcr ?? null;
  if (last != null) return last;
  if (series?.latest) return metricValue(series.latest, metric);
  if (metric === "oi" && series?.livePcr != null) return series.livePcr;
  return null;
}

const CSS = `
.kite-pcr{display:flex;flex-direction:column;height:100%;min-height:100%;background:var(--k-bg);color:var(--k-text);font-family:inherit;font-size:14px}
.kite-pcr *{box-sizing:border-box}
.kite-pcr .kp-desk{display:flex;flex-direction:column;min-height:100%}
.kite-pcr .kp-head{padding:16px 24px 0;border-bottom:1px solid var(--k-border)}
.kite-pcr .kp-head-row{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:12px}
.kite-pcr .kp-kicker{margin:0;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--k-dim);font-weight:500}
.kite-pcr h1.kp-title{margin:4px 0 0;font-size:28px;font-weight:500;letter-spacing:-.02em;line-height:1.1;color:var(--k-text)}
.kite-pcr .kp-tools{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.kite-pcr .kp-chip{border:1px solid var(--k-border);background:var(--k-surface);color:var(--k-dim);border-radius:4px;padding:6px 10px;font-size:12px;font-variant-numeric:tabular-nums}
.kite-pcr .kp-date{display:flex;align-items:center;border:1px solid var(--k-border);background:var(--k-surface);border-radius:4px;overflow:hidden}
.kite-pcr .kp-date button{border:0;background:none;color:var(--k-text);width:32px;height:32px;cursor:pointer;font-size:16px;font-family:inherit}
.kite-pcr .kp-date button:disabled{opacity:.35;cursor:default}
.kite-pcr .kp-date button:hover:not(:disabled){background:var(--k-surface-hover)}
.kite-pcr .kp-date-lab{position:relative;display:flex;align-items:center;padding:0 8px;min-width:168px;justify-content:center;font-size:13px;font-weight:500;font-variant-numeric:tabular-nums;color:var(--k-text);cursor:pointer}
.kite-pcr .kp-date-lab input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%;border:0}
.kite-pcr .kp-seg{display:flex;border:1px solid var(--k-border);background:var(--k-surface);border-radius:4px;overflow:hidden}
.kite-pcr .kp-seg button{border:0;background:none;color:var(--k-dim);padding:7px 12px;font-size:12px;cursor:pointer;font-family:inherit}
.kite-pcr .kp-seg button[data-on="true"]{background:var(--k-surface-hover);color:var(--k-text);font-weight:500}
.kite-pcr .kp-live{color:var(--k-green);border-color:color-mix(in srgb,var(--k-green) 35%, var(--k-border))}
.kite-pcr .kp-meta-row{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;margin-top:14px;padding-bottom:10px}
.kite-pcr .kp-idx{display:flex;flex-wrap:wrap;gap:6px}
.kite-pcr .kp-idx button{border:1px solid var(--k-border);background:var(--k-surface);color:var(--k-text);border-radius:4px;padding:5px 9px;font-size:13px;cursor:pointer;font-family:inherit;display:inline-flex;align-items:center;gap:6px}
.kite-pcr .kp-idx button[data-on="true"]{border-color:var(--k-orange);color:var(--k-orange)}
.kite-pcr .kp-chip-pcr{font-size:11px;font-weight:600;font-variant-numeric:tabular-nums;padding:1px 5px;border-radius:2px}
.kite-pcr .kp-tabs{display:flex;gap:16px}
.kite-pcr .kp-tabs button{border:0;background:none;color:var(--k-dim);padding:0 0 8px;font-size:13px;cursor:pointer;font-family:inherit;border-bottom:2px solid transparent}
.kite-pcr .kp-tabs button[data-on="true"]{color:var(--k-orange);border-bottom-color:var(--k-orange);font-weight:500}
.kite-pcr .kp-body{flex:1;padding:16px 24px 28px;overflow:auto}
.kite-pcr .kp-hero{display:grid;grid-template-columns:minmax(220px,1.15fr) minmax(260px,1.1fr) minmax(200px,.85fr);gap:12px;margin-bottom:14px}
.kite-pcr .kp-card{border:1px solid var(--k-border);background:var(--k-surface);border-radius:6px;padding:16px}
.kite-pcr .kp-print{font-size:52px;line-height:1;font-weight:600;font-variant-numeric:tabular-nums;display:inline-block;padding:6px 12px;border-radius:4px;margin:8px 0}
.kite-pcr .kp-sub{margin:0;font-size:13px;color:var(--k-dim);line-height:1.5}
.kite-pcr .kp-read h2{margin:8px 0 6px;font-size:22px;font-weight:500;line-height:1.25}
.kite-pcr .kp-read p{margin:0;font-size:13px;color:var(--k-dim);line-height:1.5}
.kite-pcr .kp-play{margin-top:12px;padding:10px 12px;border-radius:4px;background:var(--k-surface-hover);border:1px solid var(--k-border)}
.kite-pcr .kp-play-tag{display:inline-block;font-size:12px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;margin-bottom:4px}
.kite-pcr .kp-play p{color:var(--k-text)}
.kite-pcr .kp-conv{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:14px}
.kite-pcr .kp-conv .lab{font-size:11px;color:var(--k-dim)}
.kite-pcr .kp-conv .val{font-size:15px;font-weight:500;margin:2px 0 0}
.kite-pcr .kp-bar{height:6px;background:var(--k-surface-hover);border-radius:99px;overflow:hidden;margin-top:6px}
.kite-pcr .kp-bar>span{display:block;height:100%;background:var(--k-blue)}
.kite-pcr .kp-stats{display:grid;grid-template-columns:1fr 1fr;gap:12px 16px}
.kite-pcr .kp-stats .lab{font-size:11px;color:var(--k-dim)}
.kite-pcr .kp-stats .val{font-size:13px;font-variant-numeric:tabular-nums;margin-top:2px}
.kite-pcr .text-up{color:var(--k-green)}
.kite-pcr .text-down{color:var(--k-red)}
.kite-pcr .kp-split-wrap{margin-top:14px}
.kite-pcr .kp-split-lab{display:flex;justify-content:space-between;font-size:11px;font-variant-numeric:tabular-nums;color:var(--k-dim);margin-bottom:6px}
.kite-pcr .kp-split{display:flex;height:6px;border-radius:99px;overflow:hidden;background:var(--k-surface-hover)}
.kite-pcr .kp-split-put{background:var(--k-green)}
.kite-pcr .kp-split-call{background:var(--k-red)}
.kite-pcr .kp-spark{display:block;width:100%;height:56px;margin-top:8px}
.kite-pcr .kp-spark path{fill:none;stroke:var(--k-blue);stroke-width:1.6}
.kite-pcr .kp-spark circle{fill:var(--k-blue)}
.kite-pcr .kp-spark-ref{stroke:var(--k-border);stroke-dasharray:3 3}
.kite-pcr .kp-main{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(240px,.8fr);gap:12px;align-items:start}
.kite-pcr .kp-sheet{overflow:auto;border:1px solid var(--k-border);border-radius:6px;background:var(--k-surface);padding:8px}
.kite-pcr table{width:100%;border-collapse:separate;border-spacing:3px;font-variant-numeric:tabular-nums}
.kite-pcr thead th{background:transparent;color:var(--k-dim);font-weight:500;font-size:11px;padding:6px 8px;text-align:left;border:0}
.kite-pcr tbody th{padding:6px 8px;font-size:12px;font-weight:400;color:var(--k-dim);text-align:left;background:transparent;border:0}
.kite-pcr tbody td{padding:0}
.kite-pcr tbody tr[data-live="true"] th{color:var(--k-orange);font-weight:600}
.kite-pcr .kp-heat{display:block;text-align:center;font-size:12px;font-weight:500;padding:7px 6px;border-radius:3px;min-height:28px}
.kite-pcr .kp-delta{display:block;text-align:right;padding:7px 8px;font-size:12px;color:var(--k-dim)}
.kite-pcr .kp-band-extreme-positive{background:#1b5e4a;color:#f4f4f5}
.kite-pcr .kp-band-highly-positive{background:#2e7a64;color:#f4f4f5}
.kite-pcr .kp-band-positive{background:#b7d9cf;color:#12332c}
.kite-pcr .kp-band-negative{background:#e4c4c4;color:#3a1818}
.kite-pcr .kp-band-highly-negative{background:#c97a7a;color:#1a0c0c}
.kite-pcr .kp-band-extreme-negative{background:#a33a3a;color:#f4f4f5}
.kite-pcr .kp-band-empty{background:transparent;color:var(--k-dim)}
.kite-pcr .kp-print.kp-band-empty{background:var(--k-surface-hover)}
.kite-pcr .kp-side{display:flex;flex-direction:column;gap:12px}
.kite-pcr .kp-tape-head{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;margin-bottom:8px}
.kite-pcr .kp-idea-act{margin:4px 0 2px;font-size:28px;font-weight:600;letter-spacing:-.03em;line-height:1.1}
.kite-pcr .kp-idea-act.ce{color:var(--k-green)}
.kite-pcr .kp-idea-act.pe{color:var(--k-red)}
.kite-pcr .kp-idea-act.wait{color:var(--k-dim)}
.kite-pcr .kp-idea-meta{display:flex;justify-content:space-between;gap:8px;align-items:baseline;font-size:13px;color:var(--k-dim);font-variant-numeric:tabular-nums}
.kite-pcr .kp-idea-path{margin:8px 0 6px;font-size:18px;font-weight:500;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.kite-pcr .kp-idea-path .mv{margin-left:8px;font-size:13px;font-weight:400}
.kite-pcr .kp-idea-why{margin:0;font-size:13px;line-height:1.45;color:var(--k-text)}
.kite-pcr .kp-ev{margin-top:14px;padding-top:12px;border-top:1px solid var(--k-border)}
.kite-pcr .kp-ev-lab{margin:0 0 6px;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--k-dim);font-weight:500}
.kite-pcr .kp-ev-row{display:grid;grid-template-columns:76px 1fr auto;gap:8px;align-items:baseline;padding:7px 0;font-size:12px;font-variant-numeric:tabular-nums;border-bottom:1px solid var(--k-border)}
.kite-pcr .kp-ev-row:last-child{border-bottom:0;padding-bottom:0}
.kite-pcr .kp-ev-clock{color:var(--k-dim)}
.kite-pcr .kp-ev-path{color:var(--k-text)}
.kite-pcr .kp-ev-tag{font-size:11px;font-weight:700;letter-spacing:.04em}
.kite-pcr .kp-ev-tag.ce{color:var(--k-green)}
.kite-pcr .kp-ev-tag.pe{color:var(--k-red)}
.kite-pcr .kp-skip{margin:10px 0 0;font-size:12px;color:var(--k-dim);line-height:1.4}
.kite-pcr .kp-all{list-style:none;margin:8px 0 0;padding:0}
.kite-pcr .kp-all-row{display:grid;grid-template-columns:64px 72px 1fr auto;gap:8px;align-items:baseline;width:100%;text-align:left;border:0;background:none;color:inherit;padding:10px 0;border-bottom:1px solid var(--k-border);cursor:pointer;font-family:inherit;font-size:13px;font-variant-numeric:tabular-nums}
.kite-pcr .kp-all-row:hover{background:var(--k-surface-hover)}
.kite-pcr .kp-all-row:last-child{border-bottom:0}
.kite-pcr .kp-all-name{font-weight:500}
.kite-pcr .kp-all-act{font-weight:600;letter-spacing:-.01em}
.kite-pcr .kp-all-act.ce{color:var(--k-green)}
.kite-pcr .kp-all-act.pe{color:var(--k-red)}
.kite-pcr .kp-all-act.wait{color:var(--k-dim);font-weight:500}
.kite-pcr .kp-all-path{color:var(--k-text)}
.kite-pcr .kp-all-clock{color:var(--k-dim);font-size:12px}
.kite-pcr .kp-legend ul{list-style:none;margin:4px 0 0;padding:0}
.kite-pcr .kp-legend li{display:flex;gap:8px;align-items:flex-start;font-size:13px;color:var(--k-dim);line-height:1.45;margin:0 0 8px}
.kite-pcr .kp-swatch{width:12px;height:12px;border-radius:2px;flex-shrink:0;margin-top:3px;display:inline-block}
.kite-pcr .kp-foot{margin:16px 0 0;font-size:11px;color:var(--k-dim)}
.kite-pcr .kp-path-svg{width:100%;height:220px}
.kite-pcr .kp-path-pcr{fill:none;stroke:var(--k-blue);stroke-width:2}
.kite-pcr .kp-path-spot{fill:none;stroke:var(--k-green);stroke-width:1.5}
.kite-pcr .kp-path-key{display:flex;gap:16px;font-size:12px;color:var(--k-dim);margin-top:8px}
.kite-pcr .kp-path-key i{display:inline-block;width:12px;height:2px;margin-right:6px;vertical-align:middle}
.kite-pcr .kp-key-pcr{background:var(--k-blue)}
.kite-pcr .kp-key-spot{background:var(--k-green)}
.kite-pcr .kp-muted{color:var(--k-dim)}
.kite-pcr .kp-empty{padding:28px 8px;text-align:center;color:var(--k-dim);font-size:13px}
@media (max-width:980px){
  .kite-pcr .kp-hero,.kite-pcr .kp-main{grid-template-columns:1fr}
  .kite-pcr h1.kp-title{font-size:24px}
  .kite-pcr .kp-print{font-size:40px}
  .kite-pcr .kp-head,.kite-pcr .kp-body{padding-left:14px;padding-right:14px}
}
`;

export function PcrPane() {
  const [payload, setPayload] = useState<PcrDeskPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState<PcrIndex>("NIFTY");
  const [view, setView] = useState<View>("grid");
  const [metric, setMetric] = useState<PcrMetric>("oi");
  const [now, setNow] = useState<Date | null>(null);
  const [liveIso, setLiveIso] = useState("");
  const [sessionIso, setSessionIso] = useState("");
  const [followLive, setFollowLive] = useState(true);
  const [tapeAll, setTapeAll] = useState(false);

  useEffect(() => {
    const tick = () => setNow(new Date());
    tick();
    const id = window.setInterval(tick, 1000);
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
      if (pick) {
        setIndex(pick);
        setView("grid");
      }
      if (e.key === "g" || e.key === "G") setView("grid");
      if (e.key === "a" || e.key === "A") setView("board");
      if (e.key === "p" || e.key === "P") setView("path");
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
  const allIdeas = useMemo(() => {
    if (!tapeAll || !boards) return [];
    return PCR_INDICES.map((u) => ({ id: u.id, name: u.short, ...buildIdea(u.short, boards[u.id] ?? []) }));
  }, [tapeAll, boards]);
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

  return (
    <div className="kite-pcr">
      <style>{CSS}</style>
      <div className="kp-desk">
        <header className="kp-head">
          <div className="kp-head-row">
            <div>
              <p className="kp-kicker">Intraday + Weekly</p>
              <h1 className="kp-title">PCR Desk</h1>
            </div>
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
              <div className={`kp-chip ${live ? "kp-live" : ""}`}>{live ? "Live F&O" : "Stored"}</div>
              <div className="kp-seg" role="tablist" aria-label="View">
                <button type="button" role="tab" data-on={view === "grid"} onClick={() => setView("grid")}>Grid</button>
                <button type="button" role="tab" data-on={view === "board"} onClick={() => setView("board")}>All</button>
                <button type="button" role="tab" data-on={view === "path"} onClick={() => setView("path")}>Path</button>
              </div>
            </div>
          </div>
          <div className="kp-meta-row">
            <div className="kp-idx" role="tablist" aria-label="Underlying">
              {PCR_INDICES.map((u) => {
                const raw = payload?.series[u.id]?.livePcr ?? payload?.series[u.id]?.latest?.pcr ?? null;
                const val = isValidPrint(raw, "oi") ? raw : null;
                return (
                  <button key={u.id} type="button" role="tab" data-on={index === u.id} onClick={() => { setIndex(u.id); setView("grid"); }}>
                    {u.short}
                    {val != null ? <span className={`kp-chip-pcr kp-band-${pcrBand(val)}`}>{formatPcr(val)}</span> : null}
                  </button>
                );
              })}
            </div>
            <div className="kp-tabs" role="tablist" aria-label="PCR metric">
              {([["oi", "OI PCR"], ["volume", "Volume PCR"], ["changeOi", "ΔOI PCR"]] as const).map(([id, label]) => (
                <button key={id} type="button" role="tab" data-on={metric === id} onClick={() => setMetric(id)}>{label}</button>
              ))}
            </div>
          </div>
        </header>

        <div className="kp-body">
          {error && !payload ? <p className="kp-sub">{error}</p> : null}

          {hasSeries ? (
            <section className="kp-hero">
              <div className="kp-card">
                <p className="kp-kicker">Live print</p>
                <div className={`kp-print kp-band-${band}`}>{formatPcr(current) || "—"}</div>
                <p className="kp-sub">{lastFilled ? lastFilled.hhmm : "—"} · {bandTitle(band) || "Waiting for print"}</p>
                <Spark slots={grid} />
                <Split pcr={current} />
              </div>
              <div className="kp-card kp-read">
                <p className="kp-kicker">Read</p>
                <h2>{insight.headline}</h2>
                <p>{insight.reason}</p>
                <div className="kp-play">
                  <div className={`kp-play-tag ${insight.action === "Buy CE" ? "text-up" : insight.action === "Buy PE" ? "text-down" : ""}`}>
                    {insight.action}
                  </div>
                  <p>{insight.play}</p>
                </div>
                <div className="kp-conv">
                  <div>
                    <div className="lab">Bias</div>
                    <div className={`val ${insight.bias === "Bullish" ? "text-up" : insight.bias === "Bearish" ? "text-down" : ""}`}>{insight.bias}</div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div className="lab">Conviction {insight.conviction}</div>
                    <div className="kp-bar"><span style={{ width: `${insight.conviction}%` }} /></div>
                  </div>
                  <div>
                    <div className="lab">Regime</div>
                    <div className="val">{insight.regime}</div>
                  </div>
                </div>
              </div>
              <div className="kp-card kp-stats">
                <div>
                  <div className="lab">Δ 15m</div>
                  <div className={`val ${(delta ?? 0) > 0 ? "text-up" : (delta ?? 0) < 0 ? "text-down" : ""}`}>{formatDelta(delta)}</div>
                </div>
                <div>
                  <div className="lab">Spot</div>
                  <div className="val">
                    {fmtLtp(series?.spot.ltp)}
                    {series?.spot.changePer != null ? (
                      <span className={series.spot.changePer >= 0 ? "text-up" : "text-down"}>
                        {" "}{series.spot.changePer >= 0 ? "+" : ""}{series.spot.changePer.toFixed(2)}%
                      </span>
                    ) : null}
                  </div>
                </div>
                <div>
                  <div className="lab">Max pain</div>
                  <div className="val">{fmtLtp(series?.spot.maxPain)}</div>
                </div>
                <div>
                  <div className="lab">Expiry</div>
                  <div className="val">{expiryLabel}</div>
                </div>
                <div>
                  <div className="lab">Put share</div>
                  <div className="val">{putPct == null ? "—" : `${Math.round(putPct * 100)}%`}</div>
                </div>
                <div>
                  <div className="lab">Call share</div>
                  <div className="val">{putPct == null ? "—" : `${100 - Math.round(putPct * 100)}%`}</div>
                </div>
              </div>
            </section>
          ) : (
            <p className="kp-sub">{payload ? `No F&O prints stored for ${deskStamp}. Live feed keeps the current session.` : "Loading put-call prints…"}</p>
          )}

          {view === "path" && series ? (
            <Path slots={grid} marks={series.marks} />
          ) : (
            <div className="kp-main">
              {view === "grid" ? (
                <div className="kp-sheet">
                  {grid.length ? (
                    <table>
                      <thead>
                        <tr>
                          <th colSpan={3}>
                            {deskStamp}
                            <span style={{ marginLeft: 10, color: "var(--k-text)" }}>
                              {PCR_INDICES.find((u) => u.id === index)?.label} {metric === "oi" ? "OI" : metric === "volume" ? "Volume" : "ΔOI"} PCR
                            </span>
                          </th>
                        </tr>
                        <tr>
                          <th>Time</th>
                          <th style={{ textAlign: "center" }}>PCR</th>
                          <th style={{ textAlign: "right" }}>Δ</th>
                        </tr>
                      </thead>
                      <tbody>
                        {grid.map((slot) => (
                          <tr key={slot.hhmm} data-live={slot.live}>
                            <th>{slot.hhmm}</th>
                            <td>
                              <span className={`kp-heat kp-band-${slot.band}`}>{slot.pcr == null ? "" : formatPcr(slot.pcr)}</span>
                            </td>
                            <td>
                              <span className={`kp-delta ${(slot.delta ?? 0) > 0 ? "text-up" : (slot.delta ?? 0) < 0 ? "text-down" : ""}`}>
                                {formatDelta(slot.delta)}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="kp-empty">No prints for this session.</div>
                  )}
                </div>
              ) : (
                <div className="kp-sheet">
                  <table>
                    <thead>
                      <tr>
                        <th>{deskStamp}</th>
                        {PCR_INDICES.map((u) => <th key={u.id} style={{ textAlign: "center" }}>{u.short}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {(grid.length ? grid : []).map((slot, row) => (
                        <tr key={slot.hhmm}>
                          <th>{slot.hhmm}</th>
                          {PCR_INDICES.map((u) => {
                            const s = boards?.[u.id]?.[row];
                            return (
                              <td key={u.id}>
                                <span className={`kp-heat kp-band-${s?.band ?? "empty"}`}>
                                  {s?.pcr == null ? "" : formatPcr(s.pcr)}
                                </span>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="kp-side">
                <aside className="kp-card kp-tape">
                  <div className="kp-tape-head">
                    <p className="kp-kicker">What to buy</p>
                    <div className="kp-seg" role="tablist" aria-label="Idea scope">
                      <button type="button" data-on={!tapeAll} onClick={() => setTapeAll(false)}>This index</button>
                      <button type="button" data-on={tapeAll} onClick={() => setTapeAll(true)}>All</button>
                    </div>
                  </div>
                  {tapeAll ? (
                    <ul className="kp-all">
                      {allIdeas.map((row) => {
                        const line = row.idea;
                        const kind = line ? ideaKind(line.action) : "wait";
                        return (
                          <li key={row.id}>
                            <button
                              type="button"
                              className="kp-all-row"
                              onClick={() => { setIndex(row.id); setTapeAll(false); setView("grid"); }}
                            >
                              <span className="kp-all-name">{row.name}</span>
                              <span className={`kp-all-act ${kind}`}>{line ? line.action : "Wait"}</span>
                              <span className="kp-all-path">{line ? flowPath(line) : "—"}</span>
                              <span className="kp-all-clock">{line?.clock ?? ""}</span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  ) : idea.idea ? (
                    <div>
                      <div className={`kp-idea-act ${ideaKind(idea.idea.action)}`}>{idea.idea.action}</div>
                      <div className="kp-idea-meta">
                        <span>{idea.idea.name}</span>
                        <span>{idea.idea.clock}</span>
                      </div>
                      <div className="kp-idea-path">
                        {flowPath(idea.idea)}
                        <span className={`mv ${(idea.idea.move ?? 0) > 0 ? "text-up" : (idea.idea.move ?? 0) < 0 ? "text-down" : ""}`}>
                          {moveTxt(idea.idea.move)}
                        </span>
                      </div>
                      <p className="kp-idea-why">{idea.idea.why}</p>
                      {idea.earlier.length ? (
                        <div className="kp-ev">
                          <p className="kp-ev-lab">Earlier today</p>
                          {idea.earlier.map((e) => (
                            <div key={e.hhmm} className="kp-ev-row">
                              <span className="kp-ev-clock">{e.clock}</span>
                              <span className="kp-ev-path">{flowPath(e)}</span>
                              <span className={`kp-ev-tag ${ideaKind(e.action)}`}>{ideaTag(e.action)}</span>
                            </div>
                          ))}
                        </div>
                      ) : null}
                      {idea.idea.action !== "Wait" && idea.skipped > 0 ? (
                        <p className="kp-skip">
                          {idea.skipped} move{idea.skipped === 1 ? "" : "s"} skipped — PCR never crossed 1.00 going up, or 0.90 going down.
                        </p>
                      ) : null}
                    </div>
                  ) : (
                    <p className="kp-sub" style={{ marginTop: 12 }}>
                      No 15-minute jump yet. Need PCR above 1.00 and rising for CE, or below 0.90 and falling for PE.
                    </p>
                  )}
                </aside>
                <section className="kp-card kp-legend" aria-label="How to read PCR">
                  <h3 style={{ margin: 0, fontSize: 14, fontWeight: 500 }}>How to read PCR</h3>
                  <ul>
                    {(["positive", "highly-positive", "extreme-positive", "negative", "highly-negative", "extreme-negative"] as const).map((id) => (
                      <li key={id}>
                        <i className={`kp-swatch kp-band-${id}`} />
                        {BAND_COPY[id].hint}
                      </li>
                    ))}
                  </ul>
                  <p className="kp-sub" style={{ marginTop: 8 }}>
                    High PCR → put writing → Buy CE. Low PCR → call writing → Buy PE. Watch the 15-minute change, not a single print.
                  </p>
                </section>
              </div>
            </div>
          )}

          <p className="kp-foot">
            Click the date to pick a session. Keys 1–5 · G grid · A all · P path.
          </p>
        </div>
      </div>
    </div>
  );
}
