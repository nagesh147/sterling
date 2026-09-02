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
  formatExpiry,
  formatPcr,
  isValidPrint,
  lastValidSlot,
  liveAction,
  pcrBand,
  putShare,
  readBook,
  type PcrAction,
  type Stance,
} from "../../lib/pcr/slots";
import {
  PCR_INDICES,
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

function ideaTag(action: PcrAction): string {
  if (action === "Buy CE") return "CE";
  if (action === "Buy PE") return "PE";
  return "Wait";
}

function moveTxt(n: number): string {
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}`;
}

function stanceLab(s: Stance): string {
  if (s === "agrees") return "agrees";
  if (s === "fights") return "fights";
  return "quiet";
}

function EvidenceRow({
  label,
  line,
  stance,
}: {
  label: string;
  line: ReturnType<typeof readBook>["volume"];
  stance: Stance | "book";
}) {
  const kind = stance === "book" ? "agrees" : stance;
  return (
    <div className={`kp-evd ${kind}`}>
      <span className="kp-evd-lab">{label}</span>
      <span className="kp-evd-path">{line ? flowPath(line) : "—"}</span>
      <span className={`kp-evd-tag ${line ? ideaKind(line.action) : "wait"}`}>{line ? ideaTag(line.action) : "—"}</span>
      <span className="kp-evd-st">{stance === "book" ? "the book" : stanceLab(stance)}</span>
    </div>
  );
}

function BookPanel({
  book,
  earlier,
  tapeAll,
  allRows,
  onPick,
}: {
  book: ReturnType<typeof readBook>;
  earlier: ReturnType<typeof buildIdea>["earlier"];
  tapeAll: boolean;
  allRows: { id: PcrIndex; name: string; book: ReturnType<typeof readBook> }[];
  onPick: (id: PcrIndex) => void;
}) {
  const idea = book.book;
  return (
    <div>
      {tapeAll ? (
        <ul className="kp-all">
          {allRows.map((row) => {
            const line = row.book.book;
            const kind = line ? ideaKind(line.action) : "wait";
            return (
              <li key={row.id}>
                <button type="button" className="kp-all-row" onClick={() => onPick(row.id)}>
                  <span className="kp-all-name">{row.name}</span>
                  <span className={`kp-all-act ${kind}`}>{line ? line.action : "Wait"}</span>
                  <span className="kp-all-path">{line ? flowPath(line) : "—"}</span>
                  <span className="kp-all-clock">
                    Vol {stanceLab(row.book.volumeStance)} · ΔOI {stanceLab(row.book.deltaStance)}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : idea ? (
        <div>
          <div className={`kp-idea-act ${ideaKind(idea.action)}`}>{idea.action}</div>
          <div className="kp-idea-meta">
            <span>{idea.name} · OI book</span>
            <span>{idea.clock}</span>
          </div>
          <div className="kp-idea-path">
            {flowPath(idea)}
            <span className={`mv ${(idea.move ?? 0) > 0 ? "text-up" : (idea.move ?? 0) < 0 ? "text-down" : ""}`}>
              {moveTxt(idea.move)}
            </span>
          </div>
          <p className="kp-idea-why">{idea.why}</p>
          <div className="kp-evd-wrap">
            <EvidenceRow label="OI PCR" line={idea} stance="book" />
            <EvidenceRow label="Volume" line={book.volume} stance={book.volumeStance} />
            <EvidenceRow label="ΔOI" line={book.deltaOi} stance={book.deltaStance} />
          </div>
          {book.note ? <p className="kp-skip">{book.note}</p> : null}
          {earlier.length ? (
            <div className="kp-ev">
              <p className="kp-ev-lab">Earlier OI — not live</p>
              {earlier.map((e) => (
                <div key={e.hhmm} className="kp-ev-row">
                  <span className="kp-ev-clock">{e.clock}</span>
                  <span className="kp-ev-path">{flowPath(e)}</span>
                  <span className={`kp-ev-tag ${ideaKind(e.action)}`}>{ideaTag(e.action)}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : (
        <p className="kp-sub" style={{ marginTop: 8 }}>
          Waiting on the OI print. Volume and ΔOI do not issue a CE/PE on their own.
        </p>
      )}
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

const CSS = `
.kite-pcr{display:flex;flex-direction:column;height:100%;min-height:100%;background:var(--k-bg);color:var(--k-text);font-family:inherit;font-size:14px}
.kite-pcr *{box-sizing:border-box}
.kite-pcr .kp-desk{display:flex;flex-direction:column;min-height:100%}
.kite-pcr .kp-head{padding:8px 16px 0;border-bottom:1px solid var(--k-border)}
.kite-pcr .kp-head-row{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px}
.kite-pcr .kp-kicker{margin:0;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--k-dim);font-weight:500}
.kite-pcr h1.kp-title{margin:0;font-size:16px;font-weight:600;letter-spacing:-.02em;line-height:1;color:var(--k-text)}
.kite-pcr .kp-tools{display:flex;flex-wrap:wrap;align-items:center;gap:6px}
.kite-pcr .kp-seg{display:flex;border:1px solid var(--k-border);background:var(--k-surface);border-radius:3px;overflow:hidden;height:28px}
.kite-pcr .kp-seg button{border:0;background:none;color:var(--k-dim);padding:0 10px;font-size:12px;cursor:pointer;font-family:inherit}
.kite-pcr .kp-seg button[data-on="true"]{background:var(--k-surface-hover);color:var(--k-text);font-weight:500}
.kite-pcr .kp-plays{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px;margin:10px 0 8px}
.kite-pcr .kp-play{border:1px solid var(--k-border);background:var(--k-surface);color:var(--k-text);border-radius:4px;padding:8px 10px;cursor:pointer;font-family:inherit;display:flex;flex-direction:column;align-items:flex-start;gap:2px;text-align:left;min-width:0}
.kite-pcr .kp-play:hover{background:var(--k-surface-hover)}
.kite-pcr .kp-play[data-on="true"]{border-color:var(--k-orange)}
.kite-pcr .kp-play-name{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--k-dim);font-weight:500}
.kite-pcr .kp-play-pcr{font-size:20px;font-weight:600;font-variant-numeric:tabular-nums;letter-spacing:-.03em;line-height:1.15;color:var(--k-text)}
.kite-pcr .kp-play-act{font-size:12px;font-weight:600;letter-spacing:-.01em}
.kite-pcr .kp-play-act.ce,.kite-pcr .kp-strip-act.ce,.kite-pcr .kp-idea-act.ce,.kite-pcr .kp-all-act.ce{color:var(--k-green)}
.kite-pcr .kp-play-act.pe,.kite-pcr .kp-strip-act.pe,.kite-pcr .kp-idea-act.pe,.kite-pcr .kp-all-act.pe{color:var(--k-red)}
.kite-pcr .kp-play-act.wait,.kite-pcr .kp-strip-act.wait,.kite-pcr .kp-idea-act.wait,.kite-pcr .kp-all-act.wait{color:var(--k-dim);font-weight:500}
.kite-pcr .kp-tabs{display:flex;gap:12px;padding-bottom:8px}
.kite-pcr .kp-tabs button{border:0;background:none;color:var(--k-dim);padding:0 0 6px;font-size:12px;cursor:pointer;font-family:inherit;border-bottom:2px solid transparent}
.kite-pcr .kp-tabs button[data-on="true"]{color:var(--k-orange);border-bottom-color:var(--k-orange);font-weight:500}
.kite-pcr .kp-body{flex:1;padding:10px 16px 16px;overflow:auto}
.kite-pcr .kp-strip{display:grid;grid-template-columns:132px minmax(0,1fr);margin-bottom:10px;border:1px solid var(--k-border);background:var(--k-surface);border-radius:4px;overflow:hidden}
.kite-pcr .kp-strip-hero{padding:14px 16px;border-right:1px solid var(--k-border);display:flex;flex-direction:column;justify-content:center;gap:6px}
.kite-pcr .kp-strip-pcr{font-size:32px;line-height:1;font-weight:600;font-variant-numeric:tabular-nums;letter-spacing:-.04em}
.kite-pcr .kp-strip-read{padding:14px 16px;display:flex;flex-direction:column;justify-content:center}
.kite-pcr .kp-strip-act{font-size:22px;font-weight:600;letter-spacing:-.03em;line-height:1.1}
.kite-pcr .kp-strip-read p{margin:6px 0 0;font-size:13px;color:var(--k-dim);line-height:1.4}
.kite-pcr .kp-strip-stats{grid-column:1/-1;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:0;margin:0;border-top:1px solid var(--k-border)}
.kite-pcr .kp-strip-stats div{padding:10px 12px;border-right:1px solid var(--k-border);min-width:0}
.kite-pcr .kp-strip-stats div:last-child{border-right:0}
.kite-pcr .kp-strip-stats dt{margin:0;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--k-dim)}
.kite-pcr .kp-strip-stats dd{margin:3px 0 0;font-size:13px;font-variant-numeric:tabular-nums;font-weight:500}
.kite-pcr .kp-card{border:1px solid var(--k-border);background:var(--k-surface);border-radius:4px;padding:12px}
.kite-pcr .kp-sub{margin:0;font-size:12px;color:var(--k-dim);line-height:1.45}
.kite-pcr .text-up{color:var(--k-green)}
.kite-pcr .text-down{color:var(--k-red)}
.kite-pcr .kp-main{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(220px,.72fr);gap:10px;align-items:start}
.kite-pcr .kp-sheet{overflow:auto;border:1px solid var(--k-border);border-radius:4px;background:var(--k-surface);padding:4px}
.kite-pcr table{width:100%;border-collapse:separate;border-spacing:2px;font-variant-numeric:tabular-nums}
.kite-pcr thead th{background:transparent;color:var(--k-dim);font-weight:500;font-size:11px;padding:4px 6px;text-align:left;border:0}
.kite-pcr tbody th{padding:4px 6px;font-size:12px;font-weight:400;color:var(--k-dim);text-align:left;background:transparent;border:0}
.kite-pcr tbody td{padding:0}
.kite-pcr tbody tr[data-live="true"] th{color:var(--k-orange);font-weight:600}
.kite-pcr .kp-heat{display:block;text-align:center;font-size:12px;font-weight:500;padding:5px 4px;border-radius:2px;min-height:24px}
.kite-pcr .kp-delta{display:block;text-align:right;padding:5px 6px;font-size:12px;color:var(--k-dim)}
.kite-pcr .kp-band-extreme-positive{background:#1b5e4a;color:#f4f4f5}
.kite-pcr .kp-band-highly-positive{background:#2e7a64;color:#f4f4f5}
.kite-pcr .kp-band-positive{background:#b7d9cf;color:#12332c}
.kite-pcr .kp-band-negative{background:#e4c4c4;color:#3a1818}
.kite-pcr .kp-band-highly-negative{background:#c97a7a;color:#1a0c0c}
.kite-pcr .kp-band-extreme-negative{background:#a33a3a;color:#f4f4f5}
.kite-pcr .kp-band-empty{background:transparent;color:var(--k-dim)}
.kite-pcr .kp-side{display:flex;flex-direction:column;gap:10px}
.kite-pcr .kp-tape-head{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;margin-bottom:6px}
.kite-pcr .kp-idea-sec+.kp-idea-sec{margin-top:14px;padding-top:12px;border-top:1px solid var(--k-border)}
.kite-pcr .kp-idea-sec-lab{margin:0 0 4px;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--k-dim);font-weight:500}
.kite-pcr .kp-idea-act{margin:2px 0;font-size:20px;font-weight:600;letter-spacing:-.03em;line-height:1.1}
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
.kite-pcr .kp-evd-wrap{margin-top:12px;padding-top:10px;border-top:1px solid var(--k-border)}
.kite-pcr .kp-evd{display:grid;grid-template-columns:64px 1fr auto auto;gap:8px;align-items:baseline;padding:6px 0;font-size:12px;font-variant-numeric:tabular-nums}
.kite-pcr .kp-evd-lab{color:var(--k-dim)}
.kite-pcr .kp-evd-st{font-size:11px;color:var(--k-dim)}
.kite-pcr .kp-evd.agrees .kp-evd-st{color:var(--k-green)}
.kite-pcr .kp-evd.fights .kp-evd-st{color:var(--k-red)}
.kite-pcr .kp-all{list-style:none;margin:8px 0 0;padding:0}
.kite-pcr .kp-all-row{display:grid;grid-template-columns:64px 72px 1fr auto;gap:8px;align-items:baseline;width:100%;text-align:left;border:0;background:none;color:inherit;padding:10px 0;border-bottom:1px solid var(--k-border);cursor:pointer;font-family:inherit;font-size:13px;font-variant-numeric:tabular-nums}
.kite-pcr .kp-all-row:hover{background:var(--k-surface-hover)}
.kite-pcr .kp-all-row:last-child{border-bottom:0}
.kite-pcr .kp-all-name{font-weight:500}
.kite-pcr .kp-all-act{font-weight:600;letter-spacing:-.01em}
.kite-pcr .kp-all-path{color:var(--k-text)}
.kite-pcr .kp-all-clock{color:var(--k-dim);font-size:12px}
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
@media (max-width:980px){
  .kite-pcr .kp-strip,.kite-pcr .kp-main{grid-template-columns:1fr}
  .kite-pcr .kp-strip-hero{border-right:0;border-bottom:1px solid var(--k-border)}
  .kite-pcr .kp-strip-stats{grid-template-columns:repeat(2,minmax(0,1fr))}
  .kite-pcr .kp-plays{grid-template-columns:repeat(2,minmax(0,1fr))}
  .kite-pcr .kp-head,.kite-pcr .kp-body{padding-left:10px;padding-right:10px}
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
  const [tapeAll, setTapeAll] = useState(false);

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
      if (e.key === "g" || e.key === "G") setView("grid");
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
  const kindNow = series ? expiryKind(series.expiry, sessionIso || todayIso) : "weekly";
  const ideaName = PCR_INDICES.find((u) => u.id === index)?.short ?? index;
  const book = useMemo(
    () => readBook(
      ideaName,
      metricBoards?.oi[index] ?? [],
      metricBoards?.volume[index] ?? [],
      metricBoards?.changeOi[index] ?? [],
    ),
    [ideaName, metricBoards, index],
  );
  const oiEarlier = useMemo(
    () => buildIdea(ideaName, metricBoards?.oi[index] ?? [], "oi").earlier.filter((e) => e.hhmm !== book.book?.hhmm),
    [ideaName, metricBoards, index, book.book?.hhmm],
  );
  const allBooks = useMemo(() => {
    if (!tapeAll || !metricBoards) return [];
    return PCR_INDICES.map((u) => ({
      id: u.id,
      name: u.short,
      book: readBook(u.short, metricBoards.oi[u.id] ?? [], metricBoards.volume[u.id] ?? [], metricBoards.changeOi[u.id] ?? []),
    }));
  }, [tapeAll, metricBoards]);
  const indexPlays = useMemo(() => {
    return PCR_INDICES.map((u) => {
      const last = lastValidSlot(metricBoards?.oi[u.id] ?? [], "oi");
      const raw = last?.pcr ?? payload?.series[u.id]?.livePcr ?? payload?.series[u.id]?.latest?.pcr ?? null;
      const pcr = isValidPrint(raw, "oi") ? raw : null;
      return { id: u.id, name: u.short, pcr, action: liveAction(pcr) };
    });
  }, [metricBoards, payload]);
  const oiSlots = metricBoards?.oi[index] ?? [];
  const oiLast = lastValidSlot(oiSlots, "oi");
  const oiFilled = oiSlots.filter((s) => isValidPrint(s.pcr, "oi"));
  const oiPrev = oiFilled.length >= 2 ? oiFilled[oiFilled.length - 2] : null;
  const stripPcr = book.book?.to ?? oiLast?.pcr ?? null;
  const stripDelta =
    stripPcr != null && oiPrev?.pcr != null
      ? Math.round((stripPcr - oiPrev.pcr) * 100) / 100
      : (oiLast?.delta ?? null);
  const putPct = putShare(stripPcr);
  const expiryLabel = series
    ? `${kindNow === "today" ? "Today" : kindNow === "weekly" ? "Weekly" : "Monthly"} · ${formatExpiry(series.expiry)}`
    : "—";
  const hasSeries = Boolean(series?.marks?.length || stripPcr != null);
  const stripKind = ideaKind(book.book?.action ?? "Wait");

  return (
    <div className="kite-pcr">
      <style>{CSS}</style>
      <div className="kp-desk">
        <header className="kp-head">
          <div className="kp-head-row">
            <h1 className="kp-title">PCR Desk</h1>
            <div className="kp-tools">
              <div className="kp-seg" role="tablist" aria-label="View">
                <button type="button" role="tab" data-on={view === "grid"} onClick={() => setView("grid")}>Grid</button>
                <button type="button" role="tab" data-on={view === "board"} onClick={() => setView("board")}>All</button>
                <button type="button" role="tab" data-on={view === "path"} onClick={() => setView("path")}>Path</button>
              </div>
            </div>
          </div>
          <div className="kp-plays" role="tablist" aria-label="Underlying">
            {indexPlays.map((row) => (
              <button
                key={row.id}
                type="button"
                role="tab"
                className="kp-play"
                data-on={index === row.id}
                onClick={() => { setIndex(row.id); setView("grid"); }}
              >
                <span className="kp-play-name">{row.name}</span>
                <span className="kp-play-pcr">{row.pcr != null ? formatPcr(row.pcr) : "—"}</span>
                <span className={`kp-play-act ${ideaKind(row.action)}`}>{row.action}</span>
              </button>
            ))}
          </div>
          <div className="kp-tabs" role="tablist" aria-label="PCR metric">
            {([["oi", "OI"], ["volume", "Volume"], ["changeOi", "ΔOI"]] as const).map(([id, label]) => (
              <button key={id} type="button" role="tab" data-on={metric === id} onClick={() => setMetric(id)}>{label}</button>
            ))}
          </div>
        </header>

        <div className="kp-body">
          {error && !payload ? <p className="kp-sub">{error}</p> : null}

          {hasSeries ? (
            <section className="kp-strip">
              <div className="kp-strip-hero">
                <div className={`kp-strip-pcr ${stripKind}`}>{stripPcr != null ? formatPcr(stripPcr) : "—"}</div>
                <p className="kp-kicker">OI PCR</p>
              </div>
              <div className="kp-strip-read">
                <div className={`kp-strip-act ${stripKind}`}>{book.book?.action ?? "Wait"}</div>
                <p>{book.book?.why ?? "Waiting on the OI print."}</p>
              </div>
              <dl className="kp-strip-stats">
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
                  <dt>Δ 15m</dt>
                  <dd className={(stripDelta ?? 0) > 0 ? "text-up" : (stripDelta ?? 0) < 0 ? "text-down" : ""}>{formatDelta(stripDelta)}</dd>
                </div>
                <div>
                  <dt>Puts / Calls</dt>
                  <dd>{putPct == null ? "—" : `${Math.round(putPct * 100)} / ${100 - Math.round(putPct * 100)}`}</dd>
                </div>
                <div>
                  <dt>Expiry</dt>
                  <dd>{expiryLabel}</dd>
                </div>
                <div>
                  <dt>Max pain</dt>
                  <dd>{fmtLtp(series?.spot.maxPain)}</dd>
                </div>
              </dl>
            </section>
          ) : (
            <p className="kp-sub">{payload ? "No F&O prints yet this session." : "Loading put-call prints…"}</p>
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
                        <th>Time</th>
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
                  <BookPanel
                    book={book}
                    earlier={oiEarlier}
                    tapeAll={tapeAll}
                    allRows={allBooks}
                    onPick={(id) => { setIndex(id); setMetric("oi"); setTapeAll(false); setView("grid"); }}
                  />
                </aside>
              </div>
            </div>
          )}

          <p className="kp-foot">OI PCR ≤ 0.80 Buy PE · ≥ 1.20 Buy CE · else Wait. 1–5 index · G grid · A all · P path</p>
        </div>
      </div>
    </div>
  );
}
