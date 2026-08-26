/**
 * Exact option contracts, as a settings section — for whichever engine hosts it.
 *
 * Originally SuperTrend's, and hardwired to its config. Every option strategy
 * has the same question to answer ("which listed contracts?") and stores the
 * answer under the same field names, so this is now the SAME control on each
 * page rather than one real picker and several lookalikes.
 *
 * Called with no props it still reads and writes the SuperTrend engine config,
 * which is what every existing caller expects.
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
  type ContractSelectionConfig,
} from './optionContractsMachinery';
import { k, tint } from '../../../styles/kiteUI';

function RefreshGlyph() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
      <path d="M21 12a9 9 0 1 1-2.64-6.36" /><path d="M21 3v6h-6" />
    </svg>
  );
}

export function OptionContractsPicker({ config, onSave, saving, title }: {
  /** The hosting engine's contract selection. Omit for the SuperTrend engine. */
  config?: ContractSelectionConfig | null;
  /** Persist a change. Omit to write the SuperTrend engine config. */
  onSave?: (patch: Partial<ContractSelectionConfig>) => void;
  saving?: boolean;
  title?: string;
} = {}) {
  const { data: engineCfg } = useEngineConfig();
  const calendar = useExpiryCalendar();
  const setConfig = usePatchEngineConfig();
  const runScan = useRunScan();

  const hosted = config != null;
  const cfg = (config ?? engineCfg) as ContractSelectionConfig | undefined;
  const selection = useContractSelection(hosted ? config : null);

  const save = (patch: Partial<ContractSelectionConfig>) => {
    if (!cfg) return;
    if (hosted) {
      if (!saving) onSave?.(patch);
      return;
    }
    if (setConfig.isPending) return;
    // Only the engine's own picker triggers a rescan: a hosted engine owns its
    // own scan cadence, and kicking SuperTrend's scan from another page would
    // be a side effect nobody asked for.
    setConfig.mutate(patch as Partial<EngineConfigModel>,
                     { onSuccess: () => runScan.mutate() });
  };

  if (!cfg) return null;

  const indexEntries = calendar.data ? selectedEntries(calendar.data.indices, cfg.scan_indices) : [];
  const stockEntries = calendar.data
    ? (cfg.scan_all_stocks ? calendar.data.stocks : selectedEntries(calendar.data.stocks, cfg.scan_stocks))
    : [];

  const saveState = (hosted ? saving : setConfig.isPending) ? 'Saving…'
    : (!hosted && setConfig.isError) ? 'Save failed' : null;

  return (
    <section
      aria-label="Option contract expiries"
      style={{ marginBottom: 16, padding: 18, background: k.bg, border: `1px solid ${k.border}`, borderRadius: 9 }}
    >
      <style>{CONTRACT_PICKER_CSS}</style>

      <header style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 4 }}>
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: k.text }}>{title ?? 'Option contracts'}</h3>
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
