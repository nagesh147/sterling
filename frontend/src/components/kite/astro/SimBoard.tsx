import type { SimMonth } from "../../../lib/astro/simulate";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

function pts(n: number) {
  const v = Math.round(n);
  return `${v > 0 ? "+" : ""}${v}`;
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
        One lot. Enter the first CE/PE play, hold the same side, exit when the run ends. Index points in the option’s favor. {MONTHS[sim.month - 1]} {sim.year} · {sim.underlying}.
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
          <span className="lbl">Net</span>
          <strong className={sim.pts >= 0 ? "text-up" : "text-down"}>{pts(sim.pts)}</strong>
        </div>
        <div>
          <span className="lbl">PE / CE</span>
          <strong>
            <span className={sim.pePts >= 0 ? "text-up" : "text-down"}>{pts(sim.pePts)} PE</span>
            {" · "}
            <span className={sim.cePts >= 0 ? "text-up" : "text-down"}>{pts(sim.cePts)} CE</span>
          </strong>
        </div>
      </div>
      {sim.best || sim.worst ? (
        <p className="ko-sim-ext text-muted">
          {sim.best ? `Best ${pts(sim.best.pts)} ${sim.best.side} ${sim.best.iso.slice(8)} ${sim.best.from}–${sim.best.to}` : ""}
          {sim.best && sim.worst ? " · " : ""}
          {sim.worst ? `Worst ${pts(sim.worst.pts)} ${sim.worst.side} ${sim.worst.iso.slice(8)} ${sim.worst.from}–${sim.worst.to}` : ""}
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
              <th className="ko-num">Pts</th>
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
                    <td className={`ko-num ${t.pts >= 0 ? "text-up" : "text-down"}`}>{pts(t.pts)}</td>
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
