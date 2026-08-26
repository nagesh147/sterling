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
  const rows: { from: string; to: string; fromMin: number; toMin: number; action: WindowSlot["action"]; side: WindowSlot["side"]; why: string }[] = [];
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

export function PlaybookBoard({ book }: { book: DayForecast }) {
  const pb = book.playbook;
  const gtone = gapTone(book.gap.kind);
  const pan = book.panchang;
  const avoid = mergeWindows(pb.avoid).slice(0, 6);
  const plays: { role: string; slot: WindowSlot | null; note: string }[] = [
    { role: "Best CE", slot: pb.bestCe, note: pb.bestCe ? pb.bestCe.suggestion : "No CE window on the 30-min grid." },
    { role: "Best PE", slot: pb.bestPe, note: pb.bestPe ? pb.bestPe.suggestion : "No PE window on the 30-min grid." },
  ];

  return (
    <div className="ko-book">
      <p className="ko-sub">{pb.headline}</p>

      <div className="ko-kv">
        <div>
          <span className="lbl">Gap</span>
          <b className={gtone.fg}>{book.gap.label}</b>
        </div>
        <div>
          <span className="lbl">Thesis</span>
          <b>{THESIS[pb.thesis]}</b>
        </div>
        <div>
          <span className="lbl">Open</span>
          <b className={actionTone(book.gap.openAction, book.gap.openAction.includes("CE") ? "CE" : book.gap.openAction.includes("PE") ? "PE" : "WAIT")}>
            {book.gap.openAction}
          </b>
        </div>
        <div>
          <span className="lbl">Hora at bell</span>
          <b>{pb.horaAtOpen}</b>
        </div>
        <div>
          <span className="lbl">Close bias</span>
          <b>{REGIME_SHORT[pb.closeBias]}</b>
        </div>
        <div>
          <span className="lbl">Vol</span>
          <b>{book.gap.volatility}</b>
        </div>
        <div>
          <span className="lbl">Confidence</span>
          <b>{book.gap.confidence}%</b>
        </div>
        <div>
          <span className="lbl">Bias</span>
          <b>{book.gap.bias}</b>
        </div>
      </div>

      <p className="ko-copy">{book.gap.summary}</p>
      {book.gap.thesisNote ? <p className="ko-copy">{book.gap.thesisNote}</p> : null}
      {book.gap.sectorNote ? <p className="ko-copy text-muted">{book.gap.sectorNote}</p> : null}
      {book.gap.firstHourNote ? <p className="ko-copy">{book.gap.firstHourNote}</p> : null}

      <h3 className="ko-sec">Day’s playbook</h3>
      <div className="ko-scroll">
        <table className="ko-table">
          <thead>
            <tr>
              <th>Role</th>
              <th>Time</th>
              <th>Type</th>
              <th>Play</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {plays.map((row) => (
              <tr key={row.role} style={{ cursor: "default" }}>
                <td>{row.role}</td>
                <td>{row.slot ? `${row.slot.from} – ${row.slot.to}` : "—"}</td>
                <td>{row.slot ? <span className={sideClass(row.slot.side)}>{row.slot.side}</span> : "—"}</td>
                <td className={row.slot ? actionTone(row.slot.action, row.slot.side) : "text-muted"}>
                  {row.slot ? row.slot.action : "—"}
                </td>
                <td className="text-muted">{row.note}</td>
              </tr>
            ))}
            {avoid.map((row) => (
              <tr key={`avoid-${row.fromMin}`} style={{ cursor: "default" }}>
                <td>Avoid</td>
                <td>
                  {row.from} – {row.to}
                </td>
                <td>
                  <span className={sideClass(row.side)}>{row.side}</span>
                </td>
                <td className="text-muted">{row.action}</td>
                <td className="text-muted">{row.why}</td>
              </tr>
            ))}
            {!avoid.length ? (
              <tr style={{ cursor: "default" }}>
                <td>Avoid</td>
                <td>—</td>
                <td>—</td>
                <td className="text-muted">—</td>
                <td className="text-muted">No Rahu / AVOID block on the 30-min grid.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {(book.gap.yogas.length > 0 || book.gap.eclipse || book.gap.gandanta) && (
        <p className="ko-sub" style={{ marginTop: 12 }}>
          {book.gap.eclipse ? "Eclipse corridor · " : ""}
          {book.gap.gandanta ? "Gandanta · " : ""}
          {book.gap.yogas.length ? `Yogas: ${book.gap.yogas.join(", ")}` : null}
        </p>
      )}

      <h3 className="ko-sec">Notes</h3>
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
