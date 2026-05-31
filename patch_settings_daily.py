import sys

# 1. Update DailyLossPanel in RiskConfigPanel.tsx to include the toggle.
filepath_risk = "frontend/src/components/RiskConfigPanel.tsx"
with open(filepath_risk, "r") as f:
    content_risk = f.read()

import re

# We will actually remove DailyLossPanel from RiskConfigPanel and put it in SimpleSettings
content_risk = re.sub(r'export function DailyLossPanel\(\) \{.*?\n\}\n*', '', content_risk, flags=re.DOTALL)
with open(filepath_risk, "w") as f:
    f.write(content_risk)
    
# Also remove from BottomPanel.tsx
filepath_bottom = "frontend/src/components/BottomPanel.tsx"
with open(filepath_bottom, "r") as f:
    content_bottom = f.read()
content_bottom = content_bottom.replace("import { RiskConfigPanel, DailyLossPanel } from './RiskConfigPanel';", "import { RiskConfigPanel } from './RiskConfigPanel';")
content_bottom = content_bottom.replace("<DailyLossPanel />\n            <RiskConfigPanel />", "<RiskConfigPanel />")
with open(filepath_bottom, "w") as f:
    f.write(content_bottom)

# 2. Add DailyLossSection to SimpleSettings.tsx
filepath_settings = "frontend/src/components/SimpleSettings.tsx"
with open(filepath_settings, "r") as f:
    content_settings = f.read()

daily_loss_section = """
// ── Daily Loss Circuit Breaker ───────────────────────────────────────────────
function DailyLossSection() {
  const { data } = useDailyLossConfig();
  const update = useUpdateDailyLossConfig();
  const [enabled, setEnabled] = React.useState<boolean | null>(null);
  const [soft, setSoft] = React.useState<number | null>(null);
  const [hard, setHard] = React.useState<number | null>(null);

  React.useEffect(() => {
    if (data) {
      if (enabled === null) setEnabled(data.enabled);
      if (soft === null) setSoft(data.soft_warn_usd);
      if (hard === null) setHard(data.hard_halt_usd);
    }
  }, [data]);

  if (!data) return null;

  const handleSave = () => {
    if (enabled !== null && soft !== null && hard !== null) {
      update.mutate({ enabled, soft_warn_usd: soft, hard_halt_usd: hard });
    }
  };

  const isDirty = enabled !== data.enabled || soft !== data.soft_warn_usd || hard !== data.hard_halt_usd;

  const statusLabel = !data.enabled ? 'DISABLED' : (data.level === 'halt' ? 'HALTED' : (data.level === 'warning' ? 'WARNING' : 'CLEAR'));
  const statusColor = !data.enabled ? 'var(--t-dim)' : (data.level === 'halt' ? 'var(--t-red)' : (data.level === 'warning' ? 'var(--t-amber)' : 'var(--t-green)'));

  return (
    <Section title="DAILY LOSS LIMIT" status={<span style={{ fontSize: 9, color: statusColor, fontWeight: 500 }}>{statusLabel}</span>}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={{ fontSize: 10, color: 'var(--t-dim)', letterSpacing: '0.06em' }}>CIRCUIT BREAKER</span>
        <button
          onClick={() => setEnabled(!enabled)}
          style={{
            background: enabled ? 'var(--t-green)22' : 'var(--t-bg2)',
            color: enabled ? 'var(--t-green)' : 'var(--t-dim)',
            border: `1px solid ${enabled ? 'var(--t-green)66' : 'var(--t-border)'}`,
            padding: '4px 10px',
            borderRadius: 4,
            fontSize: 10,
            cursor: 'pointer',
            fontWeight: 500,
          }}
        >
          {enabled ? 'ON' : 'OFF'}
        </button>
      </div>

      <Field label="SOFT WARN (USD)" hint="Warning level before hard halt. Expressed as negative USD (e.g. -1000)">
        <input
          type="number"
          step={100}
          value={soft ?? 0}
          onChange={e => setSoft(parseFloat(e.target.value))}
          style={inputStyle}
          disabled={!enabled}
        />
      </Field>
      <Field label="HARD HALT (USD)" hint="Blocks new orders if daily realized PnL drops below this">
        <input
          type="number"
          step={100}
          value={hard ?? 0}
          onChange={e => setHard(parseFloat(e.target.value))}
          style={inputStyle}
          disabled={!enabled}
        />
      </Field>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}>
        <span style={{ fontSize: 10, color: 'var(--t-dim)' }}>
          Realized Today: <strong style={{ color: data.pnl_usd < 0 ? 'var(--t-red)' : 'var(--t-green)' }}>${data.pnl_usd.toFixed(2)}</strong>
        </span>
        <button
          onClick={handleSave}
          disabled={update.isPending || !isDirty}
          style={{
            padding: '6px 12px', borderRadius: 4,
            fontFamily: 'inherit', fontSize: 10, fontWeight: 500, letterSpacing: '0.1em', textTransform: 'uppercase',
            cursor: update.isPending || !isDirty ? 'not-allowed' : 'pointer',
            background: isDirty ? 'var(--t-bg2)' : 'transparent',
            color: isDirty ? 'var(--t-bright)' : 'var(--t-dim)',
            border: '1px solid var(--t-border)',
            opacity: update.isPending || !isDirty ? 0.4 : 1,
          }}
        >
          {update.isPending ? 'Saving…' : (isDirty ? 'Save Config' : 'Saved')}
        </button>
      </div>
    </Section>
  );
}
"""

if "function DailyLossSection()" not in content_settings:
    content_settings = content_settings.replace(
        "function UiSection() {",
        daily_loss_section + "\nfunction UiSection() {"
    )
    content_settings = content_settings.replace(
        "<ExchangeSection />",
        "<ExchangeSection />\n        <DailyLossSection />"
    )
    
    # We need to import useDailyLossConfig, useUpdateDailyLossConfig
    import_hook = "import { useDailyLossConfig, useUpdateDailyLossConfig } from '../hooks/useRiskConfig';"
    if "useDailyLossConfig" not in content_settings:
        content_settings = content_settings.replace(
            "import { api } from '../utils/api';",
            "import { api } from '../utils/api';\n" + import_hook
        )
    
with open(filepath_settings, "w") as f:
    f.write(content_settings)
print("Moved to Settings menu")

