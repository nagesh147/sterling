import React from 'react';
import { useStockRegistry } from '../../hooks/useSterlingKiteEngine';
import { useNavigatorConfig } from '../../hooks/useNavigator';
import type { Moneyness, ScanExpiry } from '../../types/kiteEngine';
import {
  BORDER, CheckOption, DIM, Field, MUTED, ORANGE, ORANGE_SOFT, Section, Switch, TEXT,
} from './kiteSettingsPrimitives';
import {
  AppliesChip, ConfigNote, NavigatorScopeChip, PanelCard,
} from './config/ConfigPrimitives';
import {
  FIELDS, INDEX_OPTIONS, SCAN_SOURCE_OPTIONS, STRIKE_GROUPS, scanSourceLabel,
} from './config/registry';
import { toggleInList, useConfigPatch } from './config/useConfigPatch';

const GREEN = '#4caf50';

/**
 * Everything that decides WHAT gets scanned and WHICH contracts are considered.
 *
 * This is the market layer rather than an engine's layer, but "both engines read
 * everything here" would be too strong and was wrong when this page first said
 * it. What is actually true, field by field:
 *
 *   • strike coverage and the expiry lists — handed to Navigator on every pass,
 *     whatever its scan scope;
 *   • the instrument universe — shared only while Navigator's scan scope is
 *     "shared" (navigator/runtime._resolve_nav_universe);
 *   • the signal source — NOT shared. Navigator carries its own `scan_source`
 *     and reads that one unconditionally.
 *
 * Each field carries a chip saying which of those it is, instead of one blanket
 * sentence that is only mostly true.
 */

/** Whether Navigator is currently following the shared INSTRUMENT UNIVERSE.
 *  It is deliberately not a claim about the whole page — the signal source is
 *  never shared, and strike/expiry coverage is shared regardless of this. */
function FollowerChips({ navigatorFollows, navigatorEnabled }: {
  navigatorFollows: boolean;
  navigatorEnabled: boolean;
}) {
  const chip = (label: string, on: boolean, note: string) => (
    <span
      key={label} title={note}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 9px', borderRadius: 20,
        fontSize: 10.5, fontWeight: 700, border: `1px solid ${on ? `${GREEN}55` : BORDER}`,
        background: on ? '#e8f5e9' : '#f6f6f7', color: on ? '#2e7d32' : DIM,
      }}
    >
      <span aria-hidden style={{ width: 5, height: 5, borderRadius: '50%', background: on ? GREEN : '#c2c2c2' }} />
      {label}
    </span>
  );
  return (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      {chip('SuperTrend', true, 'The SuperTrend engine always scans this universe.')}
      {chip(
        navigatorFollows ? 'Navigator' : 'Navigator — on its own',
        navigatorFollows,
        navigatorFollows
          ? navigatorEnabled
            ? 'Navigator is set to follow this instrument universe.'
            : 'Navigator would follow this universe, but Navigator is currently off.'
          : 'Navigator has its own universe — change it in the Value-Flow Navigator section.',
      )}
    </div>
  );
}

/** Rough cost of one scan under the current selection, so a wide universe is a
 *  visible choice rather than a surprise. */
function scanCostLine(instruments: number, strikes: number, source: string): string {
  const charts = instruments * strikes * 2; // CE + PE per strike per instrument
  const secs = (n: number) => {
    const s = Math.round(n / 3); // the backend paces at roughly 3 historical requests/second
    return s < 90 ? `~${s}s` : `~${Math.round(s / 60)} min`;
  };
  if (source === 'spot') return `${instruments} spot charts · ${secs(instruments)} per scan`;
  if (source === 'derivatives') return `${charts} option charts · ${secs(charts)} per scan`;
  if (source === 'confluence') {
    const premiums = instruments * strikes;
    return `${instruments} spot + up to ${premiums} premium charts · ${secs(instruments + premiums)} per scan`;
  }
  return `${instruments} spot + ${charts} option charts · ${secs(instruments + charts)} per scan`;
}

export function MarketContractsPanel() {
  const { cfg, patch, saving } = useConfigPatch();
  const { data: navData } = useNavigatorConfig();
  const { data: stockRegistry } = useStockRegistry();

  if (!cfg) {
    return <div style={{ padding: 18, color: DIM, fontSize: 12 }}>Loading market setup…</div>;
  }

  const navCfg = navData?.record.config;
  const navigatorFollows = (navCfg?.scan_scope_mode ?? 'shared') === 'shared';
  const navigatorEnabled = !!navCfg?.enabled;

  const indexExpiries = cfg.scan_expiries_indices ?? cfg.scan_expiries;
  const strikeCount = Math.max(1, cfg.strike_moneyness.length);
  const instrumentCount = cfg.scan_indices.length + (cfg.scan_all_stocks ? 0 : cfg.scan_stocks.length);

  const toggleStrikeGroup = (values: Moneyness[]) => {
    const allSelected = values.every((value) => cfg.strike_moneyness.includes(value));
    const next = allSelected
      ? cfg.strike_moneyness.filter((value) => !values.includes(value))
      : [...new Set([...cfg.strike_moneyness, ...values])];
    patch({ strike_moneyness: next.length ? next : ['ATM'] }, 'strike_moneyness');
  };

  return (
    <PanelCard>
      <div style={{ padding: '16px 18px', borderBottom: `1px solid ${BORDER}` }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ color: TEXT, fontSize: 14.5, fontWeight: 800 }}>Market &amp; contracts</div>
            <div style={{ color: MUTED, fontSize: 11.5, lineHeight: 1.55, margin: '3px 0 10px' }}>
              What gets scanned and which contracts are considered. Most of this is shared with
              the Value-Flow Navigator, so it is set once here rather than configured twice — but
              not all of it, so each setting says who reads it.
            </div>
          </div>
          <span aria-live="polite" style={{
            display: 'inline-flex', alignItems: 'center', gap: 6, flexShrink: 0,
            color: saving ? MUTED : GREEN, fontSize: 10.5, fontWeight: 700,
          }}>
            <span aria-hidden style={{ width: 6, height: 6, borderRadius: '50%', background: saving ? '#c2c2c2' : GREEN }} />
            {saving ? 'Saving…' : 'Saved'}
          </span>
        </div>
        <FollowerChips navigatorFollows={navigatorFollows} navigatorEnabled={navigatorEnabled} />
        {!navigatorFollows && (
          <div style={{
            marginTop: 10, padding: '8px 11px', borderRadius: 7, background: '#f6f6f7',
            border: `1px solid ${BORDER}`, color: MUTED, fontSize: 10.5, lineHeight: 1.5,
          }}>
            Navigator is currently set to its own universe, so the <b>Instruments</b> list below
            applies to SuperTrend only. Strike coverage and the expiry cycles still reach Navigator
            either way. Switch it back under <b>Value-Flow Navigator → What Navigator scans</b> if
            you want the instrument lists to move together again.
          </div>
        )}
        <div style={{ marginTop: 10, color: DIM, fontSize: 10.5 }}>
          {cfg.scan_all_stocks
            ? `${cfg.scan_indices.length} indices + all eligible F&O stocks`
            : scanCostLine(instrumentCount, strikeCount, cfg.scan_source)}
        </div>
      </div>

      <Section
        title="Where a signal comes from"
        description="Which chart a SuperTrend setup is read from. Navigator has its own."
        summary={scanSourceLabel(cfg.scan_source)}
        defaultOpen
      >
        <Field
          label={FIELDS.scan_source.label}
          hint={FIELDS.scan_source.help}
          badge={<>
            <AppliesChip applies={FIELDS.scan_source.applies} evidence={FIELDS.scan_source.evidence} />
            <NavigatorScopeChip scope={FIELDS.scan_source.navigator!} navigatorFollowsUniverse={navigatorFollows} />
          </>}
        >
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(165px, 1fr))', gap: 8 }}>
            {SCAN_SOURCE_OPTIONS.map((option) => {
              const selected = cfg.scan_source === option.value;
              return (
                <label key={option.value} style={{
                  minHeight: 58, display: 'grid', gridTemplateColumns: '17px minmax(0, 1fr)',
                  alignItems: 'start', gap: 9, textAlign: 'left', padding: '10px 11px', borderRadius: 7,
                  cursor: 'pointer', fontFamily: 'inherit', boxSizing: 'border-box',
                  border: `1px solid ${selected ? '#e2b6a4' : BORDER}`,
                  background: selected ? ORANGE_SOFT : '#fff',
                }}>
                  <input
                    type="radio" name="market-signal-source" checked={selected}
                    onChange={() => patch({ scan_source: option.value }, 'scan_source',
                      `Signal source changed to ${option.label}`)}
                    style={{ width: 15, height: 15, margin: '1px 0 0', accentColor: ORANGE }}
                  />
                  <span>
                    <span style={{ display: 'block', color: TEXT, fontSize: 11.5, fontWeight: 700 }}>{option.label}</span>
                    <span style={{ display: 'block', color: DIM, fontSize: 9.5, lineHeight: 1.35, marginTop: 3 }}>{option.hint}</span>
                  </span>
                </label>
              );
            })}
          </div>
        </Field>
      </Section>

      <Section
        title="Instruments"
        description="The indices and F&O stocks included in every scan."
        summary={cfg.scan_all_stocks
          ? `All F&O · ${cfg.scan_indices.length} indices`
          : `${cfg.scan_stocks.length} stocks · ${cfg.scan_indices.length} indices`}
        defaultOpen
      >
        <Field
          label={FIELDS.scan_indices.label}
          badge={<>
            <AppliesChip applies={FIELDS.scan_indices.applies} evidence={FIELDS.scan_indices.evidence} />
            <NavigatorScopeChip scope={FIELDS.scan_indices.navigator!} navigatorFollowsUniverse={navigatorFollows} />
          </>}
        >
          <div className="sk-config-check-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 7 }}>
            {INDEX_OPTIONS.map((option) => (
              <CheckOption
                key={option.value} label={option.label}
                checked={cfg.scan_indices.includes(option.value)}
                onChange={() => patch(
                  { scan_indices: toggleInList(cfg.scan_indices, option.value, ['NIFTY 50']) },
                  'scan_indices', 'Index universe updated',
                )}
              />
            ))}
          </div>
        </Field>
        <Field
          label={FIELDS.scan_stocks.label}
          hint={FIELDS.scan_all_stocks.help}
          badge={<>
            <AppliesChip applies={FIELDS.scan_stocks.applies} evidence={FIELDS.scan_stocks.evidence} />
            <NavigatorScopeChip scope={FIELDS.scan_stocks.navigator!} navigatorFollowsUniverse={navigatorFollows} />
          </>}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <Switch
              checked={cfg.scan_all_stocks} label="Scan all F&O stocks"
              onChange={() => patch({ scan_all_stocks: !cfg.scan_all_stocks }, 'scan_all_stocks',
                `All F&O stocks ${!cfg.scan_all_stocks ? 'enabled' : 'disabled'}`)}
            />
            <span style={{ color: TEXT, fontSize: 12 }}>Scan all eligible F&amp;O stocks</span>
          </div>
        </Field>
        {!cfg.scan_all_stocks && (
          <Field label="Selected stocks" hint={`${cfg.scan_stocks.length} selected`}>
            <div style={{ maxHeight: 260, overflow: 'auto', paddingRight: 4 }}>
              {(stockRegistry ?? []).map((group) => (
                <div key={group.liquidity} style={{ marginBottom: 10 }}>
                  <div style={{ color: DIM, fontSize: 9, fontWeight: 700, letterSpacing: .5, marginBottom: 5 }}>
                    {group.liquidity.toUpperCase()}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(118px, 1fr))', gap: 3 }}>
                    {group.stocks.map((stock) => (
                      <CheckOption
                        key={stock.name} label={stock.label || stock.name} compact
                        checked={cfg.scan_stocks.includes(stock.name)}
                        onChange={() => patch(
                          { scan_stocks: toggleInList(cfg.scan_stocks, stock.name, []) },
                          'scan_stocks',
                          `${stock.name} ${cfg.scan_stocks.includes(stock.name) ? 'removed' : 'added'}`,
                        )}
                      />
                    ))}
                  </div>
                </div>
              ))}
              {!stockRegistry?.length && <div style={{ color: DIM, fontSize: 11 }}>Stock universe unavailable.</div>}
            </div>
          </Field>
        )}
      </Section>

      <Section
        title="Contracts"
        description="Which strikes and expiry cycles are resolved for each setup."
        summary={`${strikeCount} strike${strikeCount === 1 ? '' : 's'} · ${indexExpiries.join(' + ')}`}
      >
        <Field
          label={FIELDS.strike_moneyness.label}
          hint={FIELDS.strike_moneyness.help}
          badge={<>
            <AppliesChip applies={FIELDS.strike_moneyness.applies} evidence={FIELDS.strike_moneyness.evidence} />
            <NavigatorScopeChip scope={FIELDS.strike_moneyness.navigator!} navigatorFollowsUniverse={navigatorFollows} />
          </>}
        >
          <div className="sk-config-check-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(132px, 1fr))', gap: 7 }}>
            {STRIKE_GROUPS.map((group) => {
              const count = group.values.filter((value) => cfg.strike_moneyness.includes(value)).length;
              return (
                <CheckOption
                  key={group.label} label={group.label} hint={group.hint}
                  checked={count === group.values.length}
                  indeterminate={count > 0 && count < group.values.length}
                  onChange={() => toggleStrikeGroup(group.values)}
                />
              );
            })}
          </div>
          <ConfigNote>
            An automatic BUY takes the leg nearest spot from exactly these strikes, so this is not
            only a view filter — it decides which contract the engine trades.
          </ConfigNote>
        </Field>
        <Field
          label={FIELDS.scan_expiries_indices.label}
          hint={FIELDS.scan_expiries_indices.help}
          badge={<>
            <AppliesChip applies={FIELDS.scan_expiries_indices.applies} evidence={FIELDS.scan_expiries_indices.evidence} />
            <NavigatorScopeChip scope={FIELDS.scan_expiries_indices.navigator!} navigatorFollowsUniverse={navigatorFollows} />
          </>}
        >
          <div className="sk-config-check-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(120px, 190px))', gap: 7 }}>
            {(['weekly', 'monthly'] as ScanExpiry[]).map((expiry) => (
              <CheckOption
                key={expiry} label={expiry === 'weekly' ? 'Weekly' : 'Monthly'}
                checked={indexExpiries.includes(expiry)}
                onChange={() => patch(
                  { scan_expiries_indices: toggleInList(indexExpiries, expiry, ['weekly', 'monthly']) },
                  'scan_expiries_indices', 'Index expiries updated',
                )}
              />
            ))}
          </div>
        </Field>
        <Field label="Stock expiries" hint="Not a choice — an exchange constraint.">
          <ConfigNote>
            Individual-stock derivatives are listed monthly only, so stock contracts are always
            scanned on the monthly cycle. There is nothing to configure here; this used to be shown
            as a permanently-ticked checkbox, which read like a setting you had turned on.
          </ConfigNote>
        </Field>
      </Section>
    </PanelCard>
  );
}

export default MarketContractsPanel;
