import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import { c as t, tint } from '../styles/terminalUI';

interface TelegramConfig {
  bot_token_set: boolean;
  bot_token_hint: string;
  chat_id: string;
  enabled: boolean;
  reachable: boolean;
}

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 14 },
  field: { display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 12 },
  label: { color: t.dim, fontSize: 10, letterSpacing: 1 },
  input: {
    background: t.bg, color: t.bright, border: `1px solid ${t.border}`,
    borderRadius: 3, padding: '7px 10px', fontFamily: 'inherit', fontSize: 12,
    width: '100%',
  },
  hint: { color: t.dim, fontSize: 10, marginTop: 2 },
  row: { display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' as const },
  btn: {
    background: '#1a2a1a', color: t.green, border: `1px solid ${t.green}`,
    borderRadius: 3, padding: '6px 16px', cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
  },
  btnBlue: {
    background: t.raised, color: t.blue, border: `1px solid ${t.blue}`,
    borderRadius: 3, padding: '6px 16px', cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
  },
  status: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 },
  guide: {
    background: t.bg, border: `1px solid ${t.border}`, borderRadius: 4,
    padding: '10px 12px', marginBottom: 14, fontSize: 11, color: t.dim,
    lineHeight: 1.8,
  },
  code: {
    fontFamily: 'monospace', background: t.raised,
    padding: '1px 5px', borderRadius: 2, color: t.blue,
  },
};

function dotStyle(on: boolean): React.CSSProperties {
  return {
    width: 8, height: 8, borderRadius: '50%',
    background: on ? t.green : 'var(--k-ink-1)',
    border: `1px solid ${on ? t.green : t.dim}`,
    display: 'inline-block',
  };
}

function msgStyle(ok: boolean): React.CSSProperties {
  return { fontSize: 11, color: ok ? t.green : t.red, marginTop: 8 };
}

function SetupGuide() {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginBottom: 12 }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          background: 'none', border: 'none', color: t.dim, cursor: 'pointer',
          fontFamily: 'inherit', fontSize: 10, letterSpacing: 1, padding: 0,
        }}
      >
        {open ? '▼' : '▶'} HOW TO GET BOT TOKEN & CHAT ID
      </button>
      {open && (
        <div style={S.guide}>
          <div><strong style={{ color: t.dim }}>Step 1 — Create bot</strong></div>
          <div>Open Telegram → search <span style={S.code}>@BotFather</span> → send <span style={S.code}>/newbot</span></div>
          <div>Follow prompts → copy the <strong style={{ color: t.text }}>HTTP API token</strong></div>
          <br />
          <div><strong style={{ color: t.dim }}>Step 2 — Get your Chat ID</strong></div>
          <div>Send any message to your bot, then open:</div>
          <div style={{ ...S.code, display: 'block', margin: '4px 0', padding: '4px 8px', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
            {'https://api.telegram.org/bot<TOKEN>/getUpdates'}
          </div>
          <div>Look for <span style={S.code}>"chat":{"{"}"id": 123456{"}"}</span> → that number is your Chat ID</div>
          <br />
          <div><strong style={{ color: t.dim }}>Group chats</strong></div>
          <div>Add the bot to a group → prefix Chat ID with <span style={S.code}>-100</span> (e.g. <span style={S.code}>-100123456789</span>)</div>
        </div>
      )}
    </div>
  );
}

export function TelegramConfigPanel() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<TelegramConfig>({
    queryKey: ['telegram-config'],
    queryFn: () => api.get<TelegramConfig>('/api/v1/config/telegram'),
    staleTime: 30_000,
  });

  const [botToken, setBotToken] = useState('');
  const [chatId, setChatId]     = useState('');
  const [msg, setMsg]           = useState('');
  const [msgOk, setMsgOk]       = useState(true);

  useEffect(() => {
    if (data) {
      setChatId(data.chat_id || '');
    }
  }, [data]);

  const save = useMutation<TelegramConfig, Error, void>({
    mutationFn: () =>
      api.put<TelegramConfig>('/api/v1/config/telegram', {
        bot_token: botToken || undefined,
        chat_id:   chatId,
      }),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ['telegram-config'] });
      setBotToken('');
      if (d.reachable) {
        setMsgOk(true);
        setMsg('✓ Saved and connected — test message sent to Telegram');
      } else if (d.enabled) {
        setMsgOk(false);
        setMsg('Saved but could not reach Telegram — check token and chat ID');
      } else {
        setMsgOk(true);
        setMsg('Saved (token/chat ID not set — notifications disabled)');
      }
      setTimeout(() => setMsg(''), 6000);
    },
    onError: (e) => {
      setMsgOk(false);
      setMsg(`Error: ${e.message}`);
    },
  });

  const test = useMutation<TelegramConfig, Error, void>({
    mutationFn: () => api.post<TelegramConfig>('/api/v1/config/telegram/test'),
    onSuccess: (d) => {
      setMsgOk(d.reachable);
      setMsg(d.reachable ? '✓ Test message delivered' : '✗ Could not deliver — check credentials');
      setTimeout(() => setMsg(''), 5000);
    },
  });

  return (
    <div style={S.card}>
      <div style={S.title}>TELEGRAM NOTIFICATIONS</div>

      <div style={S.status}>
        <span style={dotStyle(data?.enabled ?? false)} />
        <span style={{ color: data?.enabled ? t.green : t.dim, fontSize: 11 }}>
          {isLoading ? 'Loading…' : data?.enabled ? 'Connected' : 'Not configured'}
        </span>
        {data?.bot_token_set && (
          <span style={{ color: t.dim, fontSize: 10 }}>
            Token: <span style={{ color: t.dim }}>{data.bot_token_hint}</span>
          </span>
        )}
        {data?.chat_id && (
          <span style={{ color: t.dim, fontSize: 10 }}>
            Chat ID: <span style={{ color: t.dim }}>{data.chat_id}</span>
          </span>
        )}
      </div>

      <SetupGuide />

      <div style={S.field}>
        <label style={S.label}>BOT TOKEN</label>
        <input
          style={S.input}
          type="password"
          placeholder={data?.bot_token_set ? `Current: ${data.bot_token_hint} (leave blank to keep)` : 'Paste token from @BotFather'}
          value={botToken}
          onChange={e => setBotToken(e.target.value)}
          autoComplete="off"
        />
        <span style={S.hint}>From @BotFather · format: 123456789:ABC-DEF…</span>
      </div>

      <div style={S.field}>
        <label style={S.label}>CHAT ID</label>
        <input
          style={S.input}
          type="text"
          placeholder="e.g. 123456789 or -100123456789 for groups"
          value={chatId}
          onChange={e => setChatId(e.target.value)}
        />
        <span style={S.hint}>Your personal chat ID or group ID (prefix -100 for groups)</span>
      </div>

      <div style={{ color: t.dim, fontSize: 10, marginBottom: 12, lineHeight: 1.7 }}>
        <strong style={{ color: t.dim }}>Alerts sent:</strong> signal arrows · trail stop moves ·
        partial exits · position closed · circuit breaker · daily summary
      </div>

      <div style={S.row}>
        <button
          style={S.btn}
          onClick={() => save.mutate()}
          disabled={save.isPending}
        >
          {save.isPending ? 'Saving…' : 'Save & Connect'}
        </button>
        {data?.enabled && (
          <button
            style={S.btnBlue}
            onClick={() => test.mutate()}
            disabled={test.isPending}
          >
            {test.isPending ? 'Sending…' : '⟳ Send Test Message'}
          </button>
        )}
      </div>

      {msg && <div style={msgStyle(msgOk)}>{msg}</div>}
    </div>
  );
}
