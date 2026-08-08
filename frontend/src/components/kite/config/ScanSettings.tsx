import React from 'react';
import { useStockRegistry } from '../../../hooks/useSterlingKiteEngine';
import type { Moneyness, ScanExpiry, ScanSource } from '../../../types/kiteEngine';
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
      <Field
        label="Single-stock underlyings"
        hint="Off leaves stocks out of the scan entirely. Indices are unaffected."
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <Switch
            checked={stockContracts} label={`${idPrefix} scan single-stock underlyings`}
            onChange={() => onChange({ scan_stock_contracts: !stockContracts })}
          />
          <span style={{ color: TEXT, fontSize: 12 }}>
            {stockContracts ? 'Scanning stocks' : 'Indices only'}
          </span>
        </div>
        {!stockContracts && (
          <ConfigNote>
            No stock contracts are resolved and no stock rows appear. Your stock selection is
            kept, so turning this back on restores it.
          </ConfigNote>
        )}
      </Field>
      {stockContracts && (
        <>
          <Field
            label="F&O stocks"
            hint="Use the full eligible universe, or curate a smaller list."
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
              <Switch
                checked={allStocks} label={`${idPrefix} scan all F&O stocks`}
                onChange={() => onChange({ scan_all_stocks: !allStocks })}
              />
              <span style={{ color: TEXT, fontSize: 12 }}>
                {allStocks ? 'Scan all eligible F&O stocks' : 'Curated list'}
              </span>
            </div>
          </Field>
          {!allStocks && (
            <Field label="Selected stocks" hint={`${stocks.length} selected`}>
              <div className="sk-config-check-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(118px, 1fr))', gap: 3 }}>
                {(stockRegistry ?? []).map((s) => (
                  <CheckOption
                    key={s} label={s} compact
                    checked={stocks.includes(s)}
                    onChange={() => onChange({ scan_stocks: toggle(stocks, s, []) })}
                  />
                ))}
              </div>
            </Field>
          )}
        </>
      )}
    </>
  );
}

/** Chart source — full-width horizontal strip; hint shows the selected option. */
export function SignalSourceGroup({
  value, onChange, name,
}: {
  value: ScanSource;
  onChange: (next: ScanSource) => void;
  name: string;
}) {
  const selected = SCAN_SOURCE_OPTIONS.find((o) => o.value === value);
  return (
    <Field
      label="Read from"
      hint={selected?.hint ?? 'The chart this engine takes its entry signal off.'}
      wide
    >
      <ChoiceRow
        value={value}
        options={SCAN_SOURCE_OPTIONS.map((o) => ({ value: o.value, label: o.label, hint: o.hint }))}
        onChange={onChange}
      />
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
    onChange({ scan_expiries_indices: next.length ? next : ['weekly'] });
  };

  return (
    <>
      <Field label="Strike range" hint="Which strikes are resolved for each setup. Also decides which contract an automatic BUY hits.">
        <div className="sk-config-check-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(132px, 1fr))', gap: 7 }}>
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
      <Field label="Index expiries" hint="Contract cycles scanned for indices.">
        <div className="sk-config-check-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(120px, 190px))', gap: 7 }}>
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
