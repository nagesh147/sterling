/**
 * SuperTrend's exact option contracts, as a settings section.
 *
 * Same picker as before; it has simply moved to where every other engine
 * configures its contracts. Nothing here is a new control — the change is that
 * it no longer competes with the signal rows for the top of the board.
 */
import React from 'react';
import {
  useEngineConfig,
  useExpiryCalendar,
  useRunScan,
  usePatchEngineConfig,
} from '../../../hooks/useSterlingKiteEngine';
import type { EngineConfigModel } from '../../../types/kiteEngine';
import { formatExpiryDate } from '../expiryCalendarPresentation';
import {
  CONTRACT_PICKER_CSS, ExpiryGroup, MONTHLY_RANKS, WEEKLY_RANKS,
  selectedEntries, useContractSelection,
} from './optionContractsMachinery';
import { k, tint } from '../../../styles/kiteUI';

function RefreshGlyph() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
      <path d="M21 12a9 9 0 1 1-2.64-6.36" /><path d="M21 3v6h-6" />
    </svg>
  );
}

export function OptionContractsPicker() {
  const { data: cfg } = useEngineConfig();
  const calendar = useExpiryCalendar();
  const setConfig = usePatchEngineConfig();
  const runScan = useRunScan();
  const selection = useContractSelection();

  const save = (patch: Partial<EngineConfigModel>) => {
    if (!cfg || setConfig.isPending) return;
    setConfig.mutate(patch, { onSuccess: () => runScan.mutate() });
  };

  if (!cfg) return null;

  const indexEntries = calendar.data ? selectedEntries(calendar.data.indices, cfg.scan_indices) : [];
  const stockEntries = calendar.data
    ? (cfg.scan_all_stocks ? calendar.data.stocks : selectedEntries(calendar.data.stocks, cfg.scan_stocks))
    : [];

  const saveState = setConfig.isPending ? 'Saving…' : setConfig.isError ? 'Save failed' : null;

  return (
    <section
      aria-label="Option contract expiries"
      style={{ marginBottom: 16, padding: 18, background: k.bg, border: `1px solid ${k.border}`, borderRadius: 9 }}
    >
      <style>{CONTRACT_PICKER_CSS}</style>

      <header style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 4 }}>
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: k.text }}>Option contracts</h3>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 9.5, fontWeight: 700, color: k.green }}>
          <span aria-hidden style={{ width: 5, height: 5, borderRadius: '50%', background: k.green }} />
          Live Kite dates
        </span>
        <span style={{ fontSize: 10.5, color: k.dim, fontVariantNumeric: 'tabular-nums' }}>{selection.summary}</span>
        {saveState && (
          <span aria-live="polite" style={{ fontSize: 9.5, fontWeight: 700, color: setConfig.isError ? k.red : k.dim }}>
            {saveState}
          </span>
        )}
        {calendar.data && (
          <button
            type="button"
            aria-label="Refresh Kite contract dates"
            title="Refresh Kite contract dates"
            disabled={calendar.isFetching}
            onClick={() => calendar.refetch()}
            style={{
              marginLeft: 'auto', width: 26, height: 26, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              border: `1px solid ${k.border}`, borderRadius: 6, background: k.bg, color: k.dim,
              cursor: calendar.isFetching ? 'wait' : 'pointer',
            }}
          >
            <RefreshGlyph />
          </button>
        )}
      </header>

      <p style={{ margin: '0 0 12px', fontSize: 10.5, color: k.dim, lineHeight: 1.5 }}>
        One row is the same listed position across your selected instruments; the exact exchange date can differ
        between them. Expired contracts drop automatically, and dates are never inferred from weekdays or holidays.
      </p>

      {calendar.data && (
        <p style={{ margin: '0 0 10px', fontSize: 9.5, color: k.dim }}>
          Kite instruments · as of {formatExpiryDate(calendar.data.as_of, calendar.data.as_of)}
          {calendar.isFetching && <span aria-live="polite" style={{ marginLeft: 8, color: k.orange }}>Refreshing…</span>}
        </p>
      )}

      {calendar.isLoading && !calendar.data && (
        <p role="status" style={{ margin: 0, padding: 12, border: `1px solid ${k.border}`, borderRadius: 8, color: k.dim, fontSize: 10.5 }}>
          Loading exact dates from Kite instruments…
        </p>
      )}

      {calendar.isError && !calendar.data && (
        <div role="alert" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: 10, border: `1px solid ${tint(k.red, 34)}`, borderRadius: 8, background: tint(k.red, 7), color: k.red, fontSize: 10.5 }}>
          <span style={{ flex: 1, minWidth: 0 }}>Exact dates are unavailable. Check the Kite connection and try again.</span>
          <button
            type="button"
            onClick={() => calendar.refetch()}
            style={{ flexShrink: 0, border: `1px solid ${tint(k.red, 40)}`, borderRadius: 5, padding: '4px 8px', background: k.bg, color: k.red, fontFamily: 'inherit', fontSize: 9.5, fontWeight: 700, cursor: 'pointer' }}
          >
            Retry
          </button>
        </div>
      )}

      {calendar.data && (
        <div style={{ display: 'grid', gap: 9 }}>
          <ExpiryGroup
            title="Weekly indices"
            description="Exact weekly contracts for the selected indices."
            kind="weekly"
            choices={WEEKLY_RANKS}
            entries={indexEntries}
            asOf={calendar.data.as_of}
            values={cfg.scan_weekly_series_indices ?? WEEKLY_RANKS}
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
            values={cfg.scan_monthly_series_indices ?? MONTHLY_RANKS}
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
            values={cfg.scan_monthly_series_stocks ?? MONTHLY_RANKS}
            disabled={setConfig.isPending}
            onChange={(values) => save({ scan_monthly_series_stocks: values })}
          />
        </div>
      )}
    </section>
  );
}
