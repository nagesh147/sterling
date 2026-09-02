import { HEAD_METRICS, ROW_METRICS } from "../board/signalRowSpec";
import { fetchPcrDesk, sessionIsoOf } from "../../lib/pcr/fetchPcr";
import {
  SESSION_CLOSE_MIN,
  SESSION_OPEN_MIN,
  buildGrid,
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
.kite-pcr .kp-card{border:1px solid var(--k-border);background:var(--k-surface);border-radius:4px;padding:12px}
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
.kite-pcr .kp-sheet-heat{max-height:calc(100vh - 280px)}
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
.kite-pcr .kp-heat-row td{padding:2px;text-align:center}
.kite-pcr .kp-heat-row th{padding:4px 10px;font-variant-numeric:tabular-nums}
.kite-pcr .kp-heat{display:block;width:100%;text-align:center;font-size:12px;font-weight:500;padding:6px 4px;border-radius:2px;min-height:26px;box-sizing:border-box}
.kite-pcr .kp-delta{display:block;text-align:right;padding:5px 6px;font-size:12px;color:var(--k-dim)}
.kite-pcr .kp-band-extreme-positive{background:#1b5e4a;color:#f4f4f5}
.kite-pcr .kp-band-highly-positive{background:#2e7a64;color:#f4f4f5}
.kite-pcr .kp-band-positive{background:#b7d9cf;color:#12332c}
.kite-pcr .kp-band-negative{background:#e4c4c4;color:#3a1818}
.kite-pcr .kp-band-highly-negative{background:#c97a7a;color:#1a0c0c}
.kite-pcr .kp-band-extreme-negative{background:#a33a3a;color:#f4f4f5}
.kite-pcr .kp-band-empty{background:transparent;color:var(--k-dim)}
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
  .kite-pcr .kp-head,.kite-pcr .kp-body{padding-left:10px;padding-right:10px}
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
        maxPain: row?.spot.maxPain ?? null,
      };
    });
  }, [metricBoards, payload, sessionIso, todayIso]);
  const showAll = view === "board";
  const cols = showAll ? PCR_INDICES : PCR_INDICES.filter((u) => u.id === index);
  const sumRows = showAll ? deskRows : deskRows.filter((r) => r.id === index);
  const heatSlots = showAll ? axis : grid;

  return (
    <div className="kite-pcr">
      <style>{CSS}</style>
      <div className="kp-desk">
        <header className="kp-head">
          <div className="kp-head-row">
            <h1 className="kp-title">PCR Desk</h1>
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
              <div className="kp-sheet">
                <table className="kp-book">
                  <colgroup>
                    <col className="c-idx" />
                    <col className="c-play" />
                    <col className="c-pcr" />
                    <col className="c-move" />
                    <col className="c-st" />
                    <col className="c-st" />
                    <col className="c-spot" />
                    <col className="c-pc" />
                    <col className="c-exp" />
                    <col className="c-pain" />
                  </colgroup>
                  <thead>
                    <tr>
                      <th>Index</th>
                      <th>Play</th>
                      <th className="num">OI PCR</th>
                      <th className="num">Move</th>
                      <th className="mid">Vol</th>
                      <th className="mid">ΔOI</th>
                      <th className="num">Spot</th>
                      <th className="mid">P/C</th>
                      <th>Expiry</th>
                      <th className="num">Pain</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sumRows.map((row) => {
                      const kind = ideaKind(row.action);
                      return (
                        <tr key={row.id}>
                          <th>{row.name}</th>
                          <td className="kp-play-cell">
                            <span className={`kp-play kp-act ${kind}`}>{row.action}</span>
                            <span className="kp-tip">{playHint(row.action)}</span>
                          </td>
                          <td className={`kp-pcr kp-act ${kind} num`}>{row.pcr != null ? formatPcr(row.pcr) : "—"}</td>
                          <td className="kp-move num">
                            {row.path}
                            {row.move != null ? (
                              <span className={(row.move ?? 0) > 0 ? "text-up" : (row.move ?? 0) < 0 ? "text-down" : ""}>
                                {" "}{moveTxt(row.move)}
                              </span>
                            ) : null}
                          </td>
                          <td className={`kp-st ${row.vol} mid`}>{stanceLab(row.vol)}</td>
                          <td className={`kp-st ${row.doi} mid`}>{stanceLab(row.doi)}</td>
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
                          <td className="mid">{row.putPct == null ? "—" : `${Math.round(row.putPct * 100)}/${100 - Math.round(row.putPct * 100)}`}</td>
                          <td>{row.expiry}</td>
                          <td className="num">{fmtLtp(row.maxPain)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="kp-sheet kp-sheet-heat">
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
            </div>
          ) : (
            <p className="kp-sub">{payload ? "No F&O prints yet this session." : "Loading put-call prints…"}</p>
          )}

          <p className="kp-foot">All five, or one index. Path is PCR vs spot. 1–5 index · A all · P path</p>
        </div>
      </div>
    </div>
  );
}
