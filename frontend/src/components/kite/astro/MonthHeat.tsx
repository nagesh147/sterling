import type { MonthDay, MonthProjection, TradeAction } from "../../../lib/astro/types";

const DOW = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
const DOW_FULL = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

function cellSide(action: TradeAction | null): { mark: string; tone: string } | null {
  if (!action) return null;
  if (action.includes("CE") && action.includes("PE")) return { mark: "±", tone: "text-warn" };
  if (action.includes("CE")) return { mark: "CE", tone: "text-ce" };
  if (action.includes("PE")) return { mark: "PE", tone: "text-pe" };
  if (action === "WAIT" || action === "AVOID") return { mark: "W", tone: "text-muted" };
  return null;
}

function titleFor(day: MonthDay): string {
  if (day.isWeekend || day.isHoliday) return day.holidayName || day.note || "Closed";
  const bits = [day.gapLabel, day.openAction, day.bias].filter(Boolean);
  return bits.join(" · ");
}

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
  const cells: Array<MonthDay | null> = [...Array(pad).fill(null), ...month.days];
  while (cells.length % 7 !== 0) cells.push(null);

  return (
    <div className="ko-month">
      <div className="ko-cal" role="grid" aria-label={`${month.label} calendar`}>
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
          const side = closed ? null : cellSide(day.openAction);
          return (
            <button
              key={day.date}
              type="button"
              className="ko-cal-cell"
              data-gap={gap}
              data-on={day.date === iso}
              data-today={day.isToday}
              disabled={closed}
              title={titleFor(day)}
              aria-current={day.date === iso ? "date" : undefined}
              onClick={() => onPick(day.date)}
            >
              <span className="ko-cal-top">
                <span className="n">{Number(day.date.slice(-2))}</span>
                {side ? <span className={`ko-cal-act ${side.tone}`}>{side.mark}</span> : null}
              </span>
              <span className="bar" />
            </button>
          );
        })}
      </div>
      <div className="ko-cal-leg">
        <span>
          <i className="ko-swatch-ce" />
          Up {month.gapUp}
        </span>
        <span>
          <i className="ko-swatch-both" />
          Flat {month.gapFlat}
        </span>
        <span>
          <i className="ko-swatch-pe" />
          Down {month.gapDown}
        </span>
      </div>
      <p className="ko-cal-sum">
        {month.tradingDays} sessions · {month.bullishDays} bullish · {month.bearishDays} bearish
      </p>
    </div>
  );
}
