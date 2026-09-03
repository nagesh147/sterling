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
          title="Target Index Universe"
          description="Select which indices the engine scans for Bear to Bearish setups."
          summary={indicesSummary}
          defaultOpen={true}
        >
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 8 }}>
            {ALL_INDICES.map((idx) => {
              const checked = (draft.scan_indices || ALL_INDICES).includes(idx);
              return (
                <label
                  key={idx}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: 'pointer',
                    color: 'var(--k-text)',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleIndex(idx)}
                    style={{ accentColor: 'var(--k-orange)', width: 15, height: 15 }}
                  />
                  {idx}
                </label>
              );
            })}
          </div>
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
