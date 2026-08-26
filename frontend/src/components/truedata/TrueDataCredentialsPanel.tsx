import React, { useState } from 'react';
import {
  useAddTrueDataCredential,
  useDeleteTrueDataCredential,
  useRunTrueDataDiagnostics,
  useTrueDataCredentials,
  useTrueDataSettings,
  useTrueDataStatus,
  useUpdateTrueDataCredential,
  useUpdateTrueDataSettings,
} from '../../hooks/useTrueData';
import type { MarketDataSource, TrueDataCredential } from '../../types/truedata';

const S: Record<string, React.CSSProperties> = {
  card: {
    background: 'var(--k-bg)',
    border: '1px solid var(--k-border)',
    borderRadius: 9,
    padding: 18,
    marginBottom: 16,
    boxShadow: '0 1px 2px rgba(0,0,0,.025)',
  },
  title: {
    color: 'var(--k-ink-5)',
    fontSize: 10.5,
    letterSpacing: 0.75,
    marginBottom: 12,
    fontWeight: 750,
  },
  btn: {
    minHeight: 34,
    background: 'var(--k-bg)',
    color: 'var(--k-text)',
    border: '1px solid var(--k-border-strong-2)',
    padding: '0 12px',
    borderRadius: 7,
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: 11,
    fontWeight: 600,
  },
  btnGreen: {
    minHeight: 34,
    background: 'var(--k-brand)',
    color: 'var(--k-on-accent)',
    border: '1px solid var(--k-brand)',
    padding: '0 13px',
    borderRadius: 7,
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: 11,
    fontWeight: 700,
  },
  btnRed: {
    minHeight: 34,
    background: 'var(--k-bg)',
    color: 'var(--k-red-brick)',
    border: '1px solid var(--k-border-strong-2)',
    padding: '0 12px',
    borderRadius: 7,
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: 11,
    fontWeight: 600,
  },
  input: {
    minHeight: 36,
    background: 'var(--k-bg)',
    color: 'var(--k-text)',
    border: '1px solid var(--k-border-strong-2)',
    borderRadius: 7,
    padding: '0 10px',
    fontFamily: 'inherit',
    fontSize: 12,
    width: '100%',
    boxSizing: 'border-box' as const,
  },
  label: {
    color: 'var(--k-ink-5)',
    fontSize: 10,
    letterSpacing: 0.7,
    marginBottom: 4,
    display: 'block',
    fontWeight: 650,
  },
  hint: { color: 'var(--k-ink-6)', fontSize: 11.5 },
  err: { color: 'var(--k-red-strong)', fontSize: 11, marginTop: 6 },
  ok: { color: 'var(--k-green)', fontSize: 11, marginTop: 6 },
};

function initials(s: string): string {
  const parts = s.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return s.slice(0, 2).toUpperCase();
}

function TrueDataCredentialCard({ cred }: { cred: TrueDataCredential }) {
  const del = useDeleteTrueDataCredential();
  const update = useUpdateTrueDataCredential();
  const runDiag = useRunTrueDataDiagnostics();

  const [expanded, setExpanded] = useState(false);
  const [edit, setEdit] = useState(false);
  const [label, setLabel] = useState(cred.label);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [port, setPort] = useState(cred.realtime_port || 8082);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  const handleTest = async () => {
    setTestResult(null);
    try {
      const res = await runDiag.mutateAsync({ category_id: 'truedata_auth' });
      const authCat = res.categories?.find((c) => c.id === 'truedata_auth') || res.categories?.[0];
      if (authCat && authCat.status === 'PASS') {
        setTestResult({
          ok: true,
          message: `✓ Connection Verified (${authCat.latency_ms.toFixed(1)} ms) — WebAPI HTTP 200`,
        });
      } else {
        setTestResult({
          ok: false,
          message: `✗ ${authCat?.error_message || 'Authentication check failed'}`,
        });
      }
    } catch (err: any) {
      setTestResult({
        ok: false,
        message: `✗ ${err?.message || 'Connection failed'}`,
      });
    }
  };

  const subParts = [
    cred.username_hint ? `User: ${cred.username_hint}` : null,
    cred.is_active ? 'Active Feed' : null,
    cred.connected ? 'Connected' : 'Configured',
  ].filter(Boolean);
  const subText = subParts.join(' · ');

  return (
    <div
      style={{
        border: '1px solid var(--k-border)',
        borderRadius: 9,
        marginBottom: 16,
        overflow: 'hidden',
        background: 'var(--k-bg)',
        boxShadow: '0 1px 2px rgba(0,0,0,.025)',
      }}
    >
      <div
        onClick={() => setExpanded((v) => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '14px 16px',
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: '50%',
            background: 'var(--k-border-2)',
            flexShrink: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--k-ink-4)',
            fontWeight: 700,
            fontSize: 13,
          }}
        >
          {initials(cred.label)}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, color: 'var(--k-text)', fontSize: 13 }}>{cred.label}</div>
          <div style={{ color: 'var(--k-dim)', fontSize: 11, marginTop: 2 }}>{subText}</div>
        </div>
        <span
          aria-hidden
          style={{
            color: 'var(--k-faint-2)',
            fontSize: 11,
            transform: expanded ? 'rotate(180deg)' : 'none',
            transition: 'transform .15s',
          }}
        >
          ▼
        </span>
      </div>

      {expanded && (
        <div
          style={{
            borderTop: '1px solid var(--k-surface-hover-2)',
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              style={{
                ...S.btn,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                borderColor: 'var(--k-border-slate-strong)',
                background: 'var(--k-surface-sunken)',
              }}
              onClick={handleTest}
              disabled={runDiag.isPending}
            >
              {runDiag.isPending ? (
                <>
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      border: '2px solid rgba(0,0,0,0.2)',
                      borderTopColor: '#0f172a',
                      borderRadius: '50%',
                      animation: 'spin 0.6s linear infinite',
                      display: 'inline-block',
                    }}
                  />
                  Testing…
                </>
              ) : (
                '▶ Test Connection'
              )}
            </button>
            <button style={S.btn} onClick={() => setEdit((v) => !v)}>
              {edit ? 'Cancel' : 'Edit Credential'}
            </button>
            <button
              style={{ ...S.btnRed, marginLeft: 'auto' }}
              onClick={() => {
                if (window.confirm(`Remove TrueData feed "${cred.label}"?`)) del.mutate(cred.id);
              }}
            >
              Remove
            </button>
          </div>

          {testResult && (
            <div
              style={{
                fontSize: 11,
                padding: '6px 10px',
                borderRadius: 6,
                background: testResult.ok ? '#f0fdf4' : '#fef2f2',
                border: `1px solid ${testResult.ok ? '#bbf7d0' : '#fecaca'}`,
                color: testResult.ok ? '#15803d' : '#b91c1c',
                lineHeight: 1.4,
              }}
            >
              {testResult.message}
            </div>
          )}

          {edit ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div>
                <label style={S.label}>LABEL</label>
                <input
                  style={S.input}
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                />
              </div>
              <div>
                <label style={S.label}>NEW USERNAME (blank = keep current)</label>
                <input
                  style={S.input}
                  placeholder={cred.username_hint}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="off"
                />
              </div>
              <div>
                <label style={S.label}>NEW PASSWORD (blank = keep current)</label>
                <input
                  style={S.input}
                  type="password"
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                />
              </div>
              <div>
                <label style={S.label}>REALTIME PORT</label>
                <input
                  style={S.input}
                  type="number"
                  value={port}
                  onChange={(e) => setPort(Number(e.target.value))}
                />
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button
                  style={S.btnGreen}
                  disabled={update.isPending}
                  onClick={() =>
                    update.mutate(
                      {
                        id: cred.id,
                        label: label.trim() || cred.label,
                        ...(username.trim() ? { username: username.trim() } : {}),
                        ...(password.trim() ? { password: password.trim() } : {}),
                        realtime_port: port,
                      },
                      {
                        onSuccess: () => {
                          setEdit(false);
                          setUsername('');
                          setPassword('');
                        },
                      }
                    )
                  }
                >
                  {update.isPending ? 'SAVING…' : 'SAVE CHANGES'}
                </button>
                <button
                  style={S.btn}
                  onClick={() => {
                    setEdit(false);
                    setLabel(cred.label);
                    setUsername('');
                    setPassword('');
                  }}
                >
                  CANCEL
                </button>
                <button
                  style={{ ...S.btnRed, marginLeft: 'auto' }}
                  onClick={() => {
                    if (window.confirm(`Remove TrueData feed "${cred.label}"?`)) del.mutate(cred.id);
                  }}
                >
                  DELETE
                </button>
              </div>
              {update.error && <div style={S.err}>✗ {update.error.message}</div>}
            </div>
          ) : (
            <div style={{ marginTop: 14, fontSize: 12, color: 'var(--k-ink-4)', lineHeight: 1.6 }}>
              <div><strong>Port:</strong> {cred.realtime_port || 8082}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <strong>Status:</strong>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    color: cred.connected ? 'var(--k-green-600)' : '#ea580c',
                    fontWeight: 600,
                  }}
                >
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      background: cred.connected ? 'var(--k-green-600)' : '#ea580c',
                    }}
                  />
                  {cred.connected ? 'Connected & Verified' : 'Configured (Standby)'}
                </span>
              </div>
              <div><strong>Configured:</strong> {new Date(cred.created_at_ms).toLocaleDateString()}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DataSourceSelector() {
  const { data: settings } = useTrueDataSettings();
  const update = useUpdateTrueDataSettings();
  const currentSource: MarketDataSource = settings?.data_source ?? 'truedata';

  const setSource = (source: MarketDataSource) => {
    if (source !== currentSource && !update.isPending) {
      update.mutate({ data_source: source });
    }
  };

  return (
    <div style={S.card}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={S.title}>PRIMARY MARKET DATA SOURCE</div>
        <span
          style={{
            fontSize: 10,
            fontWeight: 750,
            letterSpacing: '0.05em',
            padding: '2px 8px',
            borderRadius: 4,
            background: currentSource === 'truedata' ? 'rgba(240, 100, 40, 0.12)' : 'rgba(56, 126, 209, 0.12)',
            color: currentSource === 'truedata' ? 'var(--k-brand)' : 'var(--k-blue-kite)',
            border: currentSource === 'truedata' ? '1px solid rgba(240, 100, 40, 0.3)' : '1px solid rgba(56, 126, 209, 0.3)',
          }}
        >
          {currentSource === 'truedata' ? 'ACTIVE: TRUEDATA' : 'ACTIVE: ZERODHA KITE'}
        </span>
      </div>

      <div style={{ fontSize: 12, color: 'var(--k-ink-4)', marginBottom: 14, lineHeight: 1.5 }}>
        Choose whether Adaptive Edge, orderflow indicators, and market scanners ingest live data from TrueData or Zerodha Kite.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12 }}>
        {/* TrueData Option Card */}
        <div
          onClick={() => setSource('truedata')}
          style={{
            border: `1.5px solid ${currentSource === 'truedata' ? 'var(--k-brand)' : 'var(--k-border)'}`,
            borderRadius: 8,
            padding: 14,
            background: currentSource === 'truedata' ? 'rgba(240, 100, 40, 0.04)' : 'var(--k-bg)',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <input
              type="radio"
              name="market_data_source"
              checked={currentSource === 'truedata'}
              onChange={() => setSource('truedata')}
              style={{ cursor: 'pointer', accentColor: 'var(--k-brand)' }}
            />
            <span style={{ fontSize: 13, fontWeight: 700, color: currentSource === 'truedata' ? 'var(--k-brand)' : 'var(--k-ink-1)' }}>
              TrueData Feed (Recommended)
            </span>
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--k-ink-5)', lineHeight: 1.45, marginLeft: 22 }}>
            Institutional tick-level data, Level 2 orderbook, and CVD/VWAP analytics for NIFTY-I and BANKNIFTY-I.
          </div>
        </div>

        {/* Zerodha Kite Option Card */}
        <div
          onClick={() => setSource('zerodhakite')}
          style={{
            border: `1.5px solid ${currentSource === 'zerodhakite' ? 'var(--k-blue-kite)' : 'var(--k-border)'}`,
            borderRadius: 8,
            padding: 14,
            background: currentSource === 'zerodhakite' ? 'rgba(56, 126, 209, 0.04)' : 'var(--k-bg)',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <input
              type="radio"
              name="market_data_source"
              checked={currentSource === 'zerodhakite'}
              onChange={() => setSource('zerodhakite')}
              style={{ cursor: 'pointer', accentColor: 'var(--k-blue-kite)' }}
            />
            <span style={{ fontSize: 13, fontWeight: 700, color: currentSource === 'zerodhakite' ? 'var(--k-blue-kite)' : 'var(--k-ink-1)' }}>
              Zerodha Kite Feed
            </span>
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--k-ink-5)', lineHeight: 1.45, marginLeft: 22 }}>
            Direct broker WebSocket option quote ticks, spot OHLC snapshots, and SuperTrend scans from Kite Connect.
          </div>
        </div>
      </div>
      {update.isPending && (
        <div style={{ fontSize: 11, color: 'var(--k-ink-6)', marginTop: 10, fontStyle: 'italic' }}>
          Updating data source preference…
        </div>
      )}
    </div>
  );
}

function AddTrueDataCredential() {
  const add = useAddTrueDataCredential();
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState('My TrueData Feed');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [port, setPort] = useState(8082);

  if (!open) {
    return (
      <button style={S.btnGreen} onClick={() => setOpen(true)}>
        + ADD TRUEDATA CREDENTIALS
      </button>
    );
  }

  return (
    <div style={S.card}>
      <div style={S.title}>NEW TRUEDATA FEED CREDENTIALS</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <label style={S.label}>FEED LABEL</label>
          <input
            style={S.input}
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. Primary TrueData Feed"
          />
        </div>
        <div>
          <label style={S.label}>TRUEDATA USERNAME</label>
          <input
            style={S.input}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="TrueData Username"
          />
        </div>
        <div>
          <label style={S.label}>TRUEDATA PASSWORD</label>
          <input
            style={S.input}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="TrueData Password"
          />
        </div>
        <div>
          <label style={S.label}>REALTIME PORT (DEFAULT: 8082)</label>
          <input
            style={S.input}
            type="number"
            value={port}
            onChange={(e) => setPort(Number(e.target.value))}
          />
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
          <button
            style={S.btnGreen}
            disabled={add.isPending || !username || !password}
            onClick={() =>
              add.mutate(
                {
                  label: label.trim() || 'My TrueData Feed',
                  username: username.trim(),
                  password,
                  realtime_port: port,
                },
                {
                  onSuccess: () => {
                    setOpen(false);
                    setUsername('');
                    setPassword('');
                  },
                }
              )
            }
          >
            {add.isPending ? 'CONNECTING…' : 'SAVE & CONNECT'}
          </button>
          <button style={S.btn} onClick={() => setOpen(false)}>
            CANCEL
          </button>
        </div>
        {add.error && <div style={S.err}>✗ {add.error.message}</div>}
      </div>
    </div>
  );
}

export function TrueDataCredentialsPanel() {
  const { data: creds, isLoading } = useTrueDataCredentials();
  const { data: status } = useTrueDataStatus();

  return (
    <div>
      <DataSourceSelector />

      <div style={S.card}>
        <div style={S.title}>TRUEDATA MARKET DATA STATUS</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: 4,
              background: status?.connected ? 'var(--k-green)' : 'var(--k-ink-5)',
            }}
          />
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--k-text)' }}>
            {status?.connected
              ? `Connected (${status.username_hint || 'TrueData'})`
              : status?.message || 'Not Connected'}
          </span>
        </div>
        <div style={{ ...S.hint, marginTop: 6, lineHeight: 1.5 }}>
          TrueData provides tick and bar market data feeds for Adaptive Edge and Sterling market scanning.
          Credentials are encrypted at rest with <code>STERLING_SECRET_KEY</code> and never stored in plain text.
        </div>
      </div>

      {isLoading && <div style={S.hint}>Loading TrueData credentials…</div>}
      {creds?.map((c) => (
        <TrueDataCredentialCard key={c.id} cred={c} />
      ))}
      {creds && creds.length === 0 && (
        <div style={{ ...S.hint, marginBottom: 14 }}>
          No TrueData credentials saved yet. Add your username and password below to enable market data.
        </div>
      )}

      <AddTrueDataCredential />
    </div>
  );
}

