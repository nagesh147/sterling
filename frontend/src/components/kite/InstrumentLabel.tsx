import React from 'react';

export interface ParsedParts {
  underlying: string;
  strike?: string;
  type?: string; // CE / PE / FUT
  day?: number;
  month?: string; // JUN
  year?: string; // 24
  isWeekly?: boolean;
}

export function parseInstrument(ts: string): ParsedParts | null {
  // Monthly NFO options: APLAPOLLO26JUN1820CE
  const nfoRe = /^([A-Z]+)(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d+)(CE|PE)(BFO|NFO)?$/;
  const nfoM = ts.match(nfoRe);
  if (nfoM) {
    return {
      underlying: nfoM[1],
      year: nfoM[2],
      month: nfoM[3].toUpperCase(),
      strike: nfoM[4],
      type: nfoM[5],
      isWeekly: false,
    };
  }

  // Weekly NFO options: NIFTY2461324500CE
  const weeklyMatch = ts.match(/^([A-Z]+)(\d{2})(1|2|3|4|5|6|7|8|9|O|N|D)(\d{2})(\d+)(CE|PE)(BFO|NFO)?$/);
  if (weeklyMatch) {
    const mMap: Record<string, string> = {'1':'JAN','2':'FEB','3':'MAR','4':'APR','5':'MAY','6':'JUN','7':'JUL','8':'AUG','9':'SEP','O':'OCT','N':'NOV','D':'DEC'};
    return {
      underlying: weeklyMatch[1],
      year: weeklyMatch[2],
      month: mMap[weeklyMatch[3]],
      day: parseInt(weeklyMatch[4], 10),
      strike: weeklyMatch[5],
      type: weeklyMatch[6],
      isWeekly: true,
    };
  }

  // NFO Futures: NIFTY24JUNFUT
  const futRe = /^([A-Z]+)(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)FUT(BFO|NFO)?$/;
  const futM = ts.match(futRe);
  if (futM) {
    return {
      underlying: futM[1],
      year: futM[2],
      month: futM[3].toUpperCase(),
      type: 'FUT',
      isWeekly: false,
    };
  }

  // BSE options: SENSEX2461875500CE
  const bseRe = /^([A-Z]+)(\d{2})([1-9A-COND])(\d{2})(\d+)(CE|PE)$/;
  const bseM = ts.match(bseRe);
  if (bseM) {
    let mon = parseInt(bseM[3], 10);
    if (bseM[3] === 'O' || bseM[3] === 'A') mon = 10;
    if (bseM[3] === 'N' || bseM[3] === 'B') mon = 11;
    if (bseM[3] === 'D' || bseM[3] === 'C') mon = 12;
    if (mon >= 1 && mon <= 12) {
      const d = new Date(2000 + Number(bseM[2]), mon - 1, 1);
      const monthStr = d.toLocaleString('en-US', { month: 'short' }).toUpperCase();
      return {
        underlying: bseM[1],
        year: bseM[2],
        month: monthStr,
        day: parseInt(bseM[4], 10),
        strike: bseM[5],
        type: bseM[6],
        isWeekly: true,
      };
    }
  }

  return null;
}

export function getOrdinal(n: number) {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return s[(v - 20) % 10] || s[v] || s[0];
}

export function InstrumentLabel({ symbol, fallback }: { symbol: string; fallback?: string }) {
  const parts = symbol.split(':');
  let exchange = parts.length > 1 ? parts[0] : '';
  const rawTs = parts.length > 1 ? parts[1] : symbol;
  
  if (rawTs === 'NIFTY 50' || rawTs === 'NIFTY BANK' || rawTs === 'SENSEX' || rawTs === 'BANKEX' || rawTs === 'NIFTY 100' || rawTs === 'NIFTY COMMODITIES' || rawTs === 'NIFTY FIN SERVICE' || rawTs.includes('INDEX')) {
    exchange = 'INDEX';
  }

  const parsed = parseInstrument(rawTs);

  if (!parsed) {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', whiteSpace: 'nowrap' }}>
        <span>{fallback || rawTs.replace(/(CE|PE)(BFO|NFO)?$/, ' $1')}</span>
        {exchange && <span style={{ fontSize: 9, color: '#9b9b9b', marginLeft: 4 }}>{exchange}</span>}
      </span>
    );
  }

  const { underlying, day, month, strike, type, isWeekly, year } = parsed;

  return (
    <span style={{ display: 'inline-flex', alignItems: 'baseline', whiteSpace: 'nowrap' }}>
      <span style={{ marginRight: 4 }}>{underlying}</span>
      <span style={{ marginRight: 4, display: 'inline-flex', alignItems: 'baseline', gap: 3, fontSize: 12 }}>
        {day && (
          <span>
            {day}
            <sup style={{ fontSize: '0.85em', marginLeft: 1 }}>
              {getOrdinal(day)}
              {isWeekly && (
                <span style={{ 
                  color: 'var(--color-text-4, #4184f3)', 
                  backgroundColor: 'rgba(var(--color-bg-5--rgb, 65, 132, 243), 0.1)', 
                  textAlign: 'center', 
                  borderRadius: '100%', 
                  width: 10, 
                  height: 10, 
                  fontSize: '0.65em', 
                  lineHeight: '10px',
                  display: 'inline-block',
                  marginLeft: 4
                }}>w</span>
              )}
            </sup>
          </span>
        )}
        {!day && isWeekly && (
          <span style={{ 
            color: 'var(--color-text-4, #4184f3)', 
            backgroundColor: 'rgba(var(--color-bg-5--rgb, 65, 132, 243), 0.1)', 
            textAlign: 'center', 
            borderRadius: '100%', 
            width: 10, 
            height: 10, 
            fontSize: '0.65em', 
            lineHeight: '10px',
            display: 'inline-block',
            marginLeft: 2,
            marginRight: 2
          }}>w</span>
        )}
        {month && <span>{month}</span>}
      </span>
      {strike && <span style={{ marginRight: 4 }}>{strike}</span>}
      {type && <span style={{ marginRight: 4 }}>{type}</span>}
      {exchange && !type && exchange !== 'INDEX' && <span style={{ fontSize: 9, color: '#9b9b9b', background: '#f1f1f1', padding: '1px 4px', borderRadius: 2 }}>{exchange}</span>}
    </span>
  );
}
