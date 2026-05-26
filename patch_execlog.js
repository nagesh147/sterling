const fs = require('fs');
const file = 'frontend/src/components/scalping/ScalpingTab.tsx';
let code = fs.readFileSync(file, 'utf8');

const target = `function ExecLog({ entries, mode }: {
  entries: { ts: number; key: string; mode: string; ok: boolean; status: string; reason: string; auto: boolean }[];
  mode: string;
}) {
  if (entries.length === 0) {
    return (
      <div style={{ fontSize: 10, color: 'var(--t-dim)', lineHeight: 1.5 }}>
        No execution attempts this session. With <b style={{ color: 'var(--t-bright)' }}>Algo ON</b>, every ready
        signal fires here and its result (mode · status · reason) is logged — so you can confirm <b style={{ color: 'var(--t-bright)' }}>{mode}</b> is
        actually placing orders, or see exactly why one was rejected.
      </div>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5, maxHeight: 340, overflow: 'auto' }}>
      {entries.map((e, i) => {
        const col = e.ok ? 'var(--t-green)' : e.status === 'already_open' ? 'var(--t-blue)' : 'var(--t-red)';
        const dash = e.key.indexOf('-');
        const sym = dash >= 0 ? e.key.slice(0, dash) : e.key;
        const strat = dash >= 0 ? e.key.slice(dash + 1) : '';
        return (
          <div key={i} style={{ borderLeft: \`2px solid \${col}\`, paddingLeft: 7, fontSize: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ color: 'var(--t-bright)', fontWeight: 700 }}>{sym}</span>
              <span style={{ color: 'var(--t-dim)' }}>{strat}</span>
              <span style={{ marginLeft: 'auto', color: modeColorOf(e.mode), fontWeight: 700, fontSize: 9 }}>
                {e.auto ? 'AUTO·' : ''}{e.mode}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ color: col, fontWeight: 700 }}>{e.ok ? '✓' : '✕'} {e.status}</span>
              <span style={{ marginLeft: 'auto', color: 'var(--t-dim)', fontVariantNumeric: 'tabular-nums' }}>
                {new Date(e.ts).toLocaleTimeString()}
              </span>
            </div>
            {e.reason && <div style={{ color: 'var(--t-dim)', lineHeight: 1.3, marginTop: 1 }}>{e.reason}</div>}
          </div>
        );
      })}
    </div>
  );
}`;

const replacement = `function ExecLog({ entries, mode }: {
  entries: { ts: number; key: string; mode: string; ok: boolean; status: string; reason: string; auto: boolean }[];
  mode: string;
}) {
  if (entries.length === 0) {
    return (
      <div style={{ fontSize: 10, color: 'var(--t-dim)', lineHeight: 1.5, padding: 16 }}>
        No execution attempts this session. With <b style={{ color: 'var(--t-bright)' }}>Algo ON</b>, every ready
        signal fires here and its result (mode · status · reason) is logged — so you can confirm <b style={{ color: 'var(--t-bright)' }}>{mode}</b> is
        actually placing orders, or see exactly why one was rejected.
      </div>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 16 }}>
      {entries.map((e, i) => {
        const col = e.ok ? 'var(--t-green)' : e.status === 'already_open' ? 'var(--t-blue)' : 'var(--t-red)';
        const dash = e.key.indexOf('-');
        const sym = dash >= 0 ? e.key.slice(0, dash) : e.key;
        const strat = dash >= 0 ? e.key.slice(dash + 1) : '';
        const bg = e.ok ? col + '16' : 'var(--t-bg)';
        const borderColor = e.ok ? col + '44' : 'var(--t-border)';
        return (
          <div key={i} style={{ 
            display: 'flex', flexDirection: 'column', gap: 7,
            padding: '12px 16px 12px 0', borderRadius: 10,
            border: \`1px solid \${borderColor}\`,
            background: bg,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
              <div style={{ width: 4, alignSelf: 'stretch', minHeight: 34, borderRadius: 3, background: col, flexShrink: 0 }} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2, flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 15, fontWeight: 800, color: 'var(--t-bright)', letterSpacing: '0.02em' }}>{sym}</span>
                  <span style={{ fontSize: 11, color: 'var(--t-dim)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{strat.replace(/_/g, ' ').toUpperCase()}</span>
                  <span style={{ marginLeft: 'auto', color: modeColorOf(e.mode), fontWeight: 800, fontSize: 9, letterSpacing: '0.06em', padding: '3px 8px', borderRadius: 6, background: modeColorOf(e.mode) + '18', border: \`1px solid \${modeColorOf(e.mode)}44\`, whiteSpace: 'nowrap' }}>
                    {e.auto ? 'AUTO · ' : ''}{e.mode}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ color: col, fontWeight: 800, fontSize: 10, letterSpacing: '0.04em' }}>{e.ok ? '✓' : '✕'} {e.status.toUpperCase()}</span>
                  <span style={{ marginLeft: 'auto', color: 'var(--t-dim)', fontVariantNumeric: 'tabular-nums', fontSize: 9 }}>
                    {new Date(e.ts).toLocaleTimeString()}
                  </span>
                </div>
                {e.reason && <div style={{ color: 'var(--t-amber)', fontSize: 10, lineHeight: 1.4, marginTop: 4, fontWeight: 600, wordBreak: 'break-word' }}>✕ {e.mode} — {e.reason}</div>}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}`;

if (code.includes(target)) {
  fs.writeFileSync(file, code.replace(target, replacement));
  console.log('Patched ExecLog successfully');
} else {
  console.log('Target not found in ExecLog');
}
