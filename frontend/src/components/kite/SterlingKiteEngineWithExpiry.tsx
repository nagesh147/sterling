import React from 'react';
import { SterlingKiteEnginePane } from './SterlingKiteEnginePane';
import {
  useEngineConfig,
  useExpiryCalendar,
  useRunScan,
  usePatchEngineConfig,
} from '../../hooks/useSterlingKiteEngine';
import type {
  EngineConfigModel,
  ExpiryCalendarEntry,
  SignalChartData,
} from '../../types/kiteEngine';
import { k } from '../../styles/kiteUI';
import {
  expiryContractsForRank,
  formatExpiryDate,
  type ExpiryContractPresentation,
  type ExpirySeriesKind,
} from './expiryCalendarPresentation';

interface Props {
  onSelectSignal: (sel: { token: number; underlying: string; timestamp_ms: number }) => void;
  onOpenChart?: (
    symbol: string,
    tab: 'chart',
    trailTarget?: 'fast' | 'mid' | 'slow',
    signalData?: SignalChartData,
  ) => void;
}

interface ExpirySeriesOption {
  rank: number;
  contracts: ExpiryContractPresentation[];
}

interface ExpiryGroupStats {
  selected: number;
  total: number;
  dates: number;
}

const WEEKLY_RANKS = [0, 1, 2, 3];
const MONTHLY_RANKS = [0, 1];

const CONTRACT_PICKER_CSS = `
.sk-expiry-trigger:hover { background:#fffaf7 !important; }
.sk-expiry-trigger:focus-visible,
.sk-expiry-card:focus-visible,
.sk-expiry-action:focus-visible,
.sk-expiry-refresh:focus-visible { outline:2px solid rgba(56,126,209,.42); outline-offset:-2px; }
.sk-expiry-card:not(:disabled):not([aria-disabled="true"]):hover {
  background:#fff5f0 !important;
}
.sk-expiry-card:last-child { border-bottom:none !important; }
.sk-expiry-action:hover:not(:disabled),.sk-expiry-refresh:hover:not(:disabled) { background:#f2f2f3 !important; color:#444 !important; }
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

function availableSeries(
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

function groupStats(options: ExpirySeriesOption[], values: number[]): ExpiryGroupStats {
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
        background: active ? '#fff8f4' : '#fff',
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
        background: active ? k.orange : '#fff',
        color: '#fff',
        fontSize: 10,
        fontWeight: 800,
        lineHeight: 1,
      }}>
        {active ? '✓' : ''}
      </span>

      <span className="sk-expiry-position" style={{ color: active ? '#b95020' : '#777', fontSize: 9.5, fontWeight: 750, letterSpacing: '.045em', textTransform: 'uppercase' }}>
        {seriesPosition(kind, option.rank)}
      </span>

      <span className="sk-expiry-contracts" style={{ display: 'grid', gap: 5 }}>
        {option.contracts.map((contract) => (
          <span key={`${contract.owner}-${contract.expiry}`} style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', alignItems: 'baseline', gap: 8 }}>
            <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: k.text, fontSize: 11, fontWeight: 700 }}>
              {contract.owner}
              {contract.month && (
                <span style={{ marginLeft: 5, color: '#888', fontSize: 9.5, fontWeight: 700 }}>
                  {contract.month}
                </span>
              )}
            </span>
            <time dateTime={contract.expiry} style={{ color: active ? '#b95020' : '#666', fontSize: 10.5, fontWeight: active ? 700 : 560, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
              {contract.date}
            </time>
          </span>
        ))}
      </span>
    </button>
  );
}

function ExpiryGroup({
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
    <section aria-label={title} style={{ overflow: 'hidden', border: `1px solid ${k.border}`, borderRadius: 9, background: '#fff' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 12px', borderBottom: options.length ? '1px solid #ededed' : 'none' }}>
        <span style={{ minWidth: 0, flex: 1 }}>
          <strong style={{ display: 'block', color: k.text, fontSize: 11.5, fontWeight: 750 }}>{title}</strong>
          <span style={{ display: 'block', marginTop: 3, color: '#888', fontSize: 9.5, lineHeight: 1.4 }}>{description}</span>
        </span>
        {options.length > 0 && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 9, flexShrink: 0 }}>
            <span style={{ color: '#777', fontSize: 9.5, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
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
                  background: '#fff',
                  color: '#555',
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
        <div style={{ display: 'grid', background: '#fff' }}>
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

function selectedEntries(
  entries: ExpiryCalendarEntry[],
  selected: string[],
): ExpiryCalendarEntry[] {
  const wanted = new Set(selected.map((name) => name.trim().toUpperCase()));
  return entries.filter((entry) => (
    wanted.has(entry.name.toUpperCase()) || wanted.has(entry.display_name.toUpperCase())
  ));
}

export function SterlingKiteEngineWithExpiry(props: Props) {
  const [contractsOpen, setContractsOpen] = React.useState(false);
  const panelId = React.useId();
  const { data: cfg } = useEngineConfig();
  const calendar = useExpiryCalendar();
  const setConfig = usePatchEngineConfig();
  const runScan = useRunScan();

  const save = (patch: Partial<EngineConfigModel>) => {
    if (!cfg || setConfig.isPending) return;
    setConfig.mutate(patch, { onSuccess: () => runScan.mutate() });
  };

  const indexEntries = cfg && calendar.data
    ? selectedEntries(calendar.data.indices, cfg.scan_indices)
    : [];
  const stockEntries = cfg && calendar.data
    ? (cfg.scan_all_stocks
      ? calendar.data.stocks
      : selectedEntries(calendar.data.stocks, cfg.scan_stocks))
    : [];

  const weeklyValues = cfg?.scan_weekly_series_indices ?? WEEKLY_RANKS;
  const monthlyIndexValues = cfg?.scan_monthly_series_indices ?? MONTHLY_RANKS;
  const monthlyStockValues = cfg?.scan_monthly_series_stocks ?? MONTHLY_RANKS;

  let selectionSummary = 'Live dates from Kite instruments';
  if (calendar.isLoading && !calendar.data) selectionSummary = 'Loading Kite-listed expiries…';
  else if (calendar.isError && !calendar.data) selectionSummary = 'Contract dates unavailable';
  else if (calendar.data) {
    const weekly = groupStats(
      availableSeries(indexEntries, 'weekly', WEEKLY_RANKS, calendar.data.as_of),
      weeklyValues,
    );
    const monthlyIndices = groupStats(
      availableSeries(indexEntries, 'monthly', MONTHLY_RANKS, calendar.data.as_of),
      monthlyIndexValues,
    );
    const monthlyStocks = groupStats(
      availableSeries(stockEntries, 'monthly', MONTHLY_RANKS, calendar.data.as_of, true),
      monthlyStockValues,
    );
    const selected = weekly.selected + monthlyIndices.selected + monthlyStocks.selected;
    const total = weekly.total + monthlyIndices.total + monthlyStocks.total;
    const dates = weekly.dates + monthlyIndices.dates + monthlyStocks.dates;
    selectionSummary = total
      ? `${selected} of ${total} expiry sets · ${dates} live date${dates === 1 ? '' : 's'}`
      : 'No listed expiries in the selected universe';
  }

  const saveState = setConfig.isPending
    ? 'Saving…'
    : setConfig.isError
      ? 'Save failed'
      : null;

  return (
    <div style={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
      <style>{CONTRACT_PICKER_CSS}</style>
      {cfg && (
        <section
          aria-label="Option contract expiries"
          style={{ flexShrink: 0, borderBottom: `1px solid ${k.border}`, background: '#fff' }}
        >
          <button
            className="sk-expiry-trigger"
            type="button"
            aria-label="Manage exact option contracts"
            aria-expanded={contractsOpen}
            aria-controls={panelId}
            onClick={() => setContractsOpen((open) => !open)}
            style={{
              width: '100%',
              minHeight: 56,
              display: 'grid',
              gridTemplateColumns: '32px minmax(0, 1fr) auto',
              alignItems: 'center',
              gap: 11,
              padding: '8px 12px',
              border: 'none',
              background: contractsOpen ? '#fffaf7' : '#fff',
              color: k.text,
              textAlign: 'left',
              fontFamily: 'inherit',
              cursor: 'pointer',
            }}
          >
            <span aria-hidden style={{ width: 32, height: 32, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', borderRadius: 7, background: '#fff5f0', color: k.orange }}>
              <CalendarGlyph />
            </span>
            <span style={{ minWidth: 0 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                <strong style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: k.text, fontSize: 12, fontWeight: 760 }}>
                  Option contracts
                </strong>
                <span style={{ flexShrink: 0, display: 'inline-flex', alignItems: 'center', gap: 5, color: '#33805b', fontSize: 9, fontWeight: 700 }}>
                  <span aria-hidden style={{ width: 5, height: 5, borderRadius: '50%', background: '#4caf50' }} />Live Kite dates
                </span>
                {saveState && (
                  <span aria-live="polite" style={{ marginLeft: 'auto', color: setConfig.isError ? '#d14343' : '#777', fontSize: 9.5, fontWeight: 680 }}>
                    {saveState}
                  </span>
                )}
              </span>
              <span style={{ display: 'block', marginTop: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#888', fontSize: 10, fontVariantNumeric: 'tabular-nums' }}>
                {selectionSummary}
              </span>
            </span>
            <span aria-hidden style={{ color: k.dim, fontSize: 16, lineHeight: 1, transform: contractsOpen ? 'rotate(90deg)' : 'none', transition: 'transform .15s ease' }}>
              ›
            </span>
          </button>

          {contractsOpen && (
            <div
              className="sk-expiry-scroll"
              id={panelId}
              role="region"
              aria-label="Exact option contract picker"
              style={{ maxHeight: 'min(68vh, 620px)', overflowY: 'auto', borderTop: '1px solid #ececec', background: '#f7f7f8' }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '13px 12px 9px' }}>
                <span style={{ minWidth: 0, flex: 1 }}>
                  <strong style={{ display: 'block', color: k.text, fontSize: 12, fontWeight: 760 }}>Choose the contracts Sterling scans</strong>
                  <span style={{ display: 'block', marginTop: 4, color: '#888', fontSize: 10, lineHeight: 1.45 }}>
                    One row represents the same listed position across your selected instruments; exact exchange dates may differ.
                  </span>
                </span>
                {calendar.data && (
                  <button
                    className="sk-expiry-refresh"
                    type="button"
                    aria-label="Refresh Kite contract dates"
                    disabled={calendar.isFetching}
                    onClick={() => calendar.refetch()}
                    style={{ width: 32, height: 32, flexShrink: 0, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', border: `1px solid ${k.border}`, borderRadius: 7, background: '#fff', color: '#666', cursor: calendar.isFetching ? 'wait' : 'pointer' }}
                  >
                    <RefreshGlyph />
                  </button>
                )}
              </div>

              {calendar.data && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0 12px 11px', color: '#888', fontSize: 9.5 }}>
                  <span aria-hidden style={{ width: 5, height: 5, borderRadius: '50%', background: k.green, boxShadow: '0 0 0 2px rgba(76,175,80,.10)' }} />
                  <span>Kite instruments · as of {formatExpiryDate(calendar.data.as_of, calendar.data.as_of)}</span>
                  {calendar.isFetching && <span aria-live="polite" style={{ marginLeft: 'auto', color: k.orange }}>Refreshing…</span>}
                </div>
              )}

              {calendar.isLoading && !calendar.data && (
                <div role="status" style={{ margin: '0 10px 10px', padding: '12px', border: `1px solid ${k.border}`, borderRadius: 8, background: '#fff', color: k.dim, fontSize: 9.5 }}>
                  Loading exact dates from Kite instruments…
                </div>
              )}

              {calendar.isError && !calendar.data && (
                <div role="alert" style={{ display: 'flex', alignItems: 'center', gap: 9, margin: '0 10px 10px', padding: '10px', border: '1px solid #f0d8d5', borderRadius: 8, background: '#fff8f7', color: '#8e5550', fontSize: 9.5, lineHeight: 1.4 }}>
                  <span style={{ minWidth: 0, flex: 1 }}>Exact dates are unavailable. Check the Kite connection and try again.</span>
                  <button type="button" onClick={() => calendar.refetch()} style={{ flexShrink: 0, border: '1px solid #e3bbb6', borderRadius: 5, padding: '4px 7px', background: '#fff', color: '#a33f36', fontFamily: 'inherit', fontSize: 8.5, fontWeight: 680, cursor: 'pointer' }}>
                    Retry
                  </button>
                </div>
              )}

              {calendar.data && (
                <div style={{ display: 'grid', gap: 9, padding: '0 12px 12px' }}>
                  <ExpiryGroup
                    title="Weekly indices"
                    description="Exact weekly contracts for the selected indices."
                    kind="weekly"
                    choices={WEEKLY_RANKS}
                    entries={indexEntries}
                    asOf={calendar.data.as_of}
                    values={weeklyValues}
                    disabled={setConfig.isPending}
                    onChange={(values) => save({ scan_weekly_series_indices: values })}
                  />
                  <ExpiryGroup
                    title="Monthly indices"
                    description="Current and next listed index month."
                    kind="monthly"
                    choices={MONTHLY_RANKS}
                    entries={indexEntries}
                    asOf={calendar.data.as_of}
                    values={monthlyIndexValues}
                    disabled={setConfig.isPending}
                    onChange={(values) => save({ scan_monthly_series_indices: values })}
                  />
                  <ExpiryGroup
                    title="Monthly stocks"
                    description={`${stockEntries.length} selected F&O stock${stockEntries.length === 1 ? '' : 's'}, grouped by exact date.`}
                    kind="monthly"
                    choices={MONTHLY_RANKS}
                    entries={stockEntries}
                    asOf={calendar.data.as_of}
                    collapseStocks
                    values={monthlyStockValues}
                    disabled={setConfig.isPending}
                    onChange={(values) => save({ scan_monthly_series_stocks: values })}
                  />
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '10px 12px', borderTop: '1px solid #e7e7e7', color: '#888', fontSize: 9.5, lineHeight: 1.4 }}>
                <span aria-hidden style={{ color: '#777', fontSize: 11 }}>ⓘ</span>
                <span>Expired contracts drop automatically. Dates are never inferred from weekdays or holidays.</span>
              </div>
            </div>
          )}
        </section>
      )}
      <div style={{ flex: 1, minHeight: 0 }}>
        <SterlingKiteEnginePane {...props} />
      </div>
    </div>
  );
}

export default SterlingKiteEngineWithExpiry;
