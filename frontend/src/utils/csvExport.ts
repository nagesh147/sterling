/**
 * Minimal CSV export — build a CSV string from row objects + a column spec,
 * and trigger a browser download. Matches Kite Web's per-table "Download"
 * behaviour: exports exactly the rows currently visible/sorted, no server call.
 */
export interface CsvColumn<T> {
  header: string;
  /**
   * The cell value. Return `null`/`undefined` for a genuinely absent cell —
   * it becomes an empty field, never the string "null" and never a `0` that
   * would read as a measurement.
   */
  value: (row: T) => string | number | null | undefined;
}

function escapeCsvCell(v: string | number | null | undefined): string {
  if (v === null || v === undefined) return '';
  const s = String(v);
  if (/[",\r\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export function toCsv<T>(rows: readonly T[], columns: readonly CsvColumn<T>[]): string {
  const header = columns.map((c) => escapeCsvCell(c.header)).join(',');
  const lines = rows.map((r) => columns.map((c) => escapeCsvCell(c.value(r))).join(','));
  return [header, ...lines].join('\r\n');
}

export function downloadCsv(filename: string, csv: string): void {
  // Guarded: jsdom and any environment without object URLs throws here, and an
  // export failing must not take the calling pane down with it.
  try {
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
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
    /* no object-URL support — nothing to download to */
  }
}
