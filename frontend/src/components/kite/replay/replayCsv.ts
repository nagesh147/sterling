/**
 * The single CSV exporter for the replay dock.
 *
 * There used to be two, in `SimulationBar` and `SimulationSummary`, and they had
 * drifted to 20 and 17 columns for the same trades. Neither escaped anything, so
 * a symbol or strategy name containing a comma silently corrupted the file.
 *
 * Columns are described once and drive both the rendered table and the export,
 * so the two cannot diverge again.
 */

export type CsvColumn<T> = {
  /** Header text. Should match the rendered column header. */
  header: string;
  /** Cell value. Return `null`/`undefined` for an empty cell, not the string "0". */
  value: (row: T) => string | number | null | undefined;
};

/**
 * RFC 4180: a field containing a comma, a double quote or a newline is wrapped
 * in double quotes, and internal quotes are doubled.
 */
export function escapeCsvField(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '';
  const s = String(value);
  if (!/[",\r\n]/.test(s)) return s;
  return `"${s.replace(/"/g, '""')}"`;
}

export function toCsv<T>(rows: readonly T[], columns: readonly CsvColumn<T>[]): string {
  const head = columns.map((c) => escapeCsvField(c.header)).join(',');
  const body = rows.map((row) =>
    columns.map((c) => escapeCsvField(c.value(row))).join(','),
  );
  return [head, ...body].join('\r\n');
}

/**
 * Hand the browser a file.
 *
 * Guarded because jsdom (and any environment without object URLs) throws here,
 * and an export failing must not take the dock down with it.
 */
export function downloadCsv(filename: string, csv: string): void {
  try {
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch {
    /* no object URL support — nothing to download to */
  }
}

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
