import type { SimMonth } from "../../../lib/astro/simulate";
import { rupees } from "../../../lib/astro/simulate";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

function inr(n: number) {
  const v = Math.round(n);
  const body = new Intl.NumberFormat("en-IN").format(Math.abs(v));
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}₹${body}`;
}

export function SimBoard({
  sim,
  loading,
  error,
}: {
  sim: SimMonth | null;
  loading: boolean;
  error?: string | null;
}) {
  if (loading) return <p className="ko-sim-empty text-muted">Running one-lot sim…</p>;
  if (error || !sim) return <p className="ko-sim-empty text-muted">{error || "No tape"}</p>;

  const rate = sim.trades ? Math.round((sim.hits / sim.trades) * 100) : 0;

  return (
    <div className="ko-sim">
      <p className="ko-sim-lead">
        One lot ATM. Enter the first CE/PE play, hold the same side, stop / trail / target. P&L is rupees: index points × {sim.lot} lot × 0.5 delta. Before brokerage. {MONTHS[sim.month - 1]} {sim.year} · {sim.underlying}.
      </p>
      <div className="ko-sim-kpis">
        <div>
          <span className="lbl">Trades</span>
          <strong>{sim.trades}</strong>
        </div>
        <div>
          <span className="lbl">Hit</span>
          <strong>
            {sim.hits}/{sim.trades || 0} · {rate}%
          </strong>
        </div>
        <div>
          <span className="lbl">P&L</span>
          <strong className={sim.inr >= 0 ? "text-up" : "text-down"}>{inr(sim.inr)}</strong>
        </div>
        <div>
          <span className="lbl">PE / CE</span>
          <strong>
            <span className={sim.peInr >= 0 ? "text-up" : "text-down"}>{inr(sim.peInr)} PE</span>
            {" · "}
            <span className={sim.ceInr >= 0 ? "text-up" : "text-down"}>{inr(sim.ceInr)} CE</span>
          </strong>
        </div>
      </div>
      {sim.best || sim.worst ? (
        <p className="ko-sim-ext text-muted">
          {sim.best ? `Best ${inr(rupees(sim.best.pts, sim.underlying))} ${sim.best.side} ${sim.best.iso.slice(8)} ${sim.best.from}–${sim.best.to}` : ""}
          {sim.best && sim.worst ? " · " : ""}
          {sim.worst ? `Worst ${inr(rupees(sim.worst.pts, sim.underlying))} ${sim.worst.side} ${sim.worst.iso.slice(8)} ${sim.worst.from}–${sim.worst.to}` : ""}
          {sim.missing ? ` · ${sim.missing} days without tape` : ""}
        </p>
      ) : null}
      <div className="ko-scroll">
        <table className="ko-table ko-clock ko-sim-table">
          <thead>
            <tr>
              <th>Day</th>
              <th>Run</th>
              <th>Side</th>
              <th className="ko-num">P&L</th>
            </tr>
          </thead>
          <tbody>
            {sim.days.map((d) =>
              d.skipped ? (
                <tr key={d.iso}>
                  <td>
                    {d.weekday.slice(0, 3)} {d.iso.slice(8)}
                  </td>
                  <td colSpan={3} className="text-muted">
                    {d.reason || "—"}
                  </td>
                </tr>
              ) : d.trades.length === 0 ? (
                <tr key={d.iso}>
                  <td>
                    {d.weekday.slice(0, 3)} {d.iso.slice(8)}
                  </td>
                  <td colSpan={3} className="text-muted">
                    No play
                  </td>
                </tr>
              ) : (
                d.trades.map((t, i) => (
                  <tr key={`${d.iso}-${i}`}>
                    <td>{i === 0 ? `${d.weekday.slice(0, 3)} ${d.iso.slice(8)}` : ""}</td>
                    <td>
                      {t.from}–{t.to}
                      <span className="ko-time-meta"> {t.windows} win{t.why !== "run" ? ` · ${t.why}` : ""}</span>
                    </td>
                    <td>
                      <span className={t.side === "CE" ? "ko-pill ko-pill-ce" : "ko-pill ko-pill-pe"}>{t.side}</span>
                    </td>
                    <td className={`ko-num ${t.pts >= 0 ? "text-up" : "text-down"}`}>{inr(rupees(t.pts, sim.underlying))}</td>
                  </tr>
                ))
              ),
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
