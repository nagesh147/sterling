import React, { useState, useEffect } from 'react';
import { useBearToBearishConfig, useUpdateBearToBearishConfig } from '../../hooks/useBearToBearish';
import { ChoiceRow, Field, NumberField, Section, Switch } from './kiteSettingsPrimitives';
import { PanelCard, SettingsDraftBar } from './config/ConfigPrimitives';
import { EnginePowerHeader } from './config/EnginePowerHeader';

const ALL_INDICES = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX'];

const TIMEFRAME_OPTIONS: Array<{ value: string; label: string; hint: string }> = [
  { value: '5m', label: '5 Minute', hint: 'Primary timeframe for Lower High structure detection' },
  { value: '3m', label: '3 Minute', hint: 'Faster structure confirmation with slightly more noise' },
  { value: '1m', label: '1 Minute', hint: 'Ultra-fast intraday scalping structure' },
];

const DATA_SOURCE_OPTIONS: Array<{ value: string; label: string; hint: string }> = [
  { value: 'kite', label: 'Zerodha Kite', hint: 'Live ticks and 1-minute historical candles from Kite Connect.' },
  { value: 'truedata', label: 'TrueData', hint: 'TrueData WebSocket feed (ultra-low latency tick-by-tick).' },
];

const STRIKE_GROUPS = [
  { key: 'DEEP_ITM', label: 'Deep ITM', delta: 'δ ≈ 0.85–0.95', maxLegs: 1 },
  { key: 'ITM', label: 'ITM', delta: 'δ ≈ 0.60–0.80', maxLegs: 5 },
  { key: 'ATM', label: 'ATM', delta: 'δ ≈ 0.50', maxLegs: 1 },
  { key: 'OTM', label: 'OTM', delta: 'δ ≈ 0.20–0.40', maxLegs: 5 },
  { key: 'FAR_OTM', label: 'Far OTM', delta: 'δ ≈ 0.05–0.15', maxLegs: 1 },
] as const;

const EXPIRY_SELECTION_OPTIONS: Array<{ value: string; label: string; hint: string }> = [
  { value: 'weekly', label: 'Weekly', hint: 'Front weekly contract. Maximum gamma and fast theta.' },
  { value: 'monthly', label: 'Monthly', hint: 'Front monthly contract. Higher liquidity and slower decay.' },
];

export function BearToBearishSettingsPanel() {
  const { data: serverCfg, isLoading } = useBearToBearishConfig();
  const updateMutation = useUpdateBearToBearishConfig();

  const [draft, setDraft] = useState<Record<string, any> | null>(null);

  useEffect(() => {
    if (serverCfg && !draft) {
      setDraft(serverCfg);
    }
  }, [serverCfg]);

  if (isLoading || !draft) {
    return <div style={{ padding: 20, color: 'var(--k-dim)' }}>Loading Bear to Bearish configuration...</div>;
  }

  const dirty = JSON.stringify(draft) !== JSON.stringify(serverCfg);

  const handleApply = () => {
    updateMutation.mutate(draft);
  };

  const handleDiscard = () => {
    setDraft(serverCfg || null);
  };

  const handleReset = () => {
    const defaults = {
      enabled: true,
      pcr_threshold: 0.60,
      pcr_reversal_jump: 0.20,
      timeframe: '5m',
      auto_execute: false,
      max_risk_inr: 5000.0,
      scan_indices: ALL_INDICES,
      data_source: 'kite',
      option_moneyness: 'ATM',
      option_steps_itm: 0,
      expiry_selection: 'weekly',
      expiry_dte_min: 0,
      expiry_dte_max: 14,
      avoid_expiry_day: true,
    };
    setDraft(defaults);
    updateMutation.mutate(defaults);
  };

  const toggleIndex = (idx: string) => {
    const current: string[] = draft.scan_indices || ALL_INDICES;
    const next = current.includes(idx)
      ? current.filter((i) => i !== idx)
      : [...current, idx];
    setDraft({ ...draft, scan_indices: next });
  };

  const indicesSummary = (draft.scan_indices || ALL_INDICES).join(', ');

  return (
    <>
      <PanelCard>
        <EnginePowerHeader
          name="Bear to Bearish"
          tagline="PCR Short Momentum Engine"
          on={!!draft.enabled}
          liveOn={serverCfg?.enabled}
          busy={updateMutation.isPending}
          onToggle={() => setDraft({ ...draft, enabled: !draft.enabled })}
          runningNote="Scanning index Put-Call Ratios and lower-high candles."
          offNote="Engine is stopped. No PCR signals generated."
        />

        <Section
          title="Chart source"
          description="Which market data feed Bear to Bearish reads tick data from."
          summary={draft.data_source === 'kite' ? 'Zerodha Kite' : 'TrueData'}
          defaultOpen={true}
        >
          <Field label="Market data" hint="Feed providing index spot and option quote streams." wide>
            <ChoiceRow
              value={draft.data_source || 'kite'}
              options={DATA_SOURCE_OPTIONS}
              onChange={(v) => setDraft({ ...draft, data_source: v })}
            />
          </Field>
        </Section>

        <Section
          title="Instruments"
          description="Select which indices the engine scans for Bear to Bearish setups."
          summary={indicesSummary}
          defaultOpen={true}
        >
          <Field label="Indices" hint="Indices evaluated for PCR weakness and Lower High structure." wide>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 4 }}>
              {ALL_INDICES.map((idx) => {
                const checked = (draft.scan_indices || ALL_INDICES).includes(idx);
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => toggleIndex(idx)}
                    style={{
                      padding: '5px 12px',
                      borderRadius: 6,
                      border: `1px solid ${checked ? 'var(--k-border-brand, #2563eb)' : 'var(--k-border, #e5e7eb)'}`,
                      background: checked ? 'color-mix(in srgb, #2563eb 10%, var(--k-bg))' : 'var(--k-bg)',
                      color: checked ? '#2563eb' : 'var(--k-text)',
                      fontSize: 12,
                      fontWeight: checked ? 700 : 500,
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <span
                      aria-hidden
                      style={{
                        width: 14,
                        height: 14,
                        borderRadius: 3,
                        border: `1px solid ${checked ? '#2563eb' : 'var(--k-dim)'}`,
                        background: checked ? '#2563eb' : 'transparent',
                        color: '#ffffff',
                        fontSize: 9,
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        lineHeight: 1,
                      }}
                    >
                      {checked ? '✓' : ''}
                    </span>
                    {idx}
                  </button>
                );
              })}
            </div>
          </Field>
        </Section>

        <Section
          title="Contracts"
          description="Strike moneyness and execution legs for Put entries."
          summary={`${draft.option_moneyness || 'ATM'} · ${draft.option_steps_itm ? `${draft.option_steps_itm} legs` : '1 leg'}`}
          defaultOpen={true}
        >
          <Field label="Strike range & legs" wide>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: 10, width: '100%' }}>
              {STRIKE_GROUPS.map((g) => {
                const isSelected = (draft.option_moneyness || 'ATM') === g.key;
                return (
                  <div
                    key={g.key}
                    onClick={() => {
                      setDraft({
                        ...draft,
                        option_moneyness: g.key,
                        option_steps_itm: g.maxLegs > 1 ? (draft.option_steps_itm || 1) : 0,
                      });
                    }}
                    style={{
                      padding: '9px 11px',
                      border: `1px solid ${isSelected ? 'color-mix(in srgb, #2563eb 40%, transparent)' : 'var(--k-border, #e5e7eb)'}`,
                      borderRadius: 8,
                      background: isSelected ? 'color-mix(in srgb, #2563eb 5%, var(--k-bg))' : 'var(--k-bg)',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 6,
                      transition: 'border-color 0.15s ease, background 0.15s ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', userSelect: 'none' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                        <span
                          aria-hidden
                          style={{
                            width: 16,
                            height: 16,
                            flexShrink: 0,
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            borderRadius: 4,
                            border: `1px solid ${isSelected ? '#2563eb' : 'var(--k-dim)'}`,
                            background: isSelected ? '#2563eb' : 'transparent',
                            color: '#ffffff',
                            fontSize: 10,
                            fontWeight: 700,
                            lineHeight: 1,
                          }}
                        >
                          {isSelected ? '✓' : ''}
                        </span>
                        <span style={{ fontSize: 11.5, fontWeight: isSelected ? 700 : 500, color: 'var(--k-text)' }}>
                          {g.label}
                        </span>
                      </div>
                      <span style={{ fontSize: 9.5, fontWeight: 500, color: 'var(--k-dim)' }}>
                        {g.delta}
                      </span>
                    </div>

                    {isSelected && g.maxLegs > 1 ? (
                      <div
                        style={{ display: 'flex', gap: 4, flexWrap: 'wrap', paddingTop: 2 }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        {[1, 2, 3, 4, 5].slice(0, g.maxLegs).map((legNum) => {
                          const isLegActive = (draft.option_steps_itm ?? 1) === legNum;
                          return (
                            <button
                              key={legNum}
                              type="button"
                              onClick={() => setDraft({ ...draft, option_steps_itm: legNum })}
                              style={{
                                flex: 1,
                                minWidth: 26,
                                padding: '3px 0',
                                borderRadius: 4,
                                border: `1px solid ${isLegActive ? '#2563eb' : 'var(--k-border, #e5e7eb)'}`,
                                background: isLegActive ? '#2563eb' : 'var(--k-bg)',
                                color: isLegActive ? '#ffffff' : 'var(--k-dim)',
                                fontSize: 9.5,
                                fontWeight: isLegActive ? 700 : 500,
                                cursor: 'pointer',
                                fontFamily: 'inherit',
                                transition: 'all 0.12s ease',
                              }}
                            >
                              {legNum} {legNum === 1 ? 'leg' : 'legs'}
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                      <div style={{ fontSize: 9.5, fontWeight: 500, color: 'var(--k-dim)', paddingTop: 1 }}>
                        1 leg ({g.label})
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </Field>
        </Section>

        <Section
          title="Expiry"
          description="Rules governing contract days-to-expiry and settlement dates."
          summary={`${draft.expiry_dte_min ?? 0}–${draft.expiry_dte_max ?? 14} DTE · ${draft.expiry_selection || 'weekly'}${draft.avoid_expiry_day ? ' · avoid expiry day' : ''}`}
          defaultOpen={true}
        >
          <Field label="Expiry selection" hint="Weekly contracts provide high gamma while monthly offers liquidity." wide>
            <ChoiceRow
              value={draft.expiry_selection || 'weekly'}
              options={EXPIRY_SELECTION_OPTIONS}
              onChange={(v) => setDraft({ ...draft, expiry_selection: v })}
            />
          </Field>
          <NumberField
            label="Minimum days to expiry"
            hint="Contracts expiring sooner than this window are skipped."
            value={draft.expiry_dte_min ?? 0}
            min={0}
            max={60}
            step={1}
            suffix="days"
            onChange={(val) => setDraft({ ...draft, expiry_dte_min: val })}
          />
          <NumberField
            label="Maximum days to expiry"
            hint="Contracts with further expirations are omitted to prevent theta degradation."
            value={draft.expiry_dte_max ?? 14}
            min={0}
            max={90}
            step={1}
            suffix="days"
            onChange={(val) => setDraft({ ...draft, expiry_dte_max: val })}
          />
          <Field label="Expiry day" hint="Avoid opening positions on expiry day due to rapid theta decay and gamma spikes.">
            <Switch
              checked={draft.avoid_expiry_day !== false}
              label="Avoid expiry-day entries"
              onChange={() => setDraft({ ...draft, avoid_expiry_day: draft.avoid_expiry_day === false })}
            />
          </Field>
        </Section>

        <Section
          title="PCR & Candle Parameters"
          description="Fine-tune PCR ceiling thresholds and structure timeframe."
          summary={`PCR <= ${draft.pcr_threshold ?? 0.60}, Jump ${draft.pcr_reversal_jump ?? 0.20}, ${draft.timeframe || '5m'}`}
          defaultOpen={true}
        >
          <Field
            label="PCR Bearish Threshold"
            hint="PCR ceiling for bearish confirmation (default 0.60). Below this level, puts are heavily sold & call buyers are absent."
          >
            <NumberField
              label="PCR Bearish Threshold"
              value={draft.pcr_threshold ?? 0.60}
              step={0.05}
              min={0.30}
              max={0.90}
              onChange={(val) => setDraft({ ...draft, pcr_threshold: val })}
            />
          </Field>

          <Field
            label="PCR Invalidation Reversal Jump"
            hint="A rapid PCR spike within 5-10m window (default +0.20) invalidates armed short setups."
          >
            <NumberField
              label="PCR Invalidation Reversal Jump"
              value={draft.pcr_reversal_jump ?? 0.20}
              step={0.05}
              min={0.10}
              max={0.50}
              onChange={(val) => setDraft({ ...draft, pcr_reversal_jump: val })}
            />
          </Field>

          <Field
            label="Lower High Candle Timeframe"
            hint="Timeframe used to detect Lower High (LH) resistance structure."
          >
            <ChoiceRow
              options={TIMEFRAME_OPTIONS}
              value={draft.timeframe || '5m'}
              onChange={(tf) => setDraft({ ...draft, timeframe: tf })}
            />
          </Field>
        </Section>

        <Section
          title="Risk & Auto-Execution"
          description="Manage risk caps and automatic order routing."
          summary={`Max Risk ₹${draft.max_risk_inr ?? 5000}, Auto: ${draft.auto_execute ? 'ON' : 'OFF'}`}
          defaultOpen={true}
        >
          <Field
            label="Max INR Risk Per Trade"
            hint="Maximum INR risk threshold for 1 lot option trade allocation."
          >
            <NumberField
              label="Max INR Risk Per Trade"
              value={draft.max_risk_inr ?? 5000}
              step={500}
              min={1000}
              max={50000}
              onChange={(val) => setDraft({ ...draft, max_risk_inr: val })}
            />
          </Field>

          <Field
            label="Auto Execute Trades"
            hint="Automatically route 1-lot ATM Put option orders to broker when signal status turns ARMED."
          >
            <Switch
              checked={!!draft.auto_execute}
              label="Auto Execute Signals"
              onChange={() => setDraft({ ...draft, auto_execute: !draft.auto_execute })}
            />
          </Field>
        </Section>
      </PanelCard>

      <SettingsDraftBar
        dirty={dirty}
        saving={updateMutation.isPending}
        onApply={handleApply}
        onDiscard={handleDiscard}
        onReset={handleReset}
      />
    </>
  );
}

export default BearToBearishSettingsPanel;
