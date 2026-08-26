import { clockFromMinutes, getIstParts, minutesOfDay } from "../../../lib/astro/time";
import type { DayForecast, DignityKind, WindowSlot } from "../../../lib/astro/types";
import { actionTone, gapTone, REGIME_SHORT } from "./palette";

const THESIS: Record<DayForecast["playbook"]["thesis"], string> = {
  "trend-up": "Trend up",
  "trend-down": "Trend down",
  fade: "Fade",
  chop: "Chop",
};

function istClock(iso: string): string {
  const p = getIstParts(new Date(iso));
  return clockFromMinutes(minutesOfDay(p.hour, p.minute));
}

function dignityClass(d: DignityKind): string {
  if (d === "exalted") return "text-up";
  if (d === "debilitated") return "text-down";
  return "";
}

function mergeWindows(slots: WindowSlot[]) {
  const rows: { from: string; to: string; fromMin: number; toMin: number; action: WindowSlot["action"]; side: WindowSlot["side"]; why: string; slot: WindowSlot }[] = [];
  const sorted = [...slots].sort((a, b) => a.fromMin - b.fromMin);
  for (const s of sorted) {
    const last = rows[rows.length - 1];
    if (last && s.fromMin <= last.toMin) {
      last.toMin = Math.max(last.toMin, s.toMin);
      last.to = clockFromMinutes(last.toMin);
    } else {
      rows.push({
        from: s.from,
        to: s.to,
        fromMin: s.fromMin,
        toMin: s.toMin,
        action: s.action,
        side: s.side,
        why: s.why,
        slot: s,
      });
    }
  }
  return rows;
}

function sideClass(side: WindowSlot["side"]): string {
  if (side === "CE") return "ko-pill ko-pill-ce";
  if (side === "PE") return "ko-pill ko-pill-pe";
  return "ko-pill ko-pill-wait";
}

function openSide(action: string): WindowSlot["side"] {
  if (action.includes("CE")) return "CE";
  if (action.includes("PE")) return "PE";
  return "WAIT";
}

export function PlaybookStrip({
  book,
  onPick,
}: {
  book: DayForecast;
  onPick?: (slot: WindowSlot) => void;
}) {
  const pb = book.playbook;
  const gtone = gapTone(book.gap.kind);
  const avoid = mergeWindows(pb.avoid)[0] ?? null;

  return (
    <div className="ko-play">
      <p className="ko-play-head">{pb.headline}</p>
      <div className="ko-play-meta">
        <span>
          <span className="lbl">Gap</span>
          <b className={gtone.fg}>{book.gap.label}</b>
        </span>
        <span>
          <span className="lbl">Thesis</span>
          <b>{THESIS[pb.thesis]}</b>
        </span>
        <span>
          <span className="lbl">Open</span>
          <b className={actionTone(book.gap.openAction, openSide(book.gap.openAction))}>{book.gap.openAction}</b>
        </span>
        <span>
          <span className="lbl">Hora</span>
          <b>{pb.horaAtOpen}</b>
        </span>
        <span>
          <span className="lbl">Close</span>
          <b>{REGIME_SHORT[pb.closeBias]}</b>
        </span>
        <span>
          <span className="lbl">Conf</span>
          <b>{book.gap.confidence}%</b>
        </span>
      </div>
      <div className="ko-play-roles">
        <button type="button" disabled={!pb.bestCe} onClick={() => pb.bestCe && onPick?.(pb.bestCe)}>
          <span className="lbl">Best CE</span>
          {pb.bestCe ? (
            <>
              <span className={sideClass(pb.bestCe.side)}>CE</span>
              {pb.bestCe.from}–{pb.bestCe.to}{" "}
              <b className={actionTone(pb.bestCe.action, pb.bestCe.side)}>{pb.bestCe.action}</b>
            </>
          ) : (
            <span className="text-muted">No CE window</span>
          )}
        </button>
        <button type="button" disabled={!pb.bestPe} onClick={() => pb.bestPe && onPick?.(pb.bestPe)}>
          <span className="lbl">Best PE</span>
          {pb.bestPe ? (
            <>
              <span className={sideClass(pb.bestPe.side)}>PE</span>
              {pb.bestPe.from}–{pb.bestPe.to}{" "}
              <b className={actionTone(pb.bestPe.action, pb.bestPe.side)}>{pb.bestPe.action}</b>
            </>
          ) : (
            <span className="text-muted">No PE window</span>
          )}
        </button>
        <button type="button" disabled={!avoid} onClick={() => avoid && onPick?.(avoid.slot)}>
          <span className="lbl">Avoid</span>
          {avoid ? (
            <>
              <span className={sideClass(avoid.side)}>{avoid.side}</span>
              {avoid.from}–{avoid.to} <span className="text-muted">{avoid.action}</span>
            </>
          ) : (
            <span className="text-muted">No Rahu / AVOID block</span>
          )}
        </button>
      </div>
    </div>
  );
}

export function PlaybookNotes({ book }: { book: DayForecast }) {
  const pan = book.panchang;
  return (
    <div className="ko-book">
      <p className="ko-copy">{book.gap.summary}</p>
      {book.gap.thesisNote ? <p className="ko-copy">{book.gap.thesisNote}</p> : null}
      {book.gap.sectorNote ? <p className="ko-copy text-muted">{book.gap.sectorNote}</p> : null}
      {book.gap.firstHourNote ? <p className="ko-copy">{book.gap.firstHourNote}</p> : null}

      {(book.gap.yogas.length > 0 || book.gap.eclipse || book.gap.gandanta) && (
        <p className="ko-sub">
          {book.gap.eclipse ? "Eclipse corridor · " : ""}
          {book.gap.gandanta ? "Gandanta · " : ""}
          {book.gap.yogas.length ? `Yogas: ${book.gap.yogas.join(", ")}` : null}
        </p>
      )}

      <ul className="ko-notes">
        {book.gap.reasons.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>

      <div className="ko-split">
        <div>
          <h3 className="ko-sec">Panchang</h3>
          <table className="ko-table ko-table-kv">
            <tbody>
              <tr>
                <td className="text-muted">Weekday</td>
                <td>
                  {pan.weekday} · {pan.nakshatraLord} rules the star
                </td>
              </tr>
              <tr>
                <td className="text-muted">Tithi</td>
                <td>
                  {pan.tithiName} {pan.paksha}
                </td>
              </tr>
              <tr>
                <td className="text-muted">Nakshatra</td>
                <td>
                  {pan.nakshatra} pada {pan.nakshatraPada}
                </td>
              </tr>
              <tr>
                <td className="text-muted">Yoga / Karana</td>
                <td>
                  {pan.yoga} · {pan.karana}
                </td>
              </tr>
              <tr>
                <td className="text-muted">Moon / Sun</td>
                <td>
                  {pan.moonSign} / {pan.sunSign}
                </td>
              </tr>
              <tr>
                <td className="text-muted">Lagna</td>
                <td>
                  {pan.lagnaSign} {pan.lagnaDegree.toFixed(1)}°
                </td>
              </tr>
              <tr>
                <td className="text-muted">Sunrise / set</td>
                <td>
                  {istClock(pan.sunriseIso)} / {istClock(pan.sunsetIso)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div>
          <h3 className="ko-sec">Planets</h3>
          <div className="ko-scroll">
            <table className="ko-table">
              <thead>
                <tr>
                  <th>Planet</th>
                  <th>Sign</th>
                  <th>Deg</th>
                  <th>Dignity</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {book.planets.map((p) => {
                  const d = book.dignities.find((x) => x.name === p.name);
                  return (
                    <tr key={p.name} style={{ cursor: "default" }}>
                      <td>{p.name}</td>
                      <td>{p.sign}</td>
                      <td>{p.degreeInSign.toFixed(1)}°</td>
                      <td className={d ? dignityClass(d.dignity) : ""}>{d?.dignity ?? "—"}</td>
                      <td className="text-muted">{p.retrograde ? "Rx" : ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <h3 className="ko-sec">Aspects</h3>
      <div className="ko-scroll">
        <table className="ko-table">
          <thead>
            <tr>
              <th>A</th>
              <th>Aspect</th>
              <th>B</th>
              <th>Orb</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {book.aspects.length ? (
              book.aspects.map((a) => (
                <tr key={`${a.a}-${a.kind}-${a.b}`} style={{ cursor: "default" }}>
                  <td>{a.a}</td>
                  <td>{a.kind}</td>
                  <td>{a.b}</td>
                  <td>{a.orb.toFixed(1)}°</td>
                  <td className="text-muted">{a.note}</td>
                </tr>
              ))
            ) : (
              <tr style={{ cursor: "default" }}>
                <td colSpan={5} className="text-muted">
                  No tight aspects inside orb.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function PlaybookBoard({ book, onPick }: { book: DayForecast; onPick?: (slot: WindowSlot) => void }) {
  return (
    <>
      <PlaybookStrip book={book} onPick={onPick} />
      <PlaybookNotes book={book} />
    </>
  );
}
