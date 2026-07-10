/**
 * Minimal CSV export — build a CSV string from row objects + a column spec,
 * and trigger a browser download. Matches Kite Web's per-table "Download"
 * behaviour: exports exactly the rows currently visible/sorted, no server call.
 */
export interface CsvColumn<T> {
  header: string;
  value: (row: T) => string | number;
}

function escapeCsvCell(v: string | number): string {
  const s = String(v);
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export function toCsv<T>(rows: T[], columns: CsvColumn<T>[]): string {
  const header = columns.map((c) => escapeCsvCell(c.header)).join(',');
  const lines = rows.map((r) => columns.map((c) => escapeCsvCell(c.value(r))).join(','));
  return [header, ...lines].join('\r\n');
}

export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
