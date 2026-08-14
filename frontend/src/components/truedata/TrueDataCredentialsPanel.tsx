import React, { useState } from 'react';
import {
  useAddTrueDataCredential,
  useDeleteTrueDataCredential,
  useTrueDataCredentials,
  useTrueDataStatus,
  useUpdateTrueDataCredential,
} from '../../hooks/useTrueData';
import type { TrueDataCredential } from '../../types/truedata';

const S: Record<string, React.CSSProperties> = {
  card: {
    background: '#fff',
    border: '1px solid #e0e0e0',
    borderRadius: 9,
    padding: 18,
    marginBottom: 16,
    boxShadow: '0 1px 2px rgba(0,0,0,.025)',
  },
  title: {
    color: '#777',
    fontSize: 10.5,
    letterSpacing: 0.75,
    marginBottom: 12,
    fontWeight: 750,
  },
  btn: {
    minHeight: 34,
    background: '#fff',
    color: '#444',
    border: '1px solid #dcdcdc',
    padding: '0 12px',
    borderRadius: 7,
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: 11,
    fontWeight: 600,
  },
  btnGreen: {
    minHeight: 34,
    background: '#f06428',
    color: '#fff',
    border: '1px solid #f06428',
    padding: '0 13px',
    borderRadius: 7,
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: 11,
    fontWeight: 700,
  },
  btnRed: {
    minHeight: 34,
    background: '#fff',
    color: '#c9433e',
    border: '1px solid #dcdcdc',
    padding: '0 12px',
    borderRadius: 7,
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: 11,
    fontWeight: 600,
  },
  input: {
    minHeight: 36,
    background: '#fff',
    color: '#444',
    border: '1px solid #dcdcdc',
    borderRadius: 7,
    padding: '0 10px',
    fontFamily: 'inherit',
    fontSize: 12,
    width: '100%',
    boxSizing: 'border-box' as const,
  },
  label: {
    color: '#777',
    fontSize: 10,
    letterSpacing: 0.7,
    marginBottom: 4,
    display: 'block',
    fontWeight: 650,
  },
  hint: { color: '#888', fontSize: 11.5 },
  err: { color: '#e53935', fontSize: 11, marginTop: 6 },
  ok: { color: '#4caf50', fontSize: 11, marginTop: 6 },
};

function initials(s: string): string {
  const parts = s.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return s.slice(0, 2).toUpperCase();
}

function TrueDataCredentialCard({ cred }: { cred: TrueDataCredential }) {
  const del = useDeleteTrueDataCredential();
  const update = useUpdateTrueDataCredential();

  const [expanded, setExpanded] = useState(false);
  const [edit, setEdit] = useState(false);
  const [label, setLabel] = useState(cred.label);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [port, setPort] = useState(cred.realtime_port || 8082);

  const subParts = [
    cred.username_hint ? `User: ${cred.username_hint}` : null,
    cred.is_active ? 'Active Feed' : null,
    cred.connected ? 'Connected' : 'Configured',
  ].filter(Boolean);
  const subText = subParts.join(' · ');

  return (
    <div
      style={{
        border: '1px solid #e0e0e0',
        borderRadius: 9,
        marginBottom: 16,
        overflow: 'hidden',
        background: '#fff',
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
            background: '#e8e8e8',
            flexShrink: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#666',
            fontWeight: 700,
            fontSize: 13,
          }}
        >
          {initials(cred.label)}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, color: '#444', fontSize: 13 }}>{cred.label}</div>
          <div style={{ color: '#9b9b9b', fontSize: 11, marginTop: 2 }}>{subText}</div>
        </div>
        <span
          aria-hidden
          style={{
            color: '#bbb',
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
            borderTop: '1px solid #f0f0f0',
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
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

          {edit && (
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
                {update.isPending ? 'Saving…' : 'Save Changes'}
              </button>
              {update.error && <div style={S.err}>✗ {update.error.message}</div>}
            </div>
          )}
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

  if (!open)
    return (
      <button style={S.btnGreen} onClick={() => setOpen(true)}>
        + ADD TRUEDATA CREDENTIAL
      </button>
    );

  return (
    <div style={S.card}>
      <div style={S.title}>ADD TRUEDATA CREDENTIAL</div>
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
          <label style={S.label}>USERNAME / LOGIN ID</label>
          <input
            style={S.input}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="TrueData Username"
            autoComplete="off"
          />
        </div>
        <div>
          <label style={S.label}>PASSWORD</label>
          <input
            style={S.input}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="TrueData Password"
            autoComplete="new-password"
          />
        </div>
        <div>
          <label style={S.label}>REALTIME WEBSOCKET PORT</label>
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
            disabled={add.isPending || !username.trim() || !password.trim()}
            onClick={() =>
              add.mutate(
                {
                  label: label.trim() || 'My TrueData Feed',
                  username: username.trim(),
                  password: password.trim(),
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
      <div style={S.card}>
        <div style={S.title}>TRUEDATA MARKET DATA STATUS</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: 4,
              background: status?.connected ? '#4caf50' : '#777',
            }}
          />
          <span style={{ fontSize: 13, fontWeight: 700, color: '#444' }}>
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
