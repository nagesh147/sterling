import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

interface TelegramConfig {
  bot_token_set: boolean;
  bot_token_hint: string;
  chat_id: string;
  enabled: boolean;
  reachable: boolean;
}

const S: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 14 },
  field: { display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 12 },
  label: { color: '#555', fontSize: 10, letterSpacing: 1 },
  input: {
    background: '#111', color: '#e0e0e0', border: '1px solid #2a2a2a',
    borderRadius: 3, padding: '7px 10px', fontFamily: 'inherit', fontSize: 12,
    width: '100%',
  },
  hint: { color: '#444', fontSize: 10, marginTop: 2 },
  row: { display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' as const },
  btn: {
    background: '#1a2a1a', color: '#44cc88', border: '1px solid #44cc88',
    borderRadius: 3, padding: '6px 16px', cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
  },
  btnBlue: {
    background: '#1a1a2a', color: '#88aaff', border: '1px solid #88aaff',
    borderRadius: 3, padding: '6px 16px', cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
  },
  status: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 },
  guide: {
    background: '#0d0d0d', border: '1px solid #1e1e1e', borderRadius: 4,
    padding: '10px 12px', marginBottom: 14, fontSize: 11, color: '#666',
    lineHeight: 1.8,
  },
  code: {
    fontFamily: 'monospace', background: '#1a1a1a',
    padding: '1px 5px', borderRadius: 2, color: '#88aaff',
  },
};

function dotStyle(on: boolean): React.CSSProperties {
  return {
    width: 8, height: 8, borderRadius: '50%',
    background: on ? '#44cc88' : '#333',
    border: `1px solid ${on ? '#44cc88' : '#555'}`,
    display: 'inline-block',
  };
}

function msgStyle(ok: boolean): React.CSSProperties {
  return { fontSize: 11, color: ok ? '#44cc88' : '#cc4444', marginTop: 8 };
}

function SetupGuide() {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginBottom: 12 }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          background: 'none', border: 'none', color: '#555', cursor: 'pointer',
          fontFamily: 'inherit', fontSize: 10, letterSpacing: 1, padding: 0,
        }}
      >
        {open ? '▼' : '▶'} HOW TO GET BOT TOKEN & CHAT ID
      </button>
      {open && (
        <div style={S.guide}>
          <div><strong style={{ color: '#888' }}>Step 1 — Create bot</strong></div>
          <div>Open Telegram → search <span style={S.code}>@BotFather</span> → send <span style={S.code}>/newbot</span></div>
          <div>Follow prompts → copy the <strong style={{ color: '#ccc' }}>HTTP API token</strong></div>
          <br />
          <div><strong style={{ color: '#888' }}>Step 2 — Get your Chat ID</strong></div>
          <div>Send any message to your bot, then open:</div>
          <div style={{ ...S.code, display: 'block', margin: '4px 0', padding: '4px 8px', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
            {'https://api.telegram.org/bot<TOKEN>/getUpdates'}
          </div>
          <div>Look for <span style={S.code}>"chat":{"{"}"id": 123456{"}"}</span> → that number is your Chat ID</div>
          <br />
          <div><strong style={{ color: '#888' }}>Group chats</strong></div>
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
        <span style={{ color: data?.enabled ? '#44cc88' : '#555', fontSize: 11 }}>
          {isLoading ? 'Loading…' : data?.enabled ? 'Connected' : 'Not configured'}
        </span>
        {data?.bot_token_set && (
          <span style={{ color: '#444', fontSize: 10 }}>
            Token: <span style={{ color: '#666' }}>{data.bot_token_hint}</span>
          </span>
        )}
        {data?.chat_id && (
          <span style={{ color: '#444', fontSize: 10 }}>
            Chat ID: <span style={{ color: '#666' }}>{data.chat_id}</span>
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

      <div style={{ color: '#444', fontSize: 10, marginBottom: 12, lineHeight: 1.7 }}>
        <strong style={{ color: '#555' }}>Alerts sent:</strong> signal arrows · trail stop moves ·
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
