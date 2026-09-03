import React from 'react';
import { useStockRegistry } from '../../../hooks/useSterlingKiteEngine';
import type { LiquidityGroup, Moneyness, ScanExpiry, ScanSource } from '../../../types/kiteEngine';
import {
  BORDER, CheckOption, ChoiceRow, DIM, Field, NumberField, ORANGE, ORANGE_SOFT, Switch, TEXT,
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
              border: `1px solid ${selected ? 'var(--k-border-brand)' : BORDER}`,
              background: selected ? ORANGE_SOFT : 'var(--k-bg)',
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
function StrikeGroupCard({
  group,
  strikes,
  onUpdateStrikes,
}: {
  group: { label: string; hint: string; values: Moneyness[] };
  strikes: Moneyness[];
  onUpdateStrikes: (next: Moneyness[]) => void;
}) {
  const activeCount = group.values.filter((v) => strikes.includes(v)).length;
  const isChecked = activeCount > 0;
  const maxLevels = group.values.length;

  const toggleGroup = () => {
    const next = isChecked
      ? strikes.filter((v) => !group.values.includes(v))
      : [...new Set([...strikes, ...group.values])];
    onUpdateStrikes(next.length ? next : ['ATM']);
  };

  const setLegCount = (count: number) => {
    const withoutGroup = strikes.filter((v) => !group.values.includes(v));
    const selectedLegs = group.values.slice(0, count);
    const next = [...new Set([...withoutGroup, ...selectedLegs])];
    onUpdateStrikes(next.length ? next : ['ATM']);
  };

  return (
    <div
      style={{
        padding: '9px 11px',
        border: `1px solid ${isChecked ? 'color-mix(in srgb, #2563eb 40%, transparent)' : 'var(--k-border, #e5e7eb)'}`,
        borderRadius: 8,
        background: isChecked ? 'color-mix(in srgb, #2563eb 5%, var(--k-bg))' : 'var(--k-bg)',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        transition: 'all 0.12s ease',
      }}
    >
      <div
        onClick={toggleGroup}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <span
            role="checkbox"
            aria-checked={isChecked}
            aria-label={group.label}
            style={{
              width: 16,
              height: 16,
              flexShrink: 0,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 4,
              border: isChecked ? '1px solid #2563eb' : '1px solid #d1d5db',
              background: isChecked ? '#2563eb' : 'var(--k-bg)',
              color: '#ffffff',
              fontSize: 10,
              fontWeight: 700,
              lineHeight: 1,
            }}
          >
            {isChecked ? '✓' : ''}
          </span>
          <span style={{ fontSize: 11.5, fontWeight: 700, color: isChecked ? 'var(--k-text)' : 'var(--k-ink-3)' }}>
            {group.label}
          </span>
        </div>

        <span style={{ fontSize: 9.5, fontWeight: 500, color: 'var(--k-dim)' }}>
          {group.hint}
        </span>
      </div>

      {maxLevels > 1 ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, paddingTop: 1 }}>
          <span style={{ fontSize: 9.5, fontWeight: 600, color: 'var(--k-dim)', marginRight: 2 }}>
            Legs:
          </span>
          {Array.from({ length: maxLevels }, (_, i) => i + 1).map((num) => {
            const isSelected = isChecked && activeCount === num;
            return (
              <button
                key={num}
                type="button"
                onClick={() => setLegCount(num)}
                style={{
                  padding: '2px 6px',
                  borderRadius: 4,
                  border: isSelected
                    ? '1px solid #2563eb'
                    : '1px solid var(--k-border, #e5e7eb)',
                  background: isSelected ? '#2563eb' : 'var(--k-bg)',
                  color: isSelected ? '#ffffff' : 'var(--k-ink-3)',
                  fontSize: 9.5,
                  fontWeight: isSelected ? 700 : 500,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  transition: 'all 0.12s ease',
                }}
                title={`Include ${num} leg${num === 1 ? '' : 's'} (${group.values.slice(0, num).join(', ')})`}
              >
                {num} {num === 1 ? 'leg' : 'legs'}
              </button>
            );
          })}
        </div>
      ) : (
        <div style={{ fontSize: 9.5, fontWeight: 500, color: 'var(--k-dim)', paddingTop: 1 }}>
          1 leg (ATM)
        </div>
      )}
    </div>
  );
}

export function ContractsGroup({
  strikes, indexExpiries, onChange,
  dteMin, dteMax, avoidExpiryDay, dteDefaults, dteNote,
}: {
  strikes: Moneyness[];
  indexExpiries: ScanExpiry[];
  onChange: (next: {
    strike_moneyness?: Moneyness[];
    scan_expiries_indices?: ScanExpiry[];
    expiry_dte_min?: number;
    expiry_dte_max?: number;
    avoid_expiry_day?: boolean;
  }) => void;
  dteMin?: number;
  dteMax?: number;
  avoidExpiryDay?: boolean;
  dteDefaults?: { min?: number; max?: number };
  dteNote?: React.ReactNode;
}) {
  return (
    <>
      <Field
        label="Strike range"
        hint="Select moneyness and number of legs per group"
        wide
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
            gap: 10,
            width: '100%',
          }}
        >
          {STRIKE_GROUPS.map((group) => (
            <StrikeGroupCard
              key={group.label}
              group={group}
              strikes={strikes}
              onUpdateStrikes={(next) => onChange({ strike_moneyness: next })}
            />
          ))}
        </div>
      </Field>

      <Field label="Index expiries" hint="Contract cycles scanned for indices.">
        <div style={{ display: 'flex', gap: 16 }}>
          <CheckOption
            label="Weekly"
            checked={indexExpiries.includes('weekly')}
            onChange={() => onChange({
              scan_expiries_indices: indexExpiries.includes('weekly')
                ? (indexExpiries.filter((x) => x !== 'weekly').length ? indexExpiries.filter((x) => x !== 'weekly') : ['weekly'])
                : [...indexExpiries, 'weekly'],
            })}
          />
          <CheckOption
            label="Monthly"
            checked={indexExpiries.includes('monthly')}
            onChange={() => onChange({
              scan_expiries_indices: indexExpiries.includes('monthly')
                ? (indexExpiries.filter((x) => x !== 'monthly').length ? indexExpiries.filter((x) => x !== 'monthly') : ['monthly'])
                : [...indexExpiries, 'monthly'],
            })}
          />
        </div>
      </Field>

      {dteMin !== undefined && dteMax !== undefined && (
        <ExpirySettingsGroup
          dteMin={dteMin}
          dteMax={dteMax}
          avoidExpiryDay={avoidExpiryDay}
          dteDefaults={dteDefaults}
          dteNote={dteNote}
          onChange={onChange}
        />
      )}
    </>
  );
}

export function ExpirySettingsGroup({
  dteMin, dteMax, avoidExpiryDay, dteDefaults, dteNote, onChange,
}: {
  dteMin?: number;
  dteMax?: number;
  avoidExpiryDay?: boolean;
  dteDefaults?: { min?: number; max?: number };
  dteNote?: React.ReactNode;
  onChange: (next: {
    expiry_dte_min?: number;
    expiry_dte_max?: number;
    avoid_expiry_day?: boolean;
  }) => void;
}) {
  return (
    <>
      {dteMin !== undefined && dteMax !== undefined && (
        <>
          <NumberField
            label="Minimum days to expiry"
            hint="Contracts closer to expiry than this are not eligible."
            value={dteMin} defaultValue={dteDefaults?.min}
            onChange={(v) => onChange({ expiry_dte_min: v })}
            min={0} max={365} step={1}
          />
          <NumberField
            label="Maximum days to expiry"
            hint="Contracts further out than this are not eligible."
            value={dteMax} defaultValue={dteDefaults?.max}
            onChange={(v) => onChange({ expiry_dte_max: v })}
            min={0} max={400} step={1}
          />
          <Field
            label="Expiry day"
            hint="Expiry-day options gain and lose value fastest, and their open interest is settlement mechanics rather than positioning."
          >
            <Switch
              checked={!!avoidExpiryDay}
              label="Avoid expiry-day entries"
              onChange={() => onChange({ avoid_expiry_day: !avoidExpiryDay })}
            />
          </Field>
          {dteNote && <ConfigNote>{dteNote}</ConfigNote>}
        </>
      )}
    </>
  );
}

