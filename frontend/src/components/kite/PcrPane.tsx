import { useEffect, useMemo, useRef, useState } from "react";
import { HEAD_METRICS, ROW_METRICS } from "./board/signalRowSpec";
import { fetchPcrDesk, sessionIsoOf } from "../../lib/pcr/fetchPcr";
import {
  BAND_COPY,
  FLOW_MOVE_MIN,
  SESSION_CLOSE_MIN,
  SESSION_OPEN_MIN,
  buildGrid,
  describeFlow,
  expiryKind,
  flowPath,
  formatDelta,
  formatExpiry,
  formatPcr,
  hhmmToMinutes,
  isValidPrint,
  lastValidSlot,
  liveAction,
  pcrBand,
  putShare,
  readBook,
  readPcr,
  type PcrAction,
  type PcrRead,
  type Stance,
} from "../../lib/pcr/slots";
import {
  PCR_INDICES,
  type PcrBand,
  type PcrDeskPayload,
  type PcrIndex,
  type PcrMetric,
  type PcrSlot,
} from "../../lib/pcr/types";
import { formatIstIsoDate, getIstParts } from "../../lib/astro/time";

type View = "grid" | "board" | "path";

function nowMinutes(now: Date): number {
  const p = getIstParts(now);
  return p.hour * 60 + p.minute;
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

function moveTxt(n: number): string {
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}`;
}

function stanceLab(s: Stance): string {
  if (s === "agrees") return "agrees";
  if (s === "fights") return "fights";
  return "—";
}

function playHint(action: PcrAction): string {
  if (action === "Buy PE") return "Skip CE";
  if (action === "Buy CE") return "Skip PE";
  return "0.80–1.20";
}

function bandLine(band: PcrBand): string {
  if (band === "extreme-positive") return "extreme positive";
  if (band === "highly-positive") return "highly positive";
  if (band === "positive") return "constructive";
  if (band === "negative") return "mild bearish";
  if (band === "highly-negative") return "highly negative";
  if (band === "extreme-negative") return "crowded calls";
  return "balanced";
}

function expiryLong(expiryIso: string, kind: "weekly" | "monthly" | "today"): string {
  if (!expiryIso) return "—";
  const [y, m, d] = expiryIso.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return formatExpiry(expiryIso);
  const dt = new Date(Date.UTC(y, m - 1, d));
  const wd = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][dt.getUTCDay()];
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sept", "Oct", "Nov", "Dec"];
  const k = kind === "today" ? "Today" : kind === "monthly" ? "Monthly" : "Weekly";
  return `${k} · ${wd}, ${d} ${months[m - 1]}`;
}

const PREF_KEY = "sterling.pcr.desk.v1";

const TILE_FIELDS = [
  { id: "print", label: "PCR print" },
  { id: "stamp", label: "Time / band" },
  { id: "split", label: "Puts / Calls" },
  { id: "headline", label: "Headline" },
  { id: "reason", label: "Read" },
  { id: "play", label: "Play" },
  { id: "bias", label: "Bias" },
  { id: "conviction", label: "Conviction" },
  { id: "regime", label: "Regime" },
  { id: "delta", label: "Δ 15m" },
  { id: "spot", label: "Spot" },
  { id: "pain", label: "Max pain" },
  { id: "expiry", label: "Expiry" },
  { id: "putOi", label: "Put OI" },
  { id: "callOi", label: "Call OI" },
] as const;

const SECTIONS = [
  { id: "book", label: "Book" },
  { id: "heat", label: "Heat" },
  { id: "tape", label: "Flow tape" },
  { id: "legend", label: "How to read" },
  { id: "read", label: "Read card" },
] as const;

const TABLE_COLS = [
  { id: "play", label: "Play" },
  { id: "pcr", label: "OI PCR" },
  { id: "move", label: "Move" },
  { id: "vol", label: "Vol" },
  { id: "doi", label: "ΔOI" },
  { id: "spot", label: "Spot" },
  { id: "pc", label: "P/C" },
  { id: "expiry", label: "Expiry" },
  { id: "pain", label: "Pain" },
] as const;

type TileField = (typeof TILE_FIELDS)[number]["id"];
type SectionId = (typeof SECTIONS)[number]["id"];
type ColId = (typeof TABLE_COLS)[number]["id"];
type Layout = "table" | "tiles";

type Prefs = {
  layout: Layout;
  sections: Record<SectionId, boolean>;
  tile: Record<TileField, boolean>;
  cols: Record<ColId, boolean>;
};

const DEFAULT_PREFS: Prefs = {
  layout: "tiles",
  sections: { book: true, heat: true, tape: true, legend: true, read: true },
  tile: Object.fromEntries(TILE_FIELDS.map((f) => [f.id, true])) as Prefs["tile"],
  cols: Object.fromEntries(TABLE_COLS.map((c) => [c.id, true])) as Prefs["cols"],
};

function loadPrefs(): Prefs {
  try {
    const raw = localStorage.getItem(PREF_KEY);
    if (!raw) return DEFAULT_PREFS;
    const p = JSON.parse(raw) as Partial<Prefs>;
    return {
      layout: p.layout === "table" ? "table" : "tiles",
      sections: { ...DEFAULT_PREFS.sections, ...p.sections },
      tile: { ...DEFAULT_PREFS.tile, ...p.tile },
      cols: { ...DEFAULT_PREFS.cols, ...p.cols },
    };
  } catch {
    return DEFAULT_PREFS;
  }
}

type DeskRow = {
  id: PcrIndex;
  name: string;
  pcr: number | null;
  action: PcrAction;
  why: string;
  path: string;
  move: number | null;
  vol: Stance;
  doi: Stance;
  spot: number | null;
  spotChg: number | null;
  delta: number | null;
  putPct: number | null;
  expiry: string;
  expiryLong: string;
  maxPain: number | null;
  hhmm: string;
  band: PcrBand;
  insight: PcrRead;
};

function IndexTile({ row, show }: { row: DeskRow; show: (id: TileField) => boolean }) {
  const put = row.putPct == null ? null : Math.round(row.putPct * 100);
  const call = put == null ? null : 100 - put;
  const kind = ideaKind(row.action);
  return (
    <article className="kp-tile">
      <div className="kp-tile-top">
        <span className="kp-tile-name">{row.name}</span>
        {show("play") ? <span className={`kp-tile-tag kp-act ${kind}`}>{row.action}</span> : null}
      </div>
      {show("print") ? (
        <div className={`kp-tile-pcr kp-band-${row.band}`}>{row.pcr != null ? formatPcr(row.pcr) : "—"}</div>
      ) : null}
      {show("stamp") ? (
        <p className="kp-sub">{row.hhmm || "—"}{row.band !== "empty" || row.pcr != null ? ` · ${bandLine(row.band)}` : ""}</p>
      ) : null}
      {show("split") && put != null ? (
        <div className="kp-split-wrap">
          <div className="kp-split-lab"><span>Puts {put}%</span><span>Calls {call}%</span></div>
          <div className="kp-split">
            <span className="kp-split-put" style={{ width: `${put}%` }} />
            <span className="kp-split-call" style={{ width: `${call}%` }} />
          </div>
        </div>
      ) : null}
      {show("headline") ? <h2>{row.insight.headline}</h2> : null}
      {show("reason") ? <p className="kp-sub">{row.insight.reason}</p> : null}
      {show("play") ? (
        <div className="kp-read-play">
          <span className={`kp-play-tag kp-act ${ideaKind(row.insight.action)}`}>{row.insight.action}</span>
          <p className="kp-sub">{row.insight.play}</p>
        </div>
      ) : null}
      {(show("bias") || show("conviction") || show("regime")) ? (
        <div className="kp-conv">
          {show("bias") ? (
            <div>
              <div className="lab">Bias</div>
              <div className={`val ${row.insight.bias === "Bullish" ? "text-up" : row.insight.bias === "Bearish" ? "text-down" : ""}`}>{row.insight.bias}</div>
            </div>
          ) : null}
          {show("conviction") ? (
            <div style={{ flex: 1 }}>
              <div className="lab">Conviction {row.insight.conviction}</div>
              <div className="kp-bar"><span style={{ width: `${row.insight.conviction}%` }} /></div>
            </div>
          ) : null}
          {show("regime") ? (
            <div>
              <div className="lab">Regime</div>
              <div className="val">{row.insight.regime}</div>
            </div>
          ) : null}
        </div>
      ) : null}
      <div className="kp-stats">
        {show("delta") ? (
          <div>
            <div className="lab">Δ 15m</div>
            <div className={`val ${(row.delta ?? 0) > 0 ? "text-up" : (row.delta ?? 0) < 0 ? "text-down" : ""}`}>{formatDelta(row.delta)}</div>
          </div>
        ) : null}
        {show("spot") ? (
          <div>
            <div className="lab">Spot</div>
            <div className="val">
              {fmtLtp(row.spot)}
              {row.spotChg != null ? (
                <span className={row.spotChg >= 0 ? "text-up" : "text-down"}>
                  {" "}{row.spotChg >= 0 ? "+" : ""}{row.spotChg.toFixed(2)}%
                </span>
              ) : null}
            </div>
          </div>
        ) : null}
        {show("pain") ? (
          <div>
            <div className="lab">Max pain</div>
            <div className="val">{fmtLtp(row.maxPain)}</div>
          </div>
        ) : null}
        {show("expiry") ? (
          <div>
            <div className="lab">Expiry</div>
            <div className="val">{row.expiryLong}</div>
          </div>
        ) : null}
        {show("putOi") ? (
          <div>
            <div className="lab">Put OI</div>
            <div className="val">—</div>
          </div>
        ) : null}
        {show("callOi") ? (
          <div>
            <div className="lab">Call OI</div>
            <div className="val">—</div>
          </div>
        ) : null}
      </div>
    </article>
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

const CSS = `
.kite-pcr{display:flex;flex-direction:column;height:100%;min-height:100%;background:var(--k-bg);color:var(--k-text);font-family:inherit;font-size:14px}
.kite-pcr *{box-sizing:border-box}
.kite-pcr .kp-desk{display:flex;flex-direction:column;min-height:100%}
.kite-pcr .kp-head{padding:8px 16px 0;border-bottom:1px solid var(--k-border)}
.kite-pcr .kp-head-row{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;padding-bottom:8px}
.kite-pcr .kp-kicker{margin:0;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--k-dim);font-weight:500}
.kite-pcr h1.kp-title{margin:0;font-size:16px;font-weight:600;letter-spacing:-.02em;line-height:1;color:var(--k-text)}
.kite-pcr .kp-tools{display:flex;flex-wrap:wrap;align-items:center;gap:6px}
.kite-pcr .kp-seg{display:flex;border:1px solid var(--k-border);background:var(--k-surface);border-radius:3px;overflow:hidden;height:28px}
.kite-pcr .kp-seg button{border:0;background:none;color:var(--k-dim);padding:0 10px;font-size:12px;cursor:pointer;font-family:inherit}
.kite-pcr .kp-seg button[data-on="true"]{background:var(--k-surface-hover);color:var(--k-text);font-weight:500}
.kite-pcr .kp-nav{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;padding-bottom:8px}
.kite-pcr .kp-idx{display:flex;flex-wrap:wrap;gap:4px}
.kite-pcr .kp-idx button{border:1px solid var(--k-border);background:var(--k-surface);color:var(--k-text);border-radius:3px;padding:5px 10px;font-size:12px;cursor:pointer;font-family:inherit}
.kite-pcr .kp-idx button[data-on="true"]{border-color:var(--k-orange);color:var(--k-orange);font-weight:500}
.kite-pcr .kp-tabs{display:flex;margin-left:auto;border:1px solid var(--k-border);background:var(--k-surface);border-radius:3px;overflow:hidden;height:28px}
.kite-pcr .kp-tabs button{border:0;background:none;color:var(--k-dim);padding:0 10px;font-size:12px;cursor:pointer;font-family:inherit}
.kite-pcr .kp-tabs button[data-on="true"]{background:var(--k-surface-hover);color:var(--k-text);font-weight:500}
.kite-pcr .kp-body{flex:1;padding:10px 16px 16px;overflow:auto}
.kite-pcr .kp-card{border:1px solid var(--k-border);background:var(--k-surface);border-radius:0;padding:12px}
.kite-pcr .kp-sub{margin:0;font-size:12px;color:var(--k-dim);line-height:1.45}
.kite-pcr .text-up{color:var(--k-green)}
.kite-pcr .text-down{color:var(--k-red)}
.kite-pcr .kp-act.ce{color:var(--k-green)}
.kite-pcr .kp-act.pe{color:var(--k-red)}
.kite-pcr .kp-act.wait{color:var(--k-dim)}
.kite-pcr .kp-st.agrees{color:var(--k-green)}
.kite-pcr .kp-st.fights{color:var(--k-red)}
.kite-pcr .kp-st.quiet{color:var(--k-dim)}
.kite-pcr .kp-stack{display:flex;flex-direction:column;gap:10px}
.kite-pcr .kp-sheet{overflow:auto;border:1px solid var(--k-border);border-radius:4px;background:var(--k-surface)}
.kite-pcr .kp-sheet:not(.kp-sheet-heat){overflow:visible}
.kite-pcr .kp-sheet-heat{max-height:calc(100vh - 280px);border-radius:0}
.kite-pcr table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;table-layout:fixed}
.kite-pcr thead th{position:sticky;top:0;z-index:2;background:var(--k-surface);color:var(--k-dim);font-weight:500;font-size:11px;letter-spacing:.06em;text-transform:uppercase;padding:8px 10px;text-align:center;border-bottom:1px solid var(--k-border);white-space:nowrap}
.kite-pcr thead th:first-child{text-align:left;cursor:default;position:sticky;left:0;z-index:3}
.kite-pcr thead th[data-on="true"]{color:var(--k-orange);font-weight:600}
.kite-pcr tbody th{position:sticky;left:0;z-index:1;padding:8px 10px;font-size:12px;font-weight:400;color:var(--k-dim);text-align:left;background:var(--k-surface);border-bottom:1px solid var(--k-border);white-space:nowrap}
.kite-pcr tbody td{padding:8px 10px;font-size:13px;border-bottom:1px solid var(--k-border);vertical-align:middle;text-align:center}
.kite-pcr tbody tr[data-live="true"] th{color:var(--k-orange);font-weight:600}
.kite-pcr .kp-book col.c-idx{width:72px}
.kite-pcr .kp-book col.c-play{width:92px}
.kite-pcr .kp-book col.c-pcr{width:76px}
.kite-pcr .kp-book col.c-move{width:148px}
.kite-pcr .kp-book col.c-st{width:64px}
.kite-pcr .kp-book col.c-spot{width:148px}
.kite-pcr .kp-book col.c-pc{width:64px}
.kite-pcr .kp-book col.c-exp{width:88px}
.kite-pcr .kp-book col.c-pain{width:88px}
.kite-pcr .kp-book tbody th{font-weight:600;color:var(--k-text);font-size:${ROW_METRICS.instrumentFontSize}px}
.kite-pcr .kp-book thead th{font-size:${HEAD_METRICS.fontSize}px;font-weight:${HEAD_METRICS.fontWeight};letter-spacing:${HEAD_METRICS.letterSpacing};text-transform:${HEAD_METRICS.textTransform};padding:${HEAD_METRICS.padding};color:var(--k-dim)}
.kite-pcr .kp-book thead th,.kite-pcr .kp-book tbody td{white-space:nowrap}
.kite-pcr .kp-book tbody td{font-size:${ROW_METRICS.cellFontSize}px;font-weight:400;padding:0 10px;height:${ROW_METRICS.legHeight}px}
.kite-pcr .kp-book tbody th{padding:0 10px;height:${ROW_METRICS.legHeight}px}
.kite-pcr .kp-book thead th{text-align:left}
.kite-pcr .kp-book tbody td{text-align:left}
.kite-pcr .kp-book thead th.num,.kite-pcr .kp-book tbody td.num{text-align:right}
.kite-pcr .kp-book thead th.mid,.kite-pcr .kp-book tbody td.mid{text-align:center}
.kite-pcr .kp-pcr{font-size:${ROW_METRICS.cellFontSize}px;font-weight:400;letter-spacing:0}
.kite-pcr .kp-play{font-weight:400;letter-spacing:0;white-space:nowrap;font-size:${ROW_METRICS.cellFontSize}px}
.kite-pcr .kp-play-cell{position:relative}
.kite-pcr .kp-tip{display:none;position:absolute;left:8px;top:calc(100% - 2px);z-index:6;background:var(--k-surface);border:1px solid var(--k-border);color:var(--k-text);padding:5px 8px;font-size:${ROW_METRICS.cellFontSize}px;font-weight:400;white-space:nowrap;border-radius:3px;box-shadow:0 6px 16px rgba(0,0,0,.18);pointer-events:none}
.kite-pcr .kp-play-cell:hover .kp-tip{display:block}
.kite-pcr .kp-book tbody tr:last-child .kp-tip{top:auto;bottom:calc(100% - 2px)}
.kite-pcr .kp-move{font-size:${ROW_METRICS.cellFontSize}px;color:var(--k-text)}
.kite-pcr .kp-spot{display:flex;justify-content:flex-end;align-items:baseline;gap:8px;font-size:${ROW_METRICS.cellFontSize}px}
.kite-pcr .kp-spot .ltp{min-width:8.5ch;text-align:right}
.kite-pcr .kp-chg{min-width:5.2ch;text-align:right;font-size:${ROW_METRICS.cellFontSize}px}
.kite-pcr .kp-sheet-heat col.c-time{width:72px}
.kite-pcr .kp-sheet-heat.one{width:fit-content;max-width:100%}
.kite-pcr .kp-sheet-heat.one table{width:auto}
.kite-pcr .kp-sheet-heat.one col:not(.c-time){width:108px}
.kite-pcr .kp-heat-row td{padding:0;text-align:center;border-bottom:0}
.kite-pcr .kp-heat-row th{padding:4px 10px;font-variant-numeric:tabular-nums;border-bottom:0}
.kite-pcr .kp-heat{display:block;width:100%;text-align:center;font-size:12px;font-weight:500;padding:7px 4px;border-radius:0;min-height:26px;box-sizing:border-box}
.kite-pcr .kp-delta{display:block;text-align:right;padding:5px 6px;font-size:12px;color:var(--k-dim)}
.kite-pcr .kp-band-extreme-positive{background:#1b5e4a;color:#f4f4f5}
.kite-pcr .kp-band-highly-positive{background:#2e7a64;color:#f4f4f5}
.kite-pcr .kp-band-positive{background:#b7d9cf;color:#12332c}
.kite-pcr .kp-band-negative{background:#e4c4c4;color:#3a1818}
.kite-pcr .kp-band-highly-negative{background:#c97a7a;color:#1a0c0c}
.kite-pcr .kp-band-extreme-negative{background:#a33a3a;color:#f4f4f5}
.kite-pcr .kp-band-empty{background:transparent;color:var(--k-text)}
.kite-pcr .kp-notes{display:grid;grid-template-columns:1.15fr .95fr .95fr;gap:10px;margin-top:10px}
.kite-pcr .kp-read h2{margin:6px 0 4px;font-size:15px;font-weight:600;letter-spacing:-.02em;line-height:1.3}
.kite-pcr .kp-read .kp-sub{margin:0}
.kite-pcr .kp-read-play{margin-top:10px;padding:8px 10px;background:var(--k-surface-hover);border:1px solid var(--k-border)}
.kite-pcr .kp-read-play .kp-play-tag{display:block;font-size:11px;font-weight:600;margin-bottom:2px}
.kite-pcr .kp-conv{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-top:12px}
.kite-pcr .kp-conv .lab{font-size:11px;color:var(--k-dim)}
.kite-pcr .kp-conv .val{font-size:13px;font-weight:500;margin:2px 0 0}
.kite-pcr .kp-bar{height:4px;background:var(--k-surface-hover);overflow:hidden;margin-top:6px}
.kite-pcr .kp-bar>span{display:block;height:100%;background:var(--k-blue)}
.kite-pcr .kp-tape ul,.kite-pcr .kp-legend ul{list-style:none;margin:8px 0 0;padding:0}
.kite-pcr .kp-tape li{font-size:12px;margin:0 0 8px;padding:0 0 8px;border-bottom:1px solid var(--k-border);line-height:1.4}
.kite-pcr .kp-tape li:last-child{margin:0;padding:0;border:0}
.kite-pcr .kp-tape b{font-weight:600}
.kite-pcr .kp-legend li{display:flex;gap:8px;align-items:flex-start;font-size:12px;line-height:1.4;margin:0 0 7px;color:var(--k-text)}
.kite-pcr .kp-swatch{flex:0 0 12px;width:12px;height:12px;margin-top:3px}
.kite-pcr .kp-foot{margin:10px 0 0;font-size:11px;color:var(--k-dim)}
.kite-pcr .kp-path-svg{width:100%;height:220px}
.kite-pcr .kp-path-pcr{fill:none;stroke:var(--k-blue);stroke-width:2}
.kite-pcr .kp-path-spot{fill:none;stroke:var(--k-green);stroke-width:1.5}
.kite-pcr .kp-path-key{display:flex;gap:16px;font-size:12px;color:var(--k-dim);margin-top:8px}
.kite-pcr .kp-path-key i{display:inline-block;width:12px;height:2px;margin-right:6px;vertical-align:middle}
.kite-pcr .kp-key-pcr{background:var(--k-blue)}
.kite-pcr .kp-key-spot{background:var(--k-green)}
.kite-pcr .kp-muted{color:var(--k-dim)}
.kite-pcr .kp-empty{padding:28px 8px;text-align:center;color:var(--k-dim);font-size:13px}
.kite-pcr .kp-tools{position:relative}
.kite-pcr .kp-gear{border:1px solid var(--k-border);background:var(--k-surface);color:var(--k-dim);width:28px;height:28px;cursor:pointer;font-family:inherit;font-size:14px}
.kite-pcr .kp-gear[data-on="true"]{color:var(--k-orange);border-color:var(--k-orange)}
.kite-pcr .kp-prefs{position:absolute;right:0;top:34px;z-index:30;width:272px;background:var(--k-surface);border:1px solid var(--k-border);padding:10px 12px;box-shadow:0 10px 24px rgba(0,0,0,.22)}
.kite-pcr .kp-prefs h3{margin:10px 0 6px;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--k-dim);font-weight:600}
.kite-pcr .kp-prefs h3:first-child{margin-top:0}
.kite-pcr .kp-prefs label{display:flex;align-items:center;gap:8px;font-size:12px;padding:3px 0;cursor:pointer;color:var(--k-text)}
.kite-pcr .kp-prefs input{margin:0;accent-color:var(--k-orange)}
.kite-pcr .kp-prefs .kp-pref-row{display:flex;gap:6px;margin-bottom:4px}
.kite-pcr .kp-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px}
.kite-pcr .kp-tiles.one{grid-template-columns:minmax(280px,420px)}
.kite-pcr .kp-tile{border:1px solid var(--k-border);background:var(--k-surface);padding:14px;display:flex;flex-direction:column;gap:8px}
.kite-pcr .kp-tile-top{display:flex;align-items:center;justify-content:space-between;gap:8px}
.kite-pcr .kp-tile-name{font-size:13px;font-weight:600}
.kite-pcr .kp-tile-tag{font-size:11px;font-weight:600;letter-spacing:.04em}
.kite-pcr .kp-tile-pcr{font-size:40px;font-weight:600;font-variant-numeric:tabular-nums;letter-spacing:-.04em;line-height:1;padding:6px 10px;align-self:flex-start}
.kite-pcr .kp-tile h2{margin:4px 0 0;font-size:15px;font-weight:600;letter-spacing:-.02em;line-height:1.3}
.kite-pcr .kp-split-wrap{margin:2px 0 4px}
.kite-pcr .kp-split-lab{display:flex;justify-content:space-between;font-size:11px;font-variant-numeric:tabular-nums;color:var(--k-dim);margin-bottom:4px}
.kite-pcr .kp-split{display:flex;height:4px;overflow:hidden;background:var(--k-surface-hover)}
.kite-pcr .kp-split-put{background:var(--k-green)}
.kite-pcr .kp-split-call{background:var(--k-red)}
.kite-pcr .kp-stats{display:grid;grid-template-columns:1fr 1fr;gap:10px 16px;margin-top:6px}
.kite-pcr .kp-stats .lab{font-size:11px;color:var(--k-dim)}
.kite-pcr .kp-stats .val{font-size:13px;font-variant-numeric:tabular-nums;margin-top:2px}
@media (max-width:980px){
  .kite-pcr .kp-head,.kite-pcr .kp-body{padding-left:10px;padding-right:10px}
  .kite-pcr .kp-notes{grid-template-columns:1fr}
}
`;

export function PcrPane() {
  const [payload, setPayload] = useState<PcrDeskPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState<PcrIndex>("NIFTY");
  const [view, setView] = useState<View>("board");
  const [metric, setMetric] = useState<PcrMetric>("oi");
  const [now, setNow] = useState<Date | null>(null);
  const [liveIso, setLiveIso] = useState("");
  const [sessionIso, setSessionIso] = useState("");
  const [prefs, setPrefs] = useState<Prefs>(loadPrefs);
  const [prefsOpen, setPrefsOpen] = useState(false);
  const prefsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try { localStorage.setItem(PREF_KEY, JSON.stringify(prefs)); } catch { /* ignore */ }
  }, [prefs]);

  useEffect(() => {
    if (!prefsOpen) return;
    const onDown = (e: MouseEvent) => {
      if (prefsRef.current && !prefsRef.current.contains(e.target as Node)) setPrefsOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setPrefsOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [prefsOpen]);

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
      fetchPcrDesk(null)
        .then((data) => {
          if (cancelled) return;
          setPayload(data);
          setError(null);
          const iso = sessionIsoOf(data);
          if (iso) {
            setLiveIso(iso);
            setSessionIso(iso);
          }
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
      if (e.key === "a" || e.key === "A") setView("board");
      if (e.key === "p" || e.key === "P") setView("path");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const todayIso = now ? formatIstIsoDate(now) : liveIso;
  const series = payload?.series[index];
  const nowMin = now ? nowMinutes(now) : null;
  const inLiveSession = Boolean(
    nowMin != null && nowMin >= SESSION_OPEN_MIN && nowMin < SESSION_CLOSE_MIN,
  );
  const gridNowMin = inLiveSession ? nowMin : SESSION_CLOSE_MIN;
  const metricBoards = useMemo(() => {
    if (!payload) return null;
    const make = (m: PcrMetric) => {
      const out = {} as Record<PcrIndex, PcrSlot[]>;
      for (const u of PCR_INDICES) {
        const row = payload.series[u.id];
        if (!row) continue;
        out[u.id] = buildGrid(row.marks, row.latest, gridNowMin, m);
      }
      return out;
    };
    return { oi: make("oi"), volume: make("volume"), changeOi: make("changeOi") };
  }, [payload, gridNowMin]);
  const boards = metricBoards?.[metric] ?? null;
  const grid = boards?.[index] ?? [];
  const axis = boards?.NIFTY ?? boards?.[PCR_INDICES[0].id] ?? [];

  const deskRows = useMemo(() => {
    if (!metricBoards) return [];
    return PCR_INDICES.map((u) => {
      const oi = metricBoards.oi[u.id] ?? [];
      const book = readBook(u.short, oi, metricBoards.volume[u.id] ?? [], metricBoards.changeOi[u.id] ?? []);
      const last = lastValidSlot(oi, "oi");
      const raw = book.book?.to ?? last?.pcr ?? payload?.series[u.id]?.livePcr ?? payload?.series[u.id]?.latest?.pcr ?? null;
      const pcr = isValidPrint(raw, "oi") ? raw : null;
      const filled = oi.filter((s) => isValidPrint(s.pcr, "oi"));
      const prev = filled.length >= 2 ? filled[filled.length - 2] : null;
      const delta =
        pcr != null && prev?.pcr != null
          ? Math.round((pcr - prev.pcr) * 100) / 100
          : (last?.delta ?? null);
      const row = payload?.series[u.id];
      const kind = row ? expiryKind(row.expiry, sessionIso || todayIso) : "weekly";
      const expiry = row
        ? `${kind === "today" ? "Today" : kind === "weekly" ? "Wk" : "Mo"} ${formatExpiry(row.expiry)}`
        : "—";
      const action = book.book?.action ?? liveAction(pcr);
      const insight = readPcr(oi, row?.spot.changePer ?? null);
      const band = last?.band ?? pcrBand(pcr);
      return {
        id: u.id,
        name: u.short,
        pcr,
        action,
        why: book.book?.why ?? "Waiting on the OI print.",
        path: book.book ? flowPath(book.book) : "—",
        move: book.book?.move ?? delta,
        vol: book.volumeStance,
        doi: book.deltaStance,
        spot: row?.spot.ltp ?? null,
        spotChg: row?.spot.changePer ?? null,
        delta,
        putPct: putShare(pcr),
        expiry,
        expiryLong: row ? expiryLong(row.expiry, kind) : "—",
        maxPain: row?.spot.maxPain ?? null,
        hhmm: last?.hhmm ?? "",
        band,
        insight,
      };
    });
  }, [metricBoards, payload, sessionIso, todayIso]);
  const showAll = view === "board";
  const cols = showAll ? PCR_INDICES : PCR_INDICES.filter((u) => u.id === index);
  const sumRows = showAll ? deskRows : deskRows.filter((r) => r.id === index);
  const heatSlots = showAll ? axis : grid;
  const insight = useMemo(() => readPcr(grid, series?.spot.changePer ?? null), [grid, series?.spot.changePer]);
  const tape = useMemo(() => {
    const src = showAll ? PCR_INDICES : PCR_INDICES.filter((u) => u.id === index);
    const out: { id: string; name: string; action: PcrAction; why: string; clock: string; hhmm: string }[] = [];
    for (const u of src) {
      const row = (metricBoards?.oi[u.id] ?? []);
      for (const s of row) {
        if (s.delta == null || Math.abs(s.delta) < FLOW_MOVE_MIN) continue;
        if (!isValidPrint(s.pcr, "oi")) continue;
        const line = describeFlow(u.short, s.hhmm, s.pcr, s.delta, "oi");
        out.push({ id: `${u.id}-${s.hhmm}`, name: line.name, action: line.action, why: line.why, clock: line.clock, hhmm: line.hhmm });
      }
    }
    return out.sort((a, b) => hhmmToMinutes(b.hhmm) - hhmmToMinutes(a.hhmm)).slice(0, 8);
  }, [metricBoards, showAll, index]);
  const showSec = (id: SectionId) => prefs.sections[id];
  const showTile = (id: TileField) => prefs.tile[id];
  const showCol = (id: ColId) => prefs.cols[id];
  const toggleSec = (id: SectionId) => setPrefs((p) => ({ ...p, sections: { ...p.sections, [id]: !p.sections[id] } }));
  const toggleTile = (id: TileField) => setPrefs((p) => ({ ...p, tile: { ...p.tile, [id]: !p.tile[id] } }));
  const toggleCol = (id: ColId) => setPrefs((p) => ({ ...p, cols: { ...p.cols, [id]: !p.cols[id] } }));
  const notesOn = (prefs.layout === "table" && showSec("read")) || showSec("tape") || showSec("legend");

  return (
    <div className="kite-pcr">
      <style>{CSS}</style>
      <div className="kp-desk">
        <header className="kp-head">
          <div className="kp-head-row">
            <h1 className="kp-title">PCR Desk</h1>
            <div className="kp-tools" ref={prefsRef}>
              <div className="kp-seg" role="tablist" aria-label="Layout">
                <button type="button" data-on={prefs.layout === "tiles"} onClick={() => setPrefs((p) => ({ ...p, layout: "tiles" }))}>Tiles</button>
                <button type="button" data-on={prefs.layout === "table"} onClick={() => setPrefs((p) => ({ ...p, layout: "table" }))}>Table</button>
              </div>
              <button type="button" className="kp-gear" data-on={prefsOpen} aria-expanded={prefsOpen} aria-label="Display settings" onClick={() => setPrefsOpen((v) => !v)}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9c.3.6.9 1 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
                </svg>
              </button>
              {prefsOpen ? (
                <div className="kp-prefs" role="dialog" aria-label="Display settings">
                  <h3>Show</h3>
                  {SECTIONS.filter((s) => prefs.layout === "table" || s.id !== "read").map((s) => (
                    <label key={s.id}>
                      <input type="checkbox" checked={prefs.sections[s.id]} onChange={() => toggleSec(s.id)} />
                      {s.label}
                    </label>
                  ))}
                  {prefs.layout === "tiles" ? (
                    <>
                      <h3>On each tile</h3>
                      {TILE_FIELDS.map((f) => (
                        <label key={f.id}>
                          <input type="checkbox" checked={prefs.tile[f.id]} onChange={() => toggleTile(f.id)} />
                          {f.label}
                        </label>
                      ))}
                    </>
                  ) : (
                    <>
                      <h3>Table columns</h3>
                      {TABLE_COLS.map((c) => (
                        <label key={c.id}>
                          <input type="checkbox" checked={prefs.cols[c.id]} onChange={() => toggleCol(c.id)} />
                          {c.label}
                        </label>
                      ))}
                    </>
                  )}
                </div>
              ) : null}
            </div>
          </div>
          <div className="kp-nav">
            <div className="kp-idx" role="tablist" aria-label="Underlying">
              <button type="button" role="tab" data-on={view === "board"} onClick={() => setView("board")}>All</button>
              {PCR_INDICES.map((u) => (
                <button
                  key={u.id}
                  type="button"
                  role="tab"
                  data-on={view !== "board" && index === u.id}
                  onClick={() => { setIndex(u.id); setView(view === "path" ? "path" : "grid"); }}
                >
                  {u.short}
                </button>
              ))}
              <button type="button" role="tab" data-on={view === "path"} onClick={() => setView("path")}>Path</button>
            </div>
            <div className="kp-tabs" role="tablist" aria-label="PCR metric">
              {([["oi", "OI"], ["volume", "Volume"], ["changeOi", "ΔOI"]] as const).map(([id, label]) => (
                <button key={id} type="button" role="tab" data-on={metric === id} onClick={() => setMetric(id)}>{label}</button>
              ))}
            </div>
          </div>
        </header>

        <div className="kp-body">
          {error && !payload ? <p className="kp-sub">{error}</p> : null}

          {view === "path" && series ? (
            <Path slots={grid} marks={series.marks} />
          ) : sumRows.length ? (
            <div className="kp-stack">
              {showSec("book") && prefs.layout === "tiles" ? (
                <div className={`kp-tiles${showAll ? "" : " one"}`}>
                  {sumRows.map((row) => <IndexTile key={row.id} row={row} show={showTile} />)}
                </div>
              ) : null}

              {showSec("book") && prefs.layout === "table" ? (
                <div className="kp-sheet">
                  <table className="kp-book">
                    <thead>
                      <tr>
                        <th>Index</th>
                        {showCol("play") ? <th>Play</th> : null}
                        {showCol("pcr") ? <th className="num">OI PCR</th> : null}
                        {showCol("move") ? <th className="num">Move</th> : null}
                        {showCol("vol") ? <th className="mid">Vol</th> : null}
                        {showCol("doi") ? <th className="mid">ΔOI</th> : null}
                        {showCol("spot") ? <th className="num">Spot</th> : null}
                        {showCol("pc") ? <th className="mid">P/C</th> : null}
                        {showCol("expiry") ? <th>Expiry</th> : null}
                        {showCol("pain") ? <th className="num">Pain</th> : null}
                      </tr>
                    </thead>
                    <tbody>
                      {sumRows.map((row) => {
                        const kind = ideaKind(row.action);
                        return (
                          <tr key={row.id}>
                            <th>{row.name}</th>
                            {showCol("play") ? (
                              <td className="kp-play-cell">
                                <span className={`kp-play kp-act ${kind}`}>{row.action}</span>
                                <span className="kp-tip">{playHint(row.action)}</span>
                              </td>
                            ) : null}
                            {showCol("pcr") ? <td className={`kp-pcr kp-act ${kind} num`}>{row.pcr != null ? formatPcr(row.pcr) : "—"}</td> : null}
                            {showCol("move") ? (
                              <td className="kp-move num">
                                {row.path}
                                {row.move != null ? (
                                  <span className={(row.move ?? 0) > 0 ? "text-up" : (row.move ?? 0) < 0 ? "text-down" : ""}>
                                    {" "}{moveTxt(row.move)}
                                  </span>
                                ) : null}
                              </td>
                            ) : null}
                            {showCol("vol") ? <td className={`kp-st ${row.vol} mid`}>{stanceLab(row.vol)}</td> : null}
                            {showCol("doi") ? <td className={`kp-st ${row.doi} mid`}>{stanceLab(row.doi)}</td> : null}
                            {showCol("spot") ? (
                              <td className="num">
                                <span className="kp-spot">
                                  <span className="ltp">{fmtLtp(row.spot)}</span>
                                  {row.spotChg != null ? (
                                    <span className={`kp-chg ${row.spotChg >= 0 ? "text-up" : "text-down"}`}>
                                      {row.spotChg >= 0 ? "+" : ""}{row.spotChg.toFixed(2)}%
                                    </span>
                                  ) : null}
                                </span>
                              </td>
                            ) : null}
                            {showCol("pc") ? <td className="mid">{row.putPct == null ? "—" : `${Math.round(row.putPct * 100)}/${100 - Math.round(row.putPct * 100)}`}</td> : null}
                            {showCol("expiry") ? <td>{row.expiry}</td> : null}
                            {showCol("pain") ? <td className="num">{fmtLtp(row.maxPain)}</td> : null}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : null}

              {showSec("heat") ? (
                <div className={`kp-sheet kp-sheet-heat${showAll ? "" : " one"}`}>
                  <table>
                    <colgroup>
                      <col className="c-time" />
                      {cols.map((u) => <col key={u.id} />)}
                    </colgroup>
                    <thead>
                      <tr>
                        <th>Time</th>
                        {cols.map((u) => (
                          <th key={u.id} data-on={!showAll && index === u.id}>{u.short}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {heatSlots.map((slot, row) => (
                        <tr key={slot.hhmm} className="kp-heat-row" data-live={slot.live}>
                          <th>{slot.hhmm}</th>
                          {cols.map((u) => {
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
              ) : null}
            </div>
          ) : (
            <p className="kp-sub">{payload ? "No F&O prints yet this session." : "Loading put-call prints…"}</p>
          )}

          {payload && notesOn ? (
            <div className="kp-notes">
              {prefs.layout === "table" && showSec("read") ? (
                <div className="kp-card kp-read">
                  <p className="kp-kicker">Read · {PCR_INDICES.find((u) => u.id === index)?.short}</p>
                  <h2>{insight.headline}</h2>
                  <p className="kp-sub">{insight.reason}</p>
                  <div className="kp-read-play">
                    <span className={`kp-play-tag kp-act ${ideaKind(insight.action)}`}>{insight.action}</span>
                    <p className="kp-sub">{insight.play}</p>
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
              ) : null}
              {showSec("tape") ? (
                <aside className="kp-card kp-tape">
                  <p className="kp-kicker">Flow tape</p>
                  {tape.length ? (
                    <ul>
                      {tape.map((e) => (
                        <li key={e.id}>
                          <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                            <b>{e.name} · <span className={`kp-act ${ideaKind(e.action)}`}>{e.action}</span></b>
                            <span className="kp-sub">{e.clock}</span>
                          </div>
                          <div className="kp-sub" style={{ marginTop: 3 }}>{e.why}</div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="kp-sub" style={{ marginTop: 10 }}>Quiet book — no 6-tick PCR jumps yet.</p>
                  )}
                </aside>
              ) : null}
              {showSec("legend") ? (
                <section className="kp-card kp-legend" aria-label="How to read PCR">
                  <p className="kp-kicker">How to read PCR</p>
                  <ul>
                    {(["positive", "highly-positive", "extreme-positive", "negative", "highly-negative", "extreme-negative"] as const).map((id) => (
                      <li key={id}>
                        <i className={`kp-swatch kp-band-${id}`} />
                        {BAND_COPY[id].hint}
                      </li>
                    ))}
                  </ul>
                  <p className="kp-sub" style={{ marginTop: 8 }}>
                    OI PCR is put open interest ÷ call open interest on the front weekly expiry (monthly when that is the listed series). Watch the 15-minute change, not a single print.
                  </p>
                </section>
              ) : null}
            </div>
          ) : null}

          <p className="kp-foot">All five, or one index. Path is PCR vs spot. 1–5 index · A all · P path</p>
        </div>
      </div>
    </div>
  );
}
