import { useEffect, useMemo, useState } from "react";
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
  return "quiet";
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
.kite-pcr .kp-tabs{display:flex;gap:12px;padding-bottom:8px}
.kite-pcr .kp-tabs button{border:0;background:none;color:var(--k-dim);padding:0 0 6px;font-size:12px;cursor:pointer;font-family:inherit;border-bottom:2px solid transparent}
.kite-pcr .kp-tabs button[data-on="true"]{color:var(--k-orange);border-bottom-color:var(--k-orange);font-weight:500}
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
.kite-pcr .kp-sheet{overflow:auto;border:1px solid var(--k-border);border-radius:4px;background:var(--k-surface);max-height:calc(100vh - 160px)}
.kite-pcr table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
.kite-pcr thead th{position:sticky;top:0;z-index:2;background:var(--k-surface);color:var(--k-dim);font-weight:500;font-size:11px;letter-spacing:.06em;text-transform:uppercase;padding:8px 8px;text-align:center;border-bottom:1px solid var(--k-border);white-space:nowrap;cursor:pointer}
.kite-pcr thead th:first-child{text-align:left;cursor:default;position:sticky;left:0;z-index:3}
.kite-pcr thead th[data-on="true"]{color:var(--k-orange);font-weight:600}
.kite-pcr tbody th{position:sticky;left:0;z-index:1;padding:8px 10px;font-size:12px;font-weight:400;color:var(--k-dim);text-align:left;background:var(--k-surface);border-bottom:1px solid var(--k-border);white-space:nowrap}
.kite-pcr tbody td{padding:8px;font-size:13px;border-bottom:1px solid var(--k-border);vertical-align:top;text-align:center}
.kite-pcr tbody tr[data-live="true"] th{color:var(--k-orange);font-weight:600}
.kite-pcr .kp-sum td{padding:8px 8px}
.kite-pcr .kp-pcr{font-size:16px;font-weight:600;letter-spacing:-.02em}
.kite-pcr .kp-play{font-weight:600;letter-spacing:-.02em;white-space:nowrap}
.kite-pcr .kp-why{display:block;margin-top:2px;font-size:11px;font-weight:400;color:var(--k-dim);line-height:1.35}
.kite-pcr .kp-move{white-space:nowrap;font-size:12px}
.kite-pcr .kp-heat-row td{padding:2px}
.kite-pcr .kp-heat-row th{padding:4px 10px;font-variant-numeric:tabular-nums}
.kite-pcr .kp-heat{display:block;text-align:center;font-size:12px;font-weight:500;padding:5px 4px;border-radius:2px;min-height:24px}
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
      if (pick) setIndex(pick);
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
        ? `${kind === "today" ? "Today" : kind === "weekly" ? "Weekly" : "Monthly"} · ${formatExpiry(row.expiry)}`
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

  return (
    <div className="kite-pcr">
      <style>{CSS}</style>
      <div className="kp-desk">
        <header className="kp-head">
          <div className="kp-head-row">
            <h1 className="kp-title">PCR Desk</h1>
            <div className="kp-tools">
              <div className="kp-seg" role="tablist" aria-label="View">
                <button type="button" role="tab" data-on={view === "board"} onClick={() => setView("board")}>All</button>
                <button type="button" role="tab" data-on={view === "grid"} onClick={() => setView("grid")}>Grid</button>
                <button type="button" role="tab" data-on={view === "path"} onClick={() => setView("path")}>Path</button>
              </div>
            </div>
          </div>
          <div className="kp-tabs" role="tablist" aria-label="PCR metric">
            {([["oi", "OI"], ["volume", "Volume"], ["changeOi", "ΔOI"]] as const).map(([id, label]) => (
              <button key={id} type="button" role="tab" data-on={metric === id} onClick={() => setMetric(id)}>{label}</button>
            ))}
          </div>
        </header>

        <div className="kp-body">
          {error && !payload ? <p className="kp-sub">{error}</p> : null}

          {view === "path" && series ? (
            <Path slots={grid} marks={series.marks} />
          ) : view === "grid" ? (
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
          ) : deskRows.length ? (
            <div className="kp-sheet">
              <table>
                <thead>
                  <tr>
                    <th> </th>
                    {PCR_INDICES.map((u) => (
                      <th
                        key={u.id}
                        data-on={index === u.id}
                        onClick={() => setIndex(u.id)}
                      >
                        {u.short}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr className="kp-sum">
                    <th>Play</th>
                    {deskRows.map((row) => {
                      const kind = ideaKind(row.action);
                      return (
                        <td key={row.id} onClick={() => setIndex(row.id)}>
                          <span className={`kp-play kp-act ${kind}`}>{row.action}</span>
                          <span className="kp-why">{row.why}</span>
                        </td>
                      );
                    })}
                  </tr>
                  <tr className="kp-sum">
                    <th>OI PCR</th>
                    {deskRows.map((row) => (
                      <td key={row.id} className={`kp-pcr kp-act ${ideaKind(row.action)}`} onClick={() => setIndex(row.id)}>
                        {row.pcr != null ? formatPcr(row.pcr) : "—"}
                      </td>
                    ))}
                  </tr>
                  <tr className="kp-sum">
                    <th>Move</th>
                    {deskRows.map((row) => (
                      <td key={row.id} className="kp-move" onClick={() => setIndex(row.id)}>
                        {row.path}
                        {row.move != null ? (
                          <span className={(row.move ?? 0) > 0 ? "text-up" : (row.move ?? 0) < 0 ? "text-down" : ""}>
                            {" "}{moveTxt(row.move)}
                          </span>
                        ) : null}
                      </td>
                    ))}
                  </tr>
                  <tr className="kp-sum">
                    <th>Vol</th>
                    {deskRows.map((row) => (
                      <td key={row.id} className={`kp-st ${row.vol}`} onClick={() => setIndex(row.id)}>{stanceLab(row.vol)}</td>
                    ))}
                  </tr>
                  <tr className="kp-sum">
                    <th>ΔOI</th>
                    {deskRows.map((row) => (
                      <td key={row.id} className={`kp-st ${row.doi}`} onClick={() => setIndex(row.id)}>{stanceLab(row.doi)}</td>
                    ))}
                  </tr>
                  <tr className="kp-sum">
                    <th>Spot</th>
                    {deskRows.map((row) => (
                      <td key={row.id} onClick={() => setIndex(row.id)}>
                        {fmtLtp(row.spot)}
                        {row.spotChg != null ? (
                          <span className={row.spotChg >= 0 ? "text-up" : "text-down"}>
                            {" "}{row.spotChg >= 0 ? "+" : ""}{row.spotChg.toFixed(2)}%
                          </span>
                        ) : null}
                      </td>
                    ))}
                  </tr>
                  <tr className="kp-sum">
                    <th>Δ 15m</th>
                    {deskRows.map((row) => (
                      <td key={row.id} className={(row.delta ?? 0) > 0 ? "text-up" : (row.delta ?? 0) < 0 ? "text-down" : ""} onClick={() => setIndex(row.id)}>
                        {formatDelta(row.delta)}
                      </td>
                    ))}
                  </tr>
                  <tr className="kp-sum">
                    <th>Puts / Calls</th>
                    {deskRows.map((row) => (
                      <td key={row.id} onClick={() => setIndex(row.id)}>
                        {row.putPct == null ? "—" : `${Math.round(row.putPct * 100)} / ${100 - Math.round(row.putPct * 100)}`}
                      </td>
                    ))}
                  </tr>
                  <tr className="kp-sum">
                    <th>Expiry</th>
                    {deskRows.map((row) => (
                      <td key={row.id} onClick={() => setIndex(row.id)}>{row.expiry}</td>
                    ))}
                  </tr>
                  <tr className="kp-sum">
                    <th>Max pain</th>
                    {deskRows.map((row) => (
                      <td key={row.id} onClick={() => setIndex(row.id)}>{fmtLtp(row.maxPain)}</td>
                    ))}
                  </tr>
                  {axis.map((slot, row) => (
                    <tr key={slot.hhmm} className="kp-heat-row" data-live={slot.live}>
                      <th>{slot.hhmm}</th>
                      {PCR_INDICES.map((u) => {
                        const s = boards?.[u.id]?.[row];
                        return (
                          <td key={u.id} onClick={() => setIndex(u.id)}>
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
          ) : (
            <p className="kp-sub">{payload ? "No F&O prints yet this session." : "Loading put-call prints…"}</p>
          )}

          <p className="kp-foot">Play is OI PCR. Heat below is the 15-minute table. 1–5 index · A all · G grid · P path</p>
        </div>
      </div>
    </div>
  );
}
