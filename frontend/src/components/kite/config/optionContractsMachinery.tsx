/**
 * The option-contract picker, and the numbers that summarise it.
 *
 * This used to be a 56-pixel banner sitting on top of the signal table — the
 * loudest thing on the screen, above the rows it was meant to serve, and the
 * only engine whose contract selection did not live in settings. ORB, Navigator
 * and Adaptive Edge all configure contracts under Connect; SuperTrend now does
 * too, and the board keeps a one-line summary that links here.
 *
 * `useContractSelection` is exported separately so the board can state what is
 * selected without mounting the picker.
 */
import React from 'react';
import {
  useEngineConfig,
  useExpiryCalendar,
  useRunScan,
  usePatchEngineConfig,
} from '../../../hooks/useSterlingKiteEngine';
import type {
  EngineConfigModel,
  ExpiryCalendarEntry,
} from '../../../types/kiteEngine';
import { k } from '../../../styles/kiteUI';
import {
  expiryContractsForRank,
  formatExpiryDate,
  type ExpiryContractPresentation,
  type ExpirySeriesKind,
} from '../expiryCalendarPresentation';

interface ExpirySeriesOption {
  rank: number;
  contracts: ExpiryContractPresentation[];
}

interface ExpiryGroupStats {
  selected: number;
  total: number;
  dates: number;
}

export const WEEKLY_RANKS = [0, 1, 2, 3];
export const MONTHLY_RANKS = [0, 1];

export const CONTRACT_PICKER_CSS = `
.sk-expiry-trigger:hover { background:#fffaf7 !important; }
.sk-expiry-trigger:focus-visible,
.sk-expiry-card:focus-visible,
.sk-expiry-action:focus-visible,
.sk-expiry-refresh:focus-visible { outline:2px solid rgba(56,126,209,.42); outline-offset:-2px; }
.sk-expiry-card:not(:disabled):not([aria-disabled="true"]):hover {
  background:var(--k-surface-warm) !important;
}
.sk-expiry-card:last-child { border-bottom:none !important; }
.sk-expiry-action:hover:not(:disabled),.sk-expiry-refresh:hover:not(:disabled) { background:#f2f2f3 !important; color:var(--k-text) !important; }
.sk-expiry-scroll { scrollbar-gutter:stable; }
@media (max-width:520px) {
  .sk-expiry-card { grid-template-columns:18px minmax(0,1fr) !important; }
  .sk-expiry-position { grid-column:2; }
  .sk-expiry-contracts { grid-column:2; }
}
@media (prefers-reduced-motion:reduce) {
  .sk-expiry-trigger > span:last-child,.sk-expiry-card { transition:none !important; }
}
`;

function CalendarGlyph() {
  return (
    <svg aria-hidden width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <rect x="3.5" y="5" width="17" height="15.5" rx="2.5" />
      <path d="M8 3.5V7M16 3.5V7M3.5 9.5h17" />
      <path d="M8 13h.01M12 13h.01M16 13h.01M8 17h.01M12 17h.01" strokeWidth="2.8" />
    </svg>
  );
}

function RefreshGlyph() {
  return (
    <svg aria-hidden width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 7v5h-5" />
      <path d="M4 17v-5h5" />
      <path d="M6.1 8.3A7 7 0 0118.7 10M17.9 15.7A7 7 0 015.3 14" />
    </svg>
  );
}

export function availableSeries(
  entries: ExpiryCalendarEntry[],
  kind: ExpirySeriesKind,
  choices: number[],
  asOf: string,
  collapseStocks = false,
): ExpirySeriesOption[] {
  return choices.flatMap((rank) => {
    const contracts = expiryContractsForRank(entries, kind, rank, asOf, collapseStocks);
    return contracts.length ? [{ rank, contracts }] : [];
  });
}

export function groupStats(options: ExpirySeriesOption[], values: number[]): ExpiryGroupStats {
  const selectedOptions = options.filter((option) => values.includes(option.rank));
  return {
    selected: selectedOptions.length,
    total: options.length,
    dates: selectedOptions.reduce((sum, option) => sum + option.contracts.length, 0),
  };
}

function seriesPosition(kind: ExpirySeriesKind, rank: number): string {
  if (rank === 0) return kind === 'weekly' ? 'Nearest listed' : 'Current listed';
  if (rank === 1) return 'Next listed';
  if (rank === 2) return 'Third listed';
  return 'Fourth listed';
}

function computeDte(expiryIso?: string, asOfIso?: string): number {
  if (!expiryIso) return 0;
  const expMs = Date.parse(expiryIso);
  const nowMs = asOfIso ? Date.parse(asOfIso) : Date.now();
  if (isNaN(expMs) || isNaN(nowMs)) return 0;
  return Math.max(0, Math.round((expMs - nowMs) / 86_400_000));
}

interface InstrumentItem {
  rank: number;
  expiry: string;
  date: string;
  dte: number;
}

interface InstrumentTile {
  name: string;
  title: string;
  items: InstrumentItem[];
}

export function availableInstrumentTiles(
  entries: ExpiryCalendarEntry[],
  kind: ExpirySeriesKind,
  choices: number[],
  asOf: string,
  collapseStocks = false,
): InstrumentTile[] {
  if (!entries.length) return [];

  if (collapseStocks) {
    const items = choices.flatMap((rank) => {
      const expiry = entries[0]?.[kind]?.[rank];
      if (!expiry) return [];
      const dte = computeDte(expiry, asOf);
      const date = formatExpiryDate(expiry, asOf);
      return [{ rank, expiry, date, dte }];
    });
    return [{
      name: 'STOCKS',
      title: `${entries.length} Selected Stock${entries.length === 1 ? '' : 's'}`,
      items,
    }];
  }

  return entries.flatMap((entry) => {
    const items = choices.flatMap((rank) => {
      const expiry = entry[kind]?.[rank];
      if (!expiry) return [];
      const dte = computeDte(expiry, asOf);
      const date = formatExpiryDate(expiry, asOf);
      return [{ rank, expiry, date, dte }];
    });
    if (!items.length) return [];
    const displayName = entry.display_name || entry.name;
    return [{
      name: entry.name,
      title: `${displayName} ${kind === 'weekly' ? 'Weekly' : 'Monthly'}`,
      items,
    }];
  });
}

function InstrumentExpiryCard({
  tile,
  kind,
  values,
  disabled,
  onToggleRank,
}: {
  tile: InstrumentTile;
  kind: ExpirySeriesKind;
  values: number[];
  disabled: boolean;
  onToggleRank: (rank: number) => void;
}) {
  return (
    <div
      style={{
        minWidth: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        padding: '11px 13px',
        border: `1px solid ${k.border}`,
        borderRadius: 8,
        background: 'var(--k-bg)',
        fontFamily: 'inherit',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: `1px solid ${k.border}`, paddingBottom: 6 }}>
        <span style={{ color: k.text, fontSize: 10, fontWeight: 750, letterSpacing: '.035em', textTransform: 'uppercase' }}>
          {tile.title}
        </span>
      </div>

      <div style={{ display: 'grid', gap: 4, width: '100%' }}>
        {tile.items.map((item) => {
          const active = values.includes(item.rank);
          const dteText = item.dte === 0 ? '(today)' : `(${item.dte} day${item.dte === 1 ? '' : 's'})`;
          return (
            <button
              key={`${tile.name}-${item.rank}`}
              type="button"
              disabled={disabled}
              onClick={() => onToggleRank(item.rank)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 8,
                padding: '5px 7px',
                borderRadius: 5,
                border: active ? '1px solid color-mix(in srgb, var(--k-orange) 50%, transparent)' : '1px solid transparent',
                background: active ? 'color-mix(in srgb, var(--k-orange) 8%, var(--k-bg))' : 'transparent',
                cursor: disabled ? 'wait' : 'pointer',
                textAlign: 'left',
                width: '100%',
                fontFamily: 'inherit',
                transition: 'background .12s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
                <span aria-hidden style={{
                  width: 15,
                  height: 15,
                  flexShrink: 0,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: 3,
                  border: `1px solid ${active ? k.orange : '#cfcfcf'}`,
                  background: active ? k.orange : 'var(--k-bg)',
                  color: 'var(--k-bg)',
                  fontSize: 9.5,
                  fontWeight: 800,
                  lineHeight: 1,
                }}>
                  {active ? '✓' : ''}
                </span>
                <span style={{ color: active ? k.text : 'var(--k-ink-3)', fontSize: 11, fontWeight: active ? 700 : 500, whiteSpace: 'nowrap' }}>
                  {item.date} <span style={{ color: active ? '#c26233' : 'var(--k-dim)', fontSize: 9.5, fontWeight: 500 }}>{dteText}</span>
                </span>
              </div>

              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 15,
                  height: 15,
                  borderRadius: '50%',
                  background: kind === 'weekly' ? '#eef4fb' : '#f4f4f5',
                  border: `1px solid ${kind === 'weekly' ? '#cbe0f7' : '#e4e4e7'}`,
                  color: kind === 'weekly' ? 'var(--k-blue-kite, #2563eb)' : '#71717a',
                  fontSize: 9,
                  fontWeight: 800,
                  lineHeight: 1,
                  flexShrink: 0,
                }}
                title={kind === 'weekly' ? 'Weekly contract' : 'Monthly contract'}
              >
                {kind === 'weekly' ? 'w' : 'm'}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export interface CombinedInstrumentItem {
  kind: ExpirySeriesKind;
  rank: number;
  expiry: string;
  date: string;
  dte: number;
}

export interface CombinedInstrumentTile {
  name: string;
  title: string;
  items: CombinedInstrumentItem[];
}

export function buildCombinedInstrumentTiles(
  indexEntries: ExpiryCalendarEntry[],
  stockEntries: ExpiryCalendarEntry[],
  weeklyRanks: number[],
  monthlyRanks: number[],
  asOf: string,
): CombinedInstrumentTile[] {
  const indexTiles: CombinedInstrumentTile[] = indexEntries.flatMap((entry) => {
    const weeklyItems: CombinedInstrumentItem[] = weeklyRanks.flatMap((rank) => {
      const expiry = entry.weekly?.[rank];
      if (!expiry) return [];
      const dte = computeDte(expiry, asOf);
      const date = formatExpiryDate(expiry, asOf);
      return [{ kind: 'weekly', rank, expiry, date, dte }];
    });

    const monthlyItems: CombinedInstrumentItem[] = monthlyRanks.flatMap((rank) => {
      const expiry = entry.monthly?.[rank];
      if (!expiry) return [];
      const dte = computeDte(expiry, asOf);
      const date = formatExpiryDate(expiry, asOf);
      return [{ kind: 'monthly', rank, expiry, date, dte }];
    });

    const items = [...weeklyItems, ...monthlyItems].sort((a, b) => {
      if (a.expiry === b.expiry) return a.kind === 'weekly' ? -1 : 1;
      return a.expiry.localeCompare(b.expiry);
    });

    if (!items.length) return [];
    const displayName = entry.display_name || entry.name;
    return [{
      name: entry.name,
      title: displayName,
      items,
    }];
  });

  if (stockEntries.length) {
    const stockItems: CombinedInstrumentItem[] = monthlyRanks.flatMap((rank) => {
      const expiry = stockEntries[0]?.monthly?.[rank];
      if (!expiry) return [];
      const dte = computeDte(expiry, asOf);
      const date = formatExpiryDate(expiry, asOf);
      return [{ kind: 'monthly', rank, expiry, date, dte }];
    });

    if (stockItems.length) {
      indexTiles.push({
        name: 'STOCKS',
        title: `${stockEntries.length} Selected Stock${stockEntries.length === 1 ? '' : 's'}`,
        items: stockItems,
      });
    }
  }

  return indexTiles;
}

function CombinedIndexExpiryCard({
  tile,
  weeklyValues,
  monthlyValues,
  stockValues,
  disabled,
  onToggleWeeklyRank,
  onToggleMonthlyRank,
  onToggleStockRank,
}: {
  tile: CombinedInstrumentTile;
  weeklyValues: number[];
  monthlyValues: number[];
  stockValues: number[];
  disabled: boolean;
  onToggleWeeklyRank: (rank: number) => void;
  onToggleMonthlyRank: (rank: number) => void;
  onToggleStockRank: (rank: number) => void;
}) {
  const isStocks = tile.name === 'STOCKS';
  const weeklyItems = tile.items.filter((item) => item.kind === 'weekly');
  const monthlyItems = tile.items.filter((item) => item.kind === 'monthly');

  const renderItem = (item: CombinedInstrumentItem) => {
    const active = isStocks
      ? stockValues.includes(item.rank)
      : item.kind === 'weekly'
        ? weeklyValues.includes(item.rank)
        : monthlyValues.includes(item.rank);

    const dteText = item.dte === 0 ? '(today)' : `(${item.dte} day${item.dte === 1 ? '' : 's'})`;
    const toggle = () => {
      if (isStocks) {
        onToggleStockRank(item.rank);
      } else if (item.kind === 'weekly') {
        onToggleWeeklyRank(item.rank);
      } else {
        onToggleMonthlyRank(item.rank);
      }
    };

    return (
      <button
        key={`${tile.name}-${item.kind}-${item.rank}`}
        type="button"
        disabled={disabled}
        onClick={toggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          padding: '4px 4px',
          borderRadius: 5,
          border: '1px solid transparent',
          background: 'transparent',
          cursor: disabled ? 'wait' : 'pointer',
          textAlign: 'left',
          width: '100%',
          fontFamily: 'inherit',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <span aria-hidden style={{
            width: 16,
            height: 16,
            flexShrink: 0,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 4,
            border: active ? '1px solid #2563eb' : '1px solid #d1d5db',
            background: active ? '#2563eb' : 'var(--k-bg)',
            color: '#ffffff',
            fontSize: 10,
            fontWeight: 700,
            lineHeight: 1,
            transition: 'all 0.12s ease',
          }}>
            {active ? '✓' : ''}
          </span>
          <span style={{ color: 'var(--k-text)', fontSize: 11.5, fontWeight: 450, whiteSpace: 'nowrap' }}>
            {item.date} <span style={{ color: 'var(--k-dim)', fontSize: 11, fontWeight: 400 }}>{dteText}</span>
          </span>
        </div>

        {item.kind === 'weekly' && (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 16,
              height: 16,
              borderRadius: '50%',
              background: '#eff6ff',
              color: '#3b82f6',
              fontSize: 9.5,
              fontWeight: 750,
              lineHeight: 1,
              flexShrink: 0,
            }}
            title="Weekly contract"
          >
            w
          </span>
        )}
      </button>
    );
  };

  return (
    <div
      style={{
        minWidth: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        padding: '12px 14px',
        border: `1px solid ${k.border}`,
        borderRadius: 8,
        background: 'var(--k-bg)',
        fontFamily: 'inherit',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: 2 }}>
        <span style={{ color: 'var(--k-dim)', fontSize: 11, fontWeight: 600, letterSpacing: '.01em' }}>
          {tile.title} Expiries
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 3, width: '100%' }}>
        {weeklyItems.map(renderItem)}

        {weeklyItems.length > 0 && monthlyItems.length > 0 && (
          <div
            style={{
              marginTop: 6,
              paddingTop: 6,
              borderTop: `1px solid ${k.border}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 2,
            }}
          >
            <span style={{ color: 'var(--k-dim)', fontSize: 9.5, fontWeight: 700, letterSpacing: '.04em', textTransform: 'uppercase' }}>
              Monthly
            </span>
          </div>
        )}

        {monthlyItems.map(renderItem)}
      </div>
    </div>
  );
}

export function IndexExpirySection({
  indexEntries,
  stockEntries,
  weeklyValues,
  monthlyValues,
  stockValues,
  weeklyChoices = WEEKLY_RANKS,
  monthlyChoices = MONTHLY_RANKS,
  asOf,
  disabled,
  onChangeWeekly,
  onChangeMonthly,
  onChangeStocks,
}: {
  indexEntries: ExpiryCalendarEntry[];
  stockEntries: ExpiryCalendarEntry[];
  weeklyValues: number[];
  monthlyValues: number[];
  stockValues: number[];
  weeklyChoices?: number[];
  monthlyChoices?: number[];
  asOf: string;
  disabled: boolean;
  onChangeWeekly: (values: number[]) => void;
  onChangeMonthly: (values: number[]) => void;
  onChangeStocks: (values: number[]) => void;
}) {
  const tiles = buildCombinedInstrumentTiles(indexEntries, stockEntries, weeklyChoices, monthlyChoices, asOf);

  const toggleWeeklyRank = (rank: number) => {
    const active = weeklyValues.includes(rank);
    if (active && weeklyValues.length === 1) return;
    const next = active ? weeklyValues.filter((v) => v !== rank) : [...new Set([...weeklyValues, rank])];
    onChangeWeekly(next.sort((a, b) => a - b));
  };

  const toggleMonthlyRank = (rank: number) => {
    const active = monthlyValues.includes(rank);
    if (active && monthlyValues.length === 1) return;
    const next = active ? monthlyValues.filter((v) => v !== rank) : [...new Set([...monthlyValues, rank])];
    onChangeMonthly(next.sort((a, b) => a - b));
  };

  const toggleStockRank = (rank: number) => {
    const active = stockValues.includes(rank);
    if (active && stockValues.length === 1) return;
    const next = active ? stockValues.filter((v) => v !== rank) : [...new Set([...stockValues, rank])];
    onChangeStocks(next.sort((a, b) => a - b));
  };

  return tiles.length ? (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))',
        gap: 10,
        background: 'var(--k-bg)',
      }}
    >
      {tiles.map((tile) => (
        <CombinedIndexExpiryCard
          key={tile.name}
          tile={tile}
          weeklyValues={weeklyValues}
          monthlyValues={monthlyValues}
          stockValues={stockValues}
          disabled={disabled}
          onToggleWeeklyRank={toggleWeeklyRank}
          onToggleMonthlyRank={toggleMonthlyRank}
          onToggleStockRank={toggleStockRank}
        />
      ))}
    </div>
  ) : (
    <div style={{ padding: '12px', color: k.dim, fontSize: 10, lineHeight: 1.4 }}>
      No listed contracts for the selected instruments. Select instruments above to see expiries.
    </div>
  );
}

export function ExpiryGroup({
  title,
  description,
  values,
  choices,
  entries,
  kind,
  asOf,
  collapseStocks = false,
  disabled,
  onChange,
}: {
  title: string;
  description: string;
  values: number[];
  choices: number[];
  entries: ExpiryCalendarEntry[];
  kind: ExpirySeriesKind;
  asOf: string;
  collapseStocks?: boolean;
  disabled: boolean;
  onChange: (values: number[]) => void;
}) {
  const tiles = availableInstrumentTiles(entries, kind, choices, asOf, collapseStocks);
  const allSelected = choices.length > 0 && values.length === choices.length;

  return (
    <section aria-label={title} style={{ overflow: 'hidden', border: `1px solid ${k.border}`, borderRadius: 9, background: 'var(--k-bg)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 12px', borderBottom: tiles.length ? '1px solid #ededed' : 'none' }}>
        <span style={{ minWidth: 0, flex: 1 }}>
          <strong style={{ display: 'block', color: k.text, fontSize: 11.5, fontWeight: 750 }}>{title}</strong>
          <span style={{ display: 'block', marginTop: 3, color: 'var(--k-ink-6)', fontSize: 9.5, lineHeight: 1.4 }}>{description}</span>
        </span>
        {choices.length > 0 && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 9, flexShrink: 0 }}>
            <span style={{ color: 'var(--k-ink-5)', fontSize: 9.5, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
              {values.length} of {choices.length}
            </span>
            {choices.length > 1 && (
              <button
                className="sk-expiry-action"
                type="button"
                disabled={disabled}
                aria-label={`${allSelected ? 'Use nearest only for' : 'Select all'} ${title}`}
                onClick={() => onChange(allSelected ? [choices[0]] : [...choices])}
                style={{
                  minHeight: 30,
                  border: `1px solid ${k.border}`,
                  borderRadius: 6,
                  padding: '0 9px',
                  background: 'var(--k-bg)',
                  color: 'var(--k-ink-3)',
                  fontFamily: 'inherit',
                  fontSize: 9.5,
                  fontWeight: 650,
                  cursor: disabled ? 'wait' : 'pointer',
                }}
              >
                {allSelected ? 'Nearest only' : 'Select all'}
              </button>
            )}
          </span>
        )}
      </div>

      {tiles.length ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))',
            gap: 10,
            padding: 12,
            background: 'var(--k-bg)',
          }}
        >
          {tiles.map((tile) => (
            <InstrumentExpiryCard
              key={tile.name}
              tile={tile}
              kind={kind}
              values={values}
              disabled={disabled}
              onToggleRank={(rank) => {
                const active = values.includes(rank);
                if (active && values.length === 1) return;
                const next = active
                  ? values.filter((v) => v !== rank)
                  : [...new Set([...values, rank])];
                onChange(next.sort((a, b) => a - b));
              }}
            />
          ))}
        </div>
      ) : (
        <div style={{ padding: '10px', color: k.dim, fontSize: 9.5, lineHeight: 1.4 }}>
          No listed contracts for the selected instruments.
        </div>
      )}
    </section>
  );
}

export function selectedEntries(
  entries: ExpiryCalendarEntry[],
  selected: string[],
): ExpiryCalendarEntry[] {
  const wanted = new Set(selected.map((name) => name.trim().toUpperCase()));
  return entries.filter((entry) => {
    const nameMatch = wanted.has(entry.name.trim().toUpperCase());
    const displayMatch = entry.display_name ? wanted.has(entry.display_name.trim().toUpperCase()) : false;
    return nameMatch || displayMatch;
  });
}


export interface ContractSelection {
  /** "12 of 18 expiry sets · 5 live dates", or why it cannot say.
   *
   * No longer rendered — the picker header showed it and it was asked to go.
   * Kept because `selected`/`dates` below are the same computation and callers
   * still read them; the string is the cheap part. */
  summary: string;
  /** Expiry sets currently switched on. */
  selected: number;
  /** Distinct exchange dates those sets resolve to. */
  dates: number;
  loading: boolean;
  error: boolean;
}

/**
 * What SuperTrend is currently set to scan, as a sentence.
 *
 * Shared by the picker's own header and by the board's summary line, so the two
 * can never disagree about how many contracts are selected.
 */
/**
 * The contract-selection fields any engine needs to host the picker.
 *
 * A structural type rather than one engine's config: every option strategy
 * stores these under the same names, so the picker can be the SAME control on
 * each page instead of a lookalike re-implemented per strategy.
 */
export interface ContractSelectionConfig {
  scan_indices: string[];
  scan_stocks: string[];
  scan_all_stocks: boolean;
  scan_weekly_series_indices?: number[];
  scan_monthly_series_indices?: number[];
  scan_monthly_series_stocks?: number[];
}

export function useContractSelection(override?: ContractSelectionConfig | null): ContractSelection {
  const { data: engineCfg } = useEngineConfig();
  // Passed config wins; falling back to the engine's keeps every existing
  // caller working unchanged.
  const cfg = override ?? engineCfg;
  const calendar = useExpiryCalendar();

  if (calendar.isLoading && !calendar.data) {
    return { summary: 'Loading Kite-listed expiries…', selected: 0, dates: 0, loading: true, error: false };
  }
  if (!calendar.data) {
    return { summary: 'Contract dates unavailable', selected: 0, dates: 0, loading: false, error: true };
  }
  if (!cfg) {
    return { summary: 'Live dates from Kite instruments', selected: 0, dates: 0, loading: false, error: false };
  }

  const indexEntries = selectedEntries(calendar.data.indices, cfg.scan_indices);
  const stockEntries = cfg.scan_all_stocks
    ? calendar.data.stocks
    : selectedEntries(calendar.data.stocks, cfg.scan_stocks);

  const weekly = groupStats(
    availableSeries(indexEntries, 'weekly', WEEKLY_RANKS, calendar.data.as_of),
    cfg.scan_weekly_series_indices ?? WEEKLY_RANKS,
  );
  const monthlyIndices = groupStats(
    availableSeries(indexEntries, 'monthly', MONTHLY_RANKS, calendar.data.as_of),
    cfg.scan_monthly_series_indices ?? MONTHLY_RANKS,
  );
  const monthlyStocks = groupStats(
    availableSeries(stockEntries, 'monthly', MONTHLY_RANKS, calendar.data.as_of, true),
    cfg.scan_monthly_series_stocks ?? MONTHLY_RANKS,
  );

  const selected = weekly.selected + monthlyIndices.selected + monthlyStocks.selected;
  const total = weekly.total + monthlyIndices.total + monthlyStocks.total;
  const dates = weekly.dates + monthlyIndices.dates + monthlyStocks.dates;

  return {
    summary: total
      ? `${selected} of ${total} expiry sets · ${dates} live date${dates === 1 ? '' : 's'}`
      : 'No listed expiries in the selected universe',
    selected,
    dates,
    loading: false,
    error: false,
  };
}
