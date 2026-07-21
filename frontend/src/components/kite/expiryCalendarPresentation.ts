import type { ExpiryCalendarEntry } from '../../types/kiteEngine';

export type ExpirySeriesKind = 'weekly' | 'monthly';

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
] as const;

interface IsoDateParts {
  year: number;
  month: number;
  day: number;
}

function parseIsoDate(value: string): IsoDateParts | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const verified = new Date(Date.UTC(year, month - 1, day));
  if (
    verified.getUTCFullYear() !== year
    || verified.getUTCMonth() !== month - 1
    || verified.getUTCDate() !== day
  ) return null;
  return { year, month, day };
}

export function ordinalDay(day: number): string {
  const mod100 = day % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${day}th`;
  if (day % 10 === 1) return `${day}st`;
  if (day % 10 === 2) return `${day}nd`;
  if (day % 10 === 3) return `${day}rd`;
  return `${day}th`;
}

export function formatExpiryDate(value: string, asOf: string): string {
  const expiry = parseIsoDate(value);
  if (!expiry) return '';
  const reference = parseIsoDate(asOf);
  const year = reference && reference.year === expiry.year ? '' : ` ${expiry.year}`;
  return `${ordinalDay(expiry.day)} ${MONTHS[expiry.month - 1]}${year}`;
}

function monthCode(value: string): string {
  const parsed = parseIsoDate(value);
  return parsed ? MONTHS[parsed.month - 1].toUpperCase() : '';
}

/** Build the concrete labels for one private series rank. */
export function expiryLabelsForRank(
  entries: ExpiryCalendarEntry[],
  kind: ExpirySeriesKind,
  rank: number,
  asOf: string,
  collapseStocks = false,
): string[] {
  const dated = entries.flatMap((entry) => {
    const expiry = entry[kind][rank];
    return expiry ? [{ entry, expiry }] : [];
  });

  if (!collapseStocks) {
    return dated.map(({ entry, expiry }) => {
      const seriesMonth = kind === 'monthly' ? ` ${monthCode(expiry)}` : '';
      return `${entry.name}${seriesMonth} · ${formatExpiryDate(expiry, asOf)}`;
    });
  }

  const namesByDate = new Map<string, string[]>();
  dated.forEach(({ entry, expiry }) => {
    const names = namesByDate.get(expiry) ?? [];
    names.push(entry.name);
    namesByDate.set(expiry, names);
  });
  return [...namesByDate.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([expiry, names]) => {
      const owner = names.length === 1 ? names[0] : `${names.length} STOCKS`;
      return `${owner} ${monthCode(expiry)} · ${formatExpiryDate(expiry, asOf)}`;
    });
}
