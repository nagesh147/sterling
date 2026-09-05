import { describe, expect, it } from 'vitest';
import { escapeCsvField, replayCsvName, toCsv } from '../replayCsv';
import { SIGNAL_CSV_COLUMNS, tradeCsvColumns } from '../replayColumns';

describe('CSV escaping', () => {
  // Neither of the two exporters this replaced escaped anything, so a symbol or
  // strategy name containing a comma silently corrupted the file.
  it('quotes a field containing a comma', () => {
    expect(escapeCsvField('a,b')).toBe('"a,b"');
  });

  it('doubles internal quotes', () => {
    expect(escapeCsvField('he said "hi"')).toBe('"he said ""hi"""');
  });

  it('quotes a field containing a newline', () => {
    expect(escapeCsvField('line1\nline2')).toBe('"line1\nline2"');
  });

  it('leaves a plain field alone', () => {
    expect(escapeCsvField('NIFTY')).toBe('NIFTY');
  });

  it('renders null and undefined as empty, not as the string "null"', () => {
    expect(escapeCsvField(null)).toBe('');
    expect(escapeCsvField(undefined)).toBe('');
  });
});

describe('toCsv', () => {
  it('emits a header row and CRLF line endings', () => {
    const csv = toCsv([{ a: 1 }], [{ header: 'A', value: (r) => r.a }]);
    expect(csv).toBe('A\r\n1');
  });

  it('survives a value containing every special character at once', () => {
    const csv = toCsv(
      [{ name: 'a,"b"\nc' }],
      [{ header: 'Name', value: (r) => r.name }],
    );
    expect(csv.split('\r\n')[0]).toBe('Name');
    expect(csv).toContain('"a,""b""\nc"');
  });
});

describe('trade columns', () => {
  it('omits the friction columns when nothing measured friction', () => {
    const headers = tradeCsvColumns(false).map((c) => c.header);
    expect(headers).not.toContain('Slippage (INR)');
    expect(headers).not.toContain('Raw Entry');
  });

  it('includes them when friction was measured', () => {
    const headers = tradeCsvColumns(true).map((c) => c.header);
    expect(headers).toContain('Slippage (INR)');
    expect(headers).toContain('Raw Entry');
  });
});

describe('signal columns', () => {
  it('exports the contract and the underlying separately', () => {
    const headers = SIGNAL_CSV_COLUMNS.map((c) => c.header);
    expect(headers).toContain('Contract');
    expect(headers).toContain('Underlying');
  });

  it('leaves R:R empty rather than writing Infinity', () => {
    const col = SIGNAL_CSV_COLUMNS.find((c) => c.header === 'R:R')!;
    expect(col.value({ entry: 100, stop: 100, target: 130 } as never)).toBe('');
  });
});

describe('file names', () => {
  it('carries the session and its time span', () => {
    expect(replayCsvName('signals', '2026-09-04', '09:00:00', '15:30:00'))
      .toBe('sterling_replay_signals_2026-09-04_09-00-15-30.csv');
  });

  it('omits the span when it is unknown', () => {
    expect(replayCsvName('trades', '2026-09-04')).toBe('sterling_replay_trades_2026-09-04.csv');
  });
});
