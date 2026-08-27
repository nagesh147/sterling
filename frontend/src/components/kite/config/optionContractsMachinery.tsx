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

function ExactExpiryCard({
  option,
  kind,
  active,
  lockSelected,
  disabled,
  onToggle,
}: {
  option: ExpirySeriesOption;
  kind: ExpirySeriesKind;
  active: boolean;
  lockSelected: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  const labels = option.contracts.map((contract) => contract.label);
  const title = lockSelected
    ? 'At least one listed expiry must remain selected'
    : labels.join(' • ');

  return (
    <button
      className="sk-expiry-card"
      type="button"
      aria-label={labels.join(', ')}
      aria-pressed={active}
      aria-disabled={lockSelected || disabled}
      disabled={disabled}
      title={title}
      onClick={() => {
        if (!lockSelected) onToggle();
      }}
      style={{
        minWidth: 0,
        display: 'grid',
        gridTemplateColumns: '18px 92px minmax(0, 1fr)',
        gap: 10,
        alignItems: 'center',
        textAlign: 'left',
        padding: '9px 11px',
        border: 'none',
        borderBottom: `1px solid ${k.border}`,
        borderRadius: 0,
        background: active ? '#fff8f4' : 'var(--k-bg)',
        color: k.text,
        boxShadow: active ? `inset 3px 0 ${k.orange}` : 'none',
        fontFamily: 'inherit',
        cursor: disabled ? 'wait' : lockSelected ? 'not-allowed' : 'pointer',
        opacity: disabled ? .62 : 1,
        transition: 'background .14s ease, box-shadow .14s ease',
      }}
    >
      <span aria-hidden style={{
        width: 16,
        height: 16,
        flexShrink: 0,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: 4,
        border: `1px solid ${active ? k.orange : '#cfcfcf'}`,
        background: active ? k.orange : 'var(--k-bg)',
        color: 'var(--k-bg)',
        fontSize: 10,
        fontWeight: 800,
        lineHeight: 1,
      }}>
        {active ? '✓' : ''}
      </span>

      <span className="sk-expiry-position" style={{ color: active ? '#b95020' : 'var(--k-ink-5)', fontSize: 9.5, fontWeight: 750, letterSpacing: '.045em', textTransform: 'uppercase' }}>
        {seriesPosition(kind, option.rank)}
      </span>

      <span className="sk-expiry-contracts" style={{ display: 'grid', gap: 5 }}>
        {option.contracts.map((contract) => (
          <span key={`${contract.owner}-${contract.expiry}`} style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', alignItems: 'baseline', gap: 8 }}>
            <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: k.text, fontSize: 11, fontWeight: 700 }}>
              {contract.owner}
              {contract.month && (
                <span style={{ marginLeft: 5, color: 'var(--k-ink-6)', fontSize: 9.5, fontWeight: 700 }}>
                  {contract.month}
                </span>
              )}
            </span>
            <time dateTime={contract.expiry} style={{ color: active ? '#b95020' : 'var(--k-ink-4)', fontSize: 10.5, fontWeight: active ? 700 : 560, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
              {contract.date}
            </time>
          </span>
        ))}
      </span>
    </button>
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
  const options = availableSeries(entries, kind, choices, asOf, collapseStocks);
  const selectedOptions = options.filter((option) => values.includes(option.rank));
  const allSelected = options.length > 0 && selectedOptions.length === options.length;

  return (
    <section aria-label={title} style={{ overflow: 'hidden', border: `1px solid ${k.border}`, borderRadius: 9, background: 'var(--k-bg)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 12px', borderBottom: options.length ? '1px solid #ededed' : 'none' }}>
        <span style={{ minWidth: 0, flex: 1 }}>
          <strong style={{ display: 'block', color: k.text, fontSize: 11.5, fontWeight: 750 }}>{title}</strong>
          <span style={{ display: 'block', marginTop: 3, color: 'var(--k-ink-6)', fontSize: 9.5, lineHeight: 1.4 }}>{description}</span>
        </span>
        {options.length > 0 && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 9, flexShrink: 0 }}>
            <span style={{ color: 'var(--k-ink-5)', fontSize: 9.5, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
              {selectedOptions.length} of {options.length}
            </span>
            {options.length > 1 && (
              <button
                className="sk-expiry-action"
                type="button"
                disabled={disabled}
                aria-label={`${allSelected ? 'Use nearest only for' : 'Select all'} ${title}`}
                onClick={() => onChange(allSelected ? [options[0].rank] : options.map((option) => option.rank))}
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

      {options.length ? (
        <div style={{ display: 'grid', background: 'var(--k-bg)' }}>
          {options.map((option) => {
            const active = values.includes(option.rank);
            return (
              <ExactExpiryCard
                key={`${kind}-${option.rank}`}
                option={option}
                kind={kind}
                active={active}
                lockSelected={active && selectedOptions.length === 1}
                disabled={disabled}
                onToggle={() => {
                  const next = active
                    ? values.filter((value) => value !== option.rank)
                    : [...new Set([...values, option.rank])];
                  onChange(next.sort((left, right) => left - right));
                }}
              />
            );
          })}
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
  return entries.filter((entry) => (
    wanted.has(entry.name.toUpperCase()) || wanted.has(entry.display_name.toUpperCase())
  ));
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
