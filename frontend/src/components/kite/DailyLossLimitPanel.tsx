import React from 'react';
import {
  BORDER, Field, MUTED, Section, Switch, TEXT, inputStyle,
} from './kiteSettingsPrimitives';
import { ConfigNote, PanelCard } from './config/ConfigPrimitives';
import {
  useClearDailyLossLimit, useDailyLossLimit, useSetDailyLossLimit,
} from '../../hooks/useDailyLossLimit';

/**
 * The account's daily-loss breaker.
 *
 * One pair of thresholds used to serve the whole process, nothing in the app
 * ever set them, and no screen showed them — so every account halted at the
 * shipped ₹1,500 whatever its size, and the first anyone knew of it was an
 * order coming back 423.
 *
 * Both numbers are entered as a positive rupee amount and stored negative. A
 * loss is what the field is for, and asking someone to type a minus sign in
 * front of a limit is how you end up with a limit of +1500 that can never
 * trigger.
 */
const inr = (n: number) => `₹${Math.abs(n).toLocaleString('en-IN')}`;

export function DailyLossLimitPanel() {
  const { data, isLoading } = useDailyLossLimit();
  const save = useSetDailyLossLimit();
  const clear = useClearDailyLossLimit();

  // A draft, so a half-typed number never round-trips to the breaker.
  const [draft, setDraft] = React.useState<{ warn: string; halt: string } | null>(null);
  React.useEffect(() => { setDraft(null); }, [data?.soft_warn_inr, data?.hard_halt_inr]);

  if (isLoading || !data) {
    return <PanelCard><div style={{ color: MUTED, fontSize: 11.5, padding: '10px 0' }}>Loading…</div></PanelCard>;
  }

  const warn = draft ? draft.warn : String(Math.abs(data.soft_warn_inr));
  const halt = draft ? draft.halt : String(Math.abs(data.hard_halt_inr));
  const warnNum = Number(warn);
  const haltNum = Number(halt);
  const valid = Number.isFinite(warnNum) && Number.isFinite(haltNum)
    && warnNum > 0 && haltNum > 0 && haltNum >= warnNum;
  const dirty = draft != null
    && (warnNum !== Math.abs(data.soft_warn_inr) || haltNum !== Math.abs(data.hard_halt_inr));

  const levelColour = data.level === 'halt' ? 'var(--k-red)'
    : data.level === 'warning' ? 'var(--k-orange)' : MUTED;

  const apply = (over: Partial<{ enabled: boolean }> = {}) => {
    save.mutate({
      enabled: over.enabled ?? data.enabled,
      soft_warn_inr: -Math.abs(warnNum),
      hard_halt_inr: -Math.abs(haltNum),
    });
  };

  return (
    <PanelCard>
      <Section
        title="Daily loss limit"
        description="Stops this account opening new positions once the day's realised loss reaches the halt figure."
        summary={data.enabled ? `Halt at ${inr(data.hard_halt_inr)}` : 'Off'}
        defaultOpen
        persistKey="daily-loss"
      >
        <Field
          label="Breaker"
          hint="Off means no loss figure stops a new entry. The kill switch is separate and always applies."
        >
          <Switch
            checked={data.enabled}
            label={data.enabled ? 'Armed' : 'Off'}
            onChange={() => apply({ enabled: !data.enabled })}
          />
        </Field>

        <Field label="Warn at" hint="Colours the readout. Places no order and blocks nothing.">
          <input
            type="number" min={1} step={100} value={warn} style={inputStyle}
            data-testid="daily-loss-warn"
            onChange={(e) => setDraft({ warn: e.target.value, halt })}
          />
        </Field>

        <Field
          label="Halt at"
          hint="A realised loss this size stops every engine and every manual entry for the rest of the session."
        >
          <input
            type="number" min={1} step={100} value={halt} style={inputStyle}
            data-testid="daily-loss-halt"
            onChange={(e) => setDraft({ warn, halt: e.target.value })}
          />
        </Field>

        {!valid && (
          <ConfigNote>
            Both figures are a loss, so both must be above zero, and the halt cannot be
            smaller than the warning — otherwise it would halt before it ever warned.
          </ConfigNote>
        )}

        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
          padding: '10px 0', borderTop: `1px solid ${BORDER}`, marginTop: 4,
        }}>
          <button
            type="button" disabled={!dirty || !valid || save.isPending}
            onClick={() => apply()}
            style={{
              padding: '6px 14px', fontSize: 11.5, fontWeight: 700, fontFamily: 'inherit',
              borderRadius: 6, border: `1px solid ${dirty && valid ? 'var(--k-brand)' : BORDER}`,
              background: 'transparent', color: dirty && valid ? 'var(--k-brand)' : MUTED,
              cursor: dirty && valid ? 'pointer' : 'default',
            }}
          >
            {save.isPending ? 'Saving…' : 'Apply'}
          </button>
          {data.is_account_override && (
            <button
              type="button" onClick={() => clear.mutate()} disabled={clear.isPending}
              style={{
                padding: '6px 14px', fontSize: 11.5, fontWeight: 600, fontFamily: 'inherit',
                borderRadius: 6, border: `1px solid ${BORDER}`, background: 'transparent',
                color: MUTED, cursor: 'pointer',
              }}
            >
              Use the default
            </button>
          )}
          <span style={{ color: MUTED, fontSize: 10.5, marginLeft: 'auto' }}>
            {data.is_account_override
              ? 'This account has its own limit.'
              : `On the shared default, ${inr(data.default.hard_halt_inr)}.`}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, padding: '2px 0' }}>
          <span style={{ color: MUTED, fontSize: 10.5 }}>Realised today</span>
          <span style={{ color: data.pnl_inr < 0 ? levelColour : TEXT, fontSize: 12, fontWeight: 700 }}>
            {data.pnl_inr < 0 ? `−${inr(data.pnl_inr)}` : inr(data.pnl_inr)}
          </span>
          {data.enabled && data.level !== 'clear' && (
            <span style={{ color: levelColour, fontSize: 10.5, fontWeight: 700, textTransform: 'uppercase' }}>
              {data.level === 'halt' ? 'Halted' : 'Warning'}
            </span>
          )}
        </div>
      </Section>
    </PanelCard>
  );
}
