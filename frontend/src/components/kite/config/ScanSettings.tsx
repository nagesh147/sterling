import React from 'react';
import { useStockRegistry } from '../../../hooks/useSterlingKiteEngine';
import type { Moneyness, ScanExpiry, ScanSource } from '../../../types/kiteEngine';
import {
  BORDER, CheckOption, DIM, Field, ORANGE, ORANGE_SOFT, Switch, TEXT,
} from '../kiteSettingsPrimitives';
import { ConfigNote } from './ConfigPrimitives';
import { INDEX_OPTIONS, SCAN_SOURCE_OPTIONS, STRIKE_GROUPS } from './registry';

/**
 * The scan controls, rendered from plain values so BOTH engines can own a copy.
 *
 * These used to live on a single "Market & Contracts" page that claimed both
 * engines read everything on it. They do not: Navigator has its own signal
 * source, its own instrument universe, and now its own contract coverage. A
 * page that presents one set of values as universal cannot express "SuperTrend
 * on the full ladder, Navigator on ATM only", which is a reasonable thing to
 * want from two engines that look for different things.
 *
 * So the controls are engine-agnostic components, and each engine's page owns
 * the values it passes in.
 */

/** Which instruments an engine scans. */
export function InstrumentsGroup({ indices, stocks, allStocks, onChange, idPrefix, allowEmptyIndices = false }: {
  indices: string[];
  stocks: string[];
  allStocks: boolean;
  onChange: (next: { scan_indices?: string[]; scan_stocks?: string[]; scan_all_stocks?: boolean }) => void;
  idPrefix: string;
  /**
   * Whether every index may be unticked.
   *
   * SuperTrend keeps a fallback so it can never end up scanning nothing.
   * Navigator's own scope legitimately allows an indices-empty, stocks-only
   * universe — and its panel already warns and blocks Apply on a fully empty
   * one — so a silent fallback there would fight the user.
   */
  allowEmptyIndices?: boolean;
}) {
  const { data: stockRegistry } = useStockRegistry();

  const toggle = <T extends string>(current: T[], value: T, fallback: T[]): T[] => {
    const next = current.includes(value) ? current.filter((x) => x !== value) : [...current, value];
    return next.length ? next : fallback;
  };

  return (
    <>
      <Field label="Indices">
        <div className="sk-config-check-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 7 }}>
          {INDEX_OPTIONS.map((option) => (
            <CheckOption
              key={option.value} label={option.label}
              checked={indices.includes(option.value)}
              onChange={() => onChange({
                scan_indices: toggle(indices, option.value, allowEmptyIndices ? [] : ['NIFTY 50']),
              })}
            />
          ))}
        </div>
      </Field>
      <Field label="F&O stocks" hint="Use the full eligible universe, or curate a smaller list.">
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <Switch
            checked={allStocks} label={`${idPrefix} scan all F&O stocks`}
            onChange={() => onChange({ scan_all_stocks: !allStocks })}
          />
          <span style={{ color: TEXT, fontSize: 12 }}>Scan all eligible F&amp;O stocks</span>
        </div>
      </Field>
      {!allStocks && (
        <Field label="Selected stocks" hint={`${stocks.length} selected`}>
          <div style={{ maxHeight: 240, overflow: 'auto', paddingRight: 4 }}>
            {(stockRegistry ?? []).map((group, groupIndex) => (
              <div key={group.liquidity ?? groupIndex} style={{ marginBottom: 10 }}>
                <div style={{ color: DIM, fontSize: 9, fontWeight: 700, letterSpacing: .5, marginBottom: 5 }}>
                  {(group.liquidity ?? '').toUpperCase()}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(118px, 1fr))', gap: 3 }}>
                  {group.stocks.map((stock) => (
                    <CheckOption
                      key={stock.name} label={stock.label || stock.name} compact
                      checked={stocks.includes(stock.name)}
                      onChange={() => onChange({ scan_stocks: toggle(stocks, stock.name, []) })}
                    />
                  ))}
                </div>
              </div>
            ))}
            {!stockRegistry?.length && <div style={{ color: DIM, fontSize: 11 }}>Stock universe unavailable.</div>}
          </div>
        </Field>
      )}
    </>
  );
}

/** Which chart this engine reads a signal from. */
export function SignalSourceGroup({ value, onChange, name }: {
  value: ScanSource;
  onChange: (next: ScanSource) => void;
  /** Radio-group name — must differ per engine so the two do not share state. */
  name: string;
}) {
  return (
    <Field label="Read from" hint="The chart this engine takes its entry signal off.">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(165px, 1fr))', gap: 8 }}>
        {SCAN_SOURCE_OPTIONS.map((option) => {
          const selected = value === option.value;
          return (
            <label key={option.value} style={{
              minHeight: 58, display: 'grid', gridTemplateColumns: '17px minmax(0, 1fr)',
              alignItems: 'start', gap: 9, textAlign: 'left', padding: '10px 11px', borderRadius: 7,
              cursor: 'pointer', fontFamily: 'inherit', boxSizing: 'border-box',
              border: `1px solid ${selected ? '#e2b6a4' : BORDER}`,
              background: selected ? ORANGE_SOFT : '#fff',
            }}>
              <input
                type="radio" name={name} checked={selected}
                onChange={() => onChange(option.value)}
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
  );
}

/** Which strikes and expiry cycles this engine resolves. */
export function ContractsGroup({ strikes, indexExpiries, stockContracts, onChange }: {
  strikes: Moneyness[];
  indexExpiries: ScanExpiry[];
  /** Whether single-stock underlyings are scanned at all. */
  stockContracts: boolean;
  onChange: (next: {
    strike_moneyness?: Moneyness[];
    scan_expiries_indices?: ScanExpiry[];
    scan_stock_contracts?: boolean;
  }) => void;
}) {
  const toggleStrikeGroup = (values: Moneyness[]) => {
    const all = values.every((v) => strikes.includes(v));
    const next = all ? strikes.filter((v) => !values.includes(v)) : [...new Set([...strikes, ...values])];
    onChange({ strike_moneyness: next.length ? next : ['ATM'] });
  };
  const toggleIndexExpiry = (expiry: ScanExpiry) => {
    const next = indexExpiries.includes(expiry)
      ? indexExpiries.filter((x) => x !== expiry)
      : [...indexExpiries, expiry];
    onChange({ scan_expiries_indices: next.length ? next : ['weekly', 'monthly'] });
  };

  return (
    <>
      <Field label="Strike coverage" hint="Which strikes are resolved for each setup. An automatic BUY takes the leg nearest spot from exactly these.">
        <div className="sk-config-check-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(132px, 1fr))', gap: 7 }}>
          {STRIKE_GROUPS.map((group) => {
            const count = group.values.filter((v) => strikes.includes(v)).length;
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
      </Field>
      <Field label="Index expiries" hint="Contract cycles scanned for indices.">
        <div className="sk-config-check-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(120px, 190px))', gap: 7 }}>
          {(['weekly', 'monthly'] as ScanExpiry[]).map((expiry) => (
            <CheckOption
              key={expiry} label={expiry === 'weekly' ? 'Weekly' : 'Monthly'}
              checked={indexExpiries.includes(expiry)}
              onChange={() => toggleIndexExpiry(expiry)}
            />
          ))}
        </div>
      </Field>
      <Field
        label="Stock contracts"
        hint="Single-stock contracts are exchange-listed on a monthly cycle only, so the cycle is not a choice — whether to scan them at all is."
      >
        <div className="sk-config-check-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(120px, 190px))', gap: 7 }}>
          <CheckOption
            label="Monthly"
            hint={stockContracts ? 'Scanning single-stock contracts' : 'Stocks are excluded from the scan'}
            checked={stockContracts}
            onChange={() => onChange({ scan_stock_contracts: !stockContracts })}
          />
        </div>
        {!stockContracts && (
          <ConfigNote>
            Single-stock underlyings are left out of the scan entirely — no stock contracts and no
            stock rows. Your stock selection under <b>Instruments</b> is kept, so ticking this back
            on restores it. Indices are unaffected.
          </ConfigNote>
        )}
      </Field>
    </>
  );
}
