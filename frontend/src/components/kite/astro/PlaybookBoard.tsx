import { useEffect, useMemo, useState } from "react";
import { clockFromMinutes, getIstParts, minutesOfDay } from "../../../lib/astro/time";
import type { DayForecast, DignityKind, WindowSlot } from "../../../lib/astro/types";
import { actionTone } from "./palette";

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
  const rows: { from: string; to: string; fromMin: number; toMin: number; slot: WindowSlot }[] = [];
  const sorted = [...slots].sort((a, b) => a.fromMin - b.fromMin);
  for (const s of sorted) {
    const last = rows[rows.length - 1];
    if (last && s.fromMin <= last.toMin) {
      last.toMin = Math.max(last.toMin, s.toMin);
      last.to = clockFromMinutes(last.toMin);
    } else {
      rows.push({ from: s.from, to: s.to, fromMin: s.fromMin, toMin: s.toMin, slot: s });
    }
  }
  return rows;
}

function windowState(fromMin: number, toMin: number, nowMin: number | null): "done" | "now" | "soon" | "next" | null {
  if (nowMin == null) return null;
  if (nowMin < fromMin) return fromMin - nowMin <= 15 ? "soon" : "next";
  if (nowMin <= toMin) return "now";
  return "done";
}

const pinged = new Set<string>();

function fireNotify(tag: string, title: string, body: string) {
  if (pinged.has(tag)) return;
  pinged.add(tag);
  if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
  try {
    new Notification(title, { body, tag });
  } catch {
    /* ignore */
  }
}

type Role = {
  id: string;
  label: string;
  slot: WindowSlot;
  from: string;
  to: string;
  fromMin: number;
  toMin: number;
  state: "done" | "now" | "soon" | "next" | null;
};

export function PlaybookStrip({
  book,
  onPick,
  nowMin,
}: {
  book: DayForecast;
  onPick?: (slot: WindowSlot) => void;
  nowMin?: number | null;
}) {
  const pb = book.playbook;
  const avoid = mergeWindows(pb.avoid)[0] ?? null;
  const roles = useMemo(() => {
    const list: { id: string; label: string; slot: WindowSlot | null }[] = [
      { id: "ce", label: "CE", slot: pb.bestCe },
      { id: "pe", label: "PE", slot: pb.bestPe },
      { id: "avoid", label: "Avoid", slot: avoid?.slot ?? null },
    ];
    const out: Role[] = [];
    for (const row of list) {
      const slot = row.slot;
      if (!slot) continue;
      const fromMin = row.id === "avoid" && avoid ? avoid.fromMin : slot.fromMin;
      const toMin = row.id === "avoid" && avoid ? avoid.toMin : slot.toMin;
      const from = row.id === "avoid" && avoid ? avoid.from : slot.from;
      const to = row.id === "avoid" && avoid ? avoid.to : slot.to;
      out.push({
        id: row.id,
        label: row.label,
        slot,
        from,
        to,
        fromMin,
        toMin,
        state: windowState(fromMin, toMin, nowMin ?? null),
      });
    }
    return out;
  }, [pb.bestCe, pb.bestPe, avoid, nowMin]);

  const active = roles.filter((r) => r.state === "now" || r.state === "soon");
  const [perm, setPerm] = useState<NotificationPermission | "unsupported">("default");

  useEffect(() => {
    if (typeof Notification === "undefined") {
      setPerm("unsupported");
      return;
    }
    setPerm(Notification.permission);
  }, []);

  useEffect(() => {
    for (const r of active) {
      if (!r.slot || (r.state !== "now" && r.state !== "soon")) continue;
      const when = r.state === "now" ? "now" : "soon";
      fireNotify(
        `${book.date}-${r.id}-${when}`,
        `${r.label} window ${when}`,
        `${r.slot.action} · ${r.from}–${r.to}`,
      );
    }
  }, [active, book.date]);

  const ask = () => {
    if (typeof Notification === "undefined") return;
    void Notification.requestPermission().then((p) => {
      setPerm(p);
      if (p === "granted") {
        for (const r of active) {
          if (!r.slot) continue;
          fireNotify(
            `${book.date}-${r.id}-${r.state}`,
            `${r.label} ${r.state === "now" ? "now" : "soon"}`,
            `${r.slot.action} · ${r.from}–${r.to}`,
          );
        }
      }
    });
  };

  if (roles.length === 0 && perm !== "default") return null;

  return (
    <div className="ko-alerts" aria-live="polite">
      {active.length
        ? active.map((r) => {
            const mins = Math.max(1, r.fromMin - (nowMin ?? 0));
            return (
              <button
                key={r.id}
                type="button"
                className="ko-alert"
                data-kind={r.state ?? undefined}
                onClick={() => r.slot && onPick?.(r.slot)}
              >
                <span className="ko-alert-kicker">
                  {r.state === "now" ? `${r.label} now` : `${r.label} in ${mins}m`}
                </span>
                <span className="ko-alert-body">
                  <b className={r.slot ? actionTone(r.slot.action, r.slot.side) : ""}>{r.slot?.action}</b>
                  <span className="text-muted">
                    {" "}
                    {r.from}–{r.to}
                  </span>
                </span>
              </button>
            );
          })
        : roles.map((r) => (
            <button
              key={r.id}
              type="button"
              className="ko-plan"
              data-state={r.state ?? undefined}
              onClick={() => r.slot && onPick?.(r.slot)}
            >
              <span className="ko-plan-kicker">{r.label}</span>
              {r.id === "avoid" ? null : (
                <span className={`ko-plan-play ${actionTone(r.slot.action, r.slot.side)}`}>{r.slot.action}</span>
              )}
              <span className="text-muted">
                {r.from}–{r.to}
              </span>
            </button>
          ))}
      {perm === "default" ? (
        <button type="button" className="ko-link ko-alert-enable" onClick={ask}>
          Notify me
        </button>
      ) : null}
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
