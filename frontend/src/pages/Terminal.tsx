import { useSetAppMode } from '../store/useStore';

import '../styles/terminal.css';

/**
 * Terminal (Advanced / `pro` appMode) is temporarily gutted to a welcome
 * placeholder while the multi-pane terminal is rebuilt. The previous panes
 * (SignalPane, ChartPane, RiskPane, BottomPanel, Grok panes, …) still live on
 * disk and can be wired back in here later.
 *
 * Simple mode (SimpleTerminal.tsx) is intentionally untouched. The only way
 * back to it from here is the "Back to Simple" button below, so it must stay.
 */
export function Terminal() {
  const setAppMode = useSetAppMode();

  return (
    <div
      className="term-root"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        background: 'var(--t-bg)',
        textAlign: 'center',
        padding: 24,
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18, maxWidth: 420 }}>
        {/* Brand mark */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: 'var(--t-blue)', fontSize: 22, lineHeight: 1 }}>◆</span>
          <span style={{
            color: 'var(--t-bright)',
            fontSize: 20,
            fontWeight: 800,
            letterSpacing: '0.18em',
          }}>STERLING</span>
        </div>

        {/* Heading */}
        <h1 style={{
          margin: 0,
          color: 'var(--t-bright)',
          fontSize: 16,
          fontWeight: 600,
          letterSpacing: '0.12em',
        }}>
          TERMINAL — COMING SOON
        </h1>

        {/* Subtext */}
        <p style={{
          margin: 0,
          color: 'var(--t-dim)',
          fontSize: 12,
          lineHeight: 1.6,
          letterSpacing: '0.02em',
        }}>
          The advanced terminal is being rebuilt. Check back soon.
        </p>

        {/* Back to simple — only exit from terminal mode, keep it */}
        <button
          onClick={() => setAppMode('basic')}
          style={{
            marginTop: 6,
            background: 'var(--t-blue)',
            border: '1px solid var(--t-blue)',
            color: '#fff',
            cursor: 'pointer',
            padding: '8px 18px',
            borderRadius: 4,
            fontFamily: 'inherit',
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '0.08em',
          }}
        >
          ← BACK TO SIMPLE
        </button>
      </div>
    </div>
  );
}
