import React from 'react';
import { useStockRegistry } from '../../../hooks/useSterlingKiteEngine';
import type { LiquidityGroup, Moneyness, ScanExpiry, ScanSource } from '../../../types/kiteEngine';
import {
  BORDER, CheckOption, ChoiceRow, DIM, Field, ORANGE, ORANGE_SOFT, Switch, TEXT,
} from '../kiteSettingsPrimitives';
import { ConfigNote } from './ConfigPrimitives';
import { FIELDS, INDEX_OPTIONS, SCAN_SOURCE_OPTIONS, STRIKE_GROUPS } from './registry';

/**
 * The scan controls, rendered from plain values so BOTH engines can own a copy.
 */

/** Which instruments an engine scans. */
export function InstrumentsGroup({
  indices, stocks, allStocks, stockContracts, onChange, idPrefix, allowEmptyIndices = false,
}: {
  indices: string[];
  stocks: string[];
  allStocks: boolean;
  stockContracts: boolean;
  onChange: (next: {
    scan_indices?: string[];
    scan_stocks?: string[];
    scan_all_stocks?: boolean;
    scan_stock_contracts?: boolean;
  }) => void;
  idPrefix: string;
  allowEmptyIndices?: boolean;
}) {
  const { data: stockRegistry } = useStockRegistry();

  const toggle = <T extends string>(current: T[], value: T, fallback: T[]): T[] => {
    const next = current.includes(value) ? current.filter((x) => x !== value) : [...current, value];
    return next.length ? next : fallback;
  };

  return (
    <>
      <Field label="Indices" wide>
        <div
          className="sk-config-check-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
            gap: '6px 12px',
            width: '100%',
          }}
        >
          {INDEX_OPTIONS.map((option) => (
            <CheckOption
              key={option.value}
              label={option.label}
              checked={indices.includes(option.value)}
              onChange={() => onChange({
                scan_indices: toggle(indices, option.value, allowEmptyIndices ? [] : ['NIFTY 50']),
              })}
            />
          ))}
        </div>
      </Field>

      <Field
        label="Single-stock underlyings"
        hint="Off leaves stocks out of the scan entirely. Indices are unaffected."
      >
        <Switch
          checked={stockContracts}
          label={`${idPrefix} scan single-stock underlyings`}
          onChange={() => onChange({ scan_stock_contracts: !stockContracts })}
        />
      </Field>

      {!stockContracts && (
        <ConfigNote>
          No stock contracts are resolved and no stock rows appear. Your stock selection is
          kept, so turning this back on restores it.
        </ConfigNote>
      )}

      {stockContracts && (
        <Field
          label="F&O stocks"
          hint="Use the full eligible universe, or curate a smaller list."
        >
          <Switch
            checked={allStocks}
            label={`${idPrefix} scan all F&O stocks`}
            onChange={() => onChange({ scan_all_stocks: !allStocks })}
          />
        </Field>
      )}

      {stockContracts && !allStocks && (
        <Field label="Selected stocks" hint={`${stocks.length} selected`} wide>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, width: '100%' }}>
            {(stockRegistry ?? []).map((group: LiquidityGroup) => (
              <div key={group.liquidity}>
                <div style={{
                  color: DIM, fontSize: 10, fontWeight: 700, letterSpacing: 0.4,
                  marginBottom: 4, textTransform: 'uppercase' as const,
                }}>
                  {group.liquidity}
                </div>
                <div
                  className="sk-config-check-grid"
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))',
                    gap: '2px 8px',
                  }}
                >
                  {group.stocks.map((s) => {
                    const name = s.name;
                    return (
                      <CheckOption
                        key={name}
                        label={s.label || name}
                        compact
                        checked={stocks.includes(name)}
                        onChange={() => onChange({ scan_stocks: toggle(stocks, name, []) })}
                      />
                    );
                  })}
                </div>
              </div>
            ))}
            {!stockRegistry?.length && (
              // Without this, a failed or empty registry renders an empty box that
              // reads as "no stocks are eligible" rather than "we could not load
              // the list" — and the user curates a scope from nothing.
              <div style={{ color: DIM, fontSize: 11 }}>Stock universe unavailable.</div>
            )}
          </div>
        </Field>
      )}
    </>
  );
}


/** Which chart this engine reads a signal from (main-branch descriptions + tile style). */
export function SignalSourceGroup({ value, onChange, name, fieldHint = 'The chart this engine takes its entry signal off.' }: {
  value: ScanSource;
  onChange: (next: ScanSource) => void;
  name: string;
  fieldHint?: string | null;
}) {
  return (
    <Field label="Read from" hint={fieldHint ?? undefined} wide>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(165px, 1fr))', gap: 8, width: '100%' }}>
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
export function ContractsGroup({ strikes, indexExpiries, onChange }: {
  strikes: Moneyness[];
  indexExpiries: ScanExpiry[];
  onChange: (next: {
    strike_moneyness?: Moneyness[];
    scan_expiries_indices?: ScanExpiry[];
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
    // Falling back to BOTH, not to weekly. Unticking your last remaining cycle is
    // "I did not mean to leave this empty", not "put me on weeklies" — and weekly
    // and monthly contracts do not behave alike, so silently moving someone from
    // one to the other is a real change of position dressed as a no-op.
    onChange({ scan_expiries_indices: next.length ? next : ['weekly', 'monthly'] });
  };

  return (
    <>
      <Field
        label="Strike range"
        hint="Which strikes are resolved for each setup. Also decides which contract an automatic BUY hits."
        wide
      >
        <div
          className="sk-config-check-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(5, minmax(0, 1fr))',
            gap: '8px 10px',
            width: '100%',
          }}
        >
          {STRIKE_GROUPS.map((group) => {
            const checked = group.values.every((v) => strikes.includes(v));
            const partial = !checked && group.values.some((v) => strikes.includes(v));
            return (
              <CheckOption
                key={group.label}
                label={group.label}
                hint={group.hint}
                checked={checked}
                indeterminate={partial}
                onChange={() => toggleStrikeGroup(group.values)}
              />
            );
          })}
        </div>
      </Field>

      <Field label="Index expiries" hint="Contract cycles scanned for indices." wide>
        <div
          className="sk-config-check-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
            gap: '6px 12px',
            maxWidth: 320,
          }}
        >
          {(['weekly', 'monthly'] as ScanExpiry[]).map((expiry) => (
            <CheckOption
              key={expiry}
              label={expiry === 'weekly' ? 'Weekly' : 'Monthly'}
              checked={indexExpiries.includes(expiry)}
              onChange={() => toggleIndexExpiry(expiry)}
            />
          ))}
        </div>
      </Field>

      <ConfigNote>
        Single-stock contracts are exchange-listed on a monthly cycle only, so there is no cycle to choose.
        Whether stocks are scanned at all is under Instruments.
      </ConfigNote>
    </>
  );
}

