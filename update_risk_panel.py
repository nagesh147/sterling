filepath = "frontend/src/components/RiskConfigPanel.tsx"
with open(filepath, "r") as f:
    content = f.read()

content = content.replace(
    "import { useRiskConfig, useUpdateRiskConfig, useResetRiskConfig } from '../hooks/useRiskConfig';",
    "import { useRiskConfig, useUpdateRiskConfig, useResetRiskConfig, useDailyLossConfig, useUpdateDailyLossConfig } from '../hooks/useRiskConfig';"
)

new_dl_section = """
export function DailyLossPanel() {
  const { data } = useDailyLossConfig();
  const update = useUpdateDailyLossConfig();
  const [soft, setSoft] = React.useState<number | null>(null);
  const [hard, setHard] = React.useState<number | null>(null);

  React.useEffect(() => {
    if (data) {
      if (soft === null) setSoft(data.soft_warn_usd);
      if (hard === null) setHard(data.hard_halt_usd);
    }
  }, [data]);

  if (!data) return null;

  const handleSave = () => {
    if (soft !== null && hard !== null) {
      update.mutate({ soft_warn_usd: soft, hard_halt_usd: hard });
    }
  };

  const isDirty = soft !== data.soft_warn_usd || hard !== data.hard_halt_usd;

  return (
    <div style={styles.card}>
      <div style={styles.title}>
        DAILY LOSS CIRCUIT BREAKER
        <span style={{ float: 'right', color: data.level === 'halt' ? c.red : (data.level === 'warning' ? c.orange : c.dim) }}>
          Status: {data.level.toUpperCase()} (PnL: ${data.pnl_usd.toFixed(2)})
        </span>
      </div>
      <div style={styles.grid}>
        <div style={styles.fieldWrap}>
          <label style={styles.label}>SOFT WARN (USD)</label>
          <input
            style={styles.input}
            type="number"
            step={100}
            value={soft ?? 0}
            onChange={e => setSoft(parseFloat(e.target.value))}
          />
        </div>
        <div style={styles.fieldWrap}>
          <label style={styles.label}>HARD HALT (USD)</label>
          <input
            style={styles.input}
            type="number"
            step={100}
            value={hard ?? 0}
            onChange={e => setHard(parseFloat(e.target.value))}
          />
        </div>
      </div>
      <div style={styles.actions}>
        <button style={{...styles.saveBtn, opacity: isDirty ? 1 : 0.5}} onClick={handleSave} disabled={update.isPending || !isDirty}>
          {update.isPending ? 'SAVING…' : (isDirty ? 'SAVE CONFIG' : 'SAVED')}
        </button>
      </div>
    </div>
  );
}
"""

if "export function DailyLossPanel" not in content:
    content += "\n" + new_dl_section

with open(filepath, "w") as f:
    f.write(content)
print("Added DailyLossPanel")
