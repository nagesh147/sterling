import type { MonthProjection } from "../../../lib/astro/types";

const DOW = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
const DOW_FULL = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export function MonthHeat({
  month,
  iso,
  onPick,
}: {
  month: MonthProjection;
  iso: string;
  onPick: (date: string) => void;
}) {
  const first = month.days[0];
  const pad = first ? Math.max(0, DOW_FULL.indexOf(first.weekday)) : 0;
  const cells: Array<(typeof month.days)[number] | null> = [...Array(pad).fill(null), ...month.days];
  while (cells.length % 7 !== 0) cells.push(null);

  return (
    <div>
      <p className="ko-sub">{month.summary}</p>
      <div className="ko-cal" role="grid" aria-label={`${month.label} gap map`}>
        {DOW.map((d) => (
          <div key={d} className="ko-cal-hd">
            {d}
          </div>
        ))}
        {cells.map((day, i) => {
          if (!day) {
            return <div key={`e-${i}`} className="ko-cal-cell ko-cal-empty" />;
          }
          const closed = day.isWeekend || day.isHoliday;
          const gap = closed ? "closed" : (day.gap ?? "flat");
          return (
            <button
              key={day.date}
              type="button"
              className="ko-cal-cell"
              data-gap={gap}
              data-on={day.date === iso}
              disabled={closed}
              title={closed ? (day.holidayName || day.note || "Closed") : `${day.gapLabel} · ${day.openAction} · ${day.note}`}
              onClick={() => onPick(day.date)}
            >
              <span className="n">
                {Number(day.date.slice(-2))}
                {day.isToday ? <span className="ko-tag">TODAY</span> : null}
              </span>
              <span className="bar" />
            </button>
          );
        })}
      </div>
      <div className="ko-strip-leg" style={{ marginTop: 0, marginBottom: 16 }}>
        <span>
          <i className="ko-swatch-ce" />
          Gap up {month.gapUp}
        </span>
        <span>
          <i className="ko-swatch-both" />
          Flat {month.gapFlat}
        </span>
        <span>
          <i className="ko-swatch-pe" />
          Gap down {month.gapDown}
        </span>
        <span className="text-muted">
          {month.tradingDays} sessions · {month.bullishDays} bullish · {month.bearishDays} bearish
        </span>
      </div>
    </div>
  );
}
