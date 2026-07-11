import { describe, it, expect, vi } from 'vitest';
import { toCsv, downloadCsv } from './csvExport';

describe('toCsv', () => {
  it('builds a header row plus one row per item', () => {
    const rows = [{ symbol: 'INFY', qty: 10 }, { symbol: 'TCS', qty: 5 }];
    const csv = toCsv(rows, [
      { header: 'Symbol', value: (r) => r.symbol },
      { header: 'Qty', value: (r) => r.qty },
    ]);
    expect(csv).toBe('Symbol,Qty\r\nINFY,10\r\nTCS,5');
  });

  it('quotes and escapes cells containing commas or quotes', () => {
    const rows = [{ name: 'Reliance, Ltd' }, { name: 'Say "hi"' }];
    const csv = toCsv(rows, [{ header: 'Name', value: (r) => r.name }]);
    expect(csv).toBe('Name\r\n"Reliance, Ltd"\r\n"Say ""hi"""');
  });

  it('returns just the header row for an empty list', () => {
    const csv = toCsv([] as { symbol: string }[], [{ header: 'Symbol', value: (r) => r.symbol }]);
    expect(csv).toBe('Symbol');
  });
});

describe('downloadCsv', () => {
  it('creates an object URL, clicks a temporary anchor, and revokes the URL', () => {
    const createUrl = vi.fn(() => 'blob:mock-url');
    const revoke = vi.fn();
    (globalThis as any).URL.createObjectURL = createUrl;
    (globalThis as any).URL.revokeObjectURL = revoke;
    const click = vi.fn();
    const origCreateElement = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const el = origCreateElement(tag);
      if (tag === 'a') (el as HTMLAnchorElement).click = click;
      return el;
    });

    downloadCsv('positions.csv', 'a,b\r\n1,2');

    expect(createUrl).toHaveBeenCalled();
    expect(click).toHaveBeenCalled();
    expect(revoke).toHaveBeenCalledWith('blob:mock-url');

    vi.restoreAllMocks();
  });
});
