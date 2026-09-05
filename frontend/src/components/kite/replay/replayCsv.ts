/**
 * Replay-specific CSV helpers.
 *
 * The escaping and download live in `utils/csvExport`, which the positions and
 * portfolio panes already use — this module adds only what is specific to a
 * replay export. There used to be TWO bespoke exporters for this dock alone
 * (in `SimulationBar` and `SimulationSummary`), drifted to 20 and 17 columns
 * for the same trades, and neither escaped anything, so a symbol containing a
 * comma corrupted the file. Adding a third would have been the same mistake.
 */
import { CsvColumn, downloadCsv, toCsv } from '../../../utils/csvExport';

export type { CsvColumn };
export { downloadCsv, toCsv };

/** `sterling_replay_signals_2026-09-04_09-00-15-30.csv` */
export function replayCsvName(
  kind: 'signals' | 'trades',
  date: string,
  startTime?: string,
  endTime?: string,
): string {
  const span =
    startTime && endTime
      ? `_${startTime.slice(0, 5).replace(':', '-')}-${endTime.slice(0, 5).replace(':', '-')}`
      : '';
  return `sterling_replay_${kind}_${date}${span}.csv`;
}

export function exportCsv<T>(
  filename: string,
  rows: readonly T[],
  columns: readonly CsvColumn<T>[],
): void {
  if (!rows.length) return;
  downloadCsv(filename, toCsv(rows, columns));
}
