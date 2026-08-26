import React, { useState } from 'react';
import {
  useAddKiteTelegram, useDeleteKiteTelegram, useKiteTelegramTargets,
  useTestKiteTelegram, useUpdateKiteTelegram,
} from '../../hooks/useKiteTelegram';
import type { KiteTelegramTarget } from '../../types/kiteTelegram';
import { useKiteSettings } from '../../store/useKiteSettings';
import {
  applyKiteBrandIcon,
  getKiteBrandIconHref,
  KITE_BRAND_ICON_GROUPS,
  KITE_BRAND_ICON_OPTIONS,
  KITE_BRAND_ICON_SIZES,
  type KiteBrandIcon,
  type KiteBrandIconOption,
  type KiteBrandIconSize,
} from '../../utils/kiteBrandIcon';

// Kite light theme — white cards, var(--k-border) borders, orange var(--k-brand) accents.
// Matches ConnectPane's inline-style conventions; this panel is the Kite-specific
// multi-bot Telegram manager (distinct from the global crypto TelegramConfigPanel).
const ORANGE = 'var(--k-brand)';

const S: Record<string, React.CSSProperties> = {
  title: { color: 'var(--k-ink-5)', fontSize: 10.5, letterSpacing: .75, marginBottom: 5, fontWeight: 750 },
  sub: { color: 'var(--k-ink-6)', fontSize: 11.5, marginBottom: 14, lineHeight: 1.55 },
  row: { background: 'var(--k-surface-sunken-2)', border: '1px solid var(--k-border)', borderRadius: 7, padding: '11px 12px', marginBottom: 8 },
  name: { fontWeight: 700, color: 'var(--k-text)', fontSize: 13 },
  meta: { color: 'var(--k-dim)', fontSize: 11 },
  actions: { display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8, alignItems: 'center' },
  btn: { minHeight: 34, background: 'var(--k-bg)', color: 'var(--k-text)', border: '1px solid var(--k-border-strong-2)', padding: '0 12px', borderRadius: 7, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, fontWeight: 600 },
  btnOrange: { minHeight: 34, background: ORANGE, color: 'var(--k-bg)', border: `1px solid ${ORANGE}`, padding: '0 13px', borderRadius: 7, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, fontWeight: 700 },
  btnRed: { minHeight: 34, background: 'var(--k-bg)', color: 'var(--k-red-brick)', border: '1px solid var(--k-border-strong-2)', padding: '0 12px', borderRadius: 7, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, fontWeight: 600 },
  input: { minHeight: 36, background: 'var(--k-bg)', color: 'var(--k-text)', border: '1px solid var(--k-border-strong-2)', borderRadius: 7, padding: '0 10px', fontFamily: 'inherit', fontSize: 12, width: '100%', boxSizing: 'border-box' },
  label: { color: 'var(--k-ink-5)', fontSize: 10, letterSpacing: .7, marginBottom: 4, display: 'block', fontWeight: 650 },
  hint: { color: 'var(--k-ink-6)', fontSize: 11.5 },
  err: { color: 'var(--k-red-strong)', fontSize: 11, marginTop: 6 },
  ok: { color: 'var(--k-green)', fontSize: 11, marginTop: 6 },
  guide: { background: '#fff8f4', border: '1px solid #ecd1c4', borderRadius: 8, padding: '12px 14px', marginBottom: 12 },
  step: { display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 12, color: 'var(--k-text)', lineHeight: 1.6, marginBottom: 8 },
  stepNum: { flex: '0 0 18px', width: 18, height: 18, borderRadius: '50%', background: ORANGE, color: 'var(--k-bg)', fontSize: 11, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 1 },
  handle: { display: 'inline-flex', alignItems: 'center', gap: 4, background: 'var(--k-surface-hover)', border: '1px solid var(--k-border)', borderRadius: 3, padding: '0 4px 0 6px', fontFamily: 'monospace', fontSize: 12, color: ORANGE },
  copyBtn: { background: 'none', border: 'none', cursor: 'pointer', color: 'var(--k-dim)', fontSize: 11, padding: '1px 3px', fontFamily: 'inherit' },
};

function dotStyle(reachable: boolean): React.CSSProperties {
  return {
    width: 9, height: 9, borderRadius: '50%',
    background: reachable ? 'var(--k-green)' : 'var(--k-faint-3)',
    border: `1px solid ${reachable ? 'var(--k-green)' : 'var(--k-dim)'}`,
    display: 'inline-block', flex: '0 0 9px',
  };
}

/** A small copyable inline code handle (e.g. @BotFather). */
function CopyHandle({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }).catch(() => { /* clipboard unavailable — ignore */ });
  };
  return (
    <span style={S.handle}>
      {text}
      <button style={S.copyBtn} onClick={copy} title={`Copy ${text}`} type="button">
        {copied ? '✓' : '⧉'}
      </button>
    </span>
  );
}

function FirstRunGuide() {
  return (
    <div style={S.guide}>
      <div style={{ ...S.title, color: ORANGE, marginBottom: 10 }}>SET UP YOUR FIRST KITE TELEGRAM BOT</div>
      <div style={S.step}>
        <span style={S.stepNum}>1</span>
        <span>Open Telegram, message <CopyHandle text="@BotFather" />, send <code style={{ color: ORANGE }}>/newbot</code>, and copy the <strong>bot token</strong> it gives you.</span>
      </div>
      <div style={S.step}>
        <span style={S.stepNum}>2</span>
        <span>Message <CopyHandle text="@userinfobot" /> (or add your bot to a group) to get your <strong>chat id</strong>.</span>
      </div>
      <div style={S.step}>
        <span style={S.stepNum}>3</span>
        <span>Paste both below, name the bot, <strong>Add</strong>, then <strong>Test</strong>.</span>
      </div>
    </div>
  );
}

function IconPreview({ option, size, px = 32 }: { option: KiteBrandIconOption; size: KiteBrandIconSize; px?: number }) {
  if (option.emoji) {
    return <span style={{ fontSize: px, lineHeight: 1 }}>{option.emoji}</span>;
  }
  return <img src={getKiteBrandIconHref(option.value, size)} alt="" width={px} height={px} style={{ display: 'block' }} />;
}

function IconChoice({ option, selected, size, onPick, compact = false }: {
  option: KiteBrandIconOption;
  selected: boolean;
  size: KiteBrandIconSize;
  onPick: (value: KiteBrandIcon) => void;
  compact?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={() => onPick(option.value)}
      aria-pressed={selected}
      title={option.label}
      style={{
        display: 'flex', alignItems: 'center', gap: compact ? 6 : 8,
        minWidth: compact ? 106 : 132,
        minHeight: 46, padding: compact ? '7px 9px' : '8px 10px', cursor: 'pointer',
        background: selected ? 'var(--k-surface-warm)' : 'var(--k-bg)',
        border: `1px solid ${selected ? 'var(--k-border-brand)' : 'var(--k-border)'}`,
        borderRadius: 7, fontFamily: 'inherit', textAlign: 'left',
      }}
    >
      <span style={{ width: compact ? 28 : 30, height: compact ? 28 : 30, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        <IconPreview option={option} size={size} px={compact ? 25 : 28} />
      </span>
      <span style={{ fontSize: 12, fontWeight: selected ? 700 : 600, color: selected ? ORANGE : 'var(--k-text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {option.label}
      </span>
    </button>
  );
}

export function BrandIconPicker() {
  const brandIcon = useKiteSettings((s) => s.brandIcon);
  const brandIconSize = useKiteSettings((s) => s.brandIconSize);
  const recentBrandIcons = useKiteSettings((s) => s.recentBrandIcons);
  const setBrandIcon = useKiteSettings((s) => s.setBrandIcon);
  const setBrandIconSize = useKiteSettings((s) => s.setBrandIconSize);

  const pickIcon = (value: KiteBrandIcon) => {
    setBrandIcon(value);
    applyKiteBrandIcon(value, brandIconSize);
  };
  const pickSize = (size: KiteBrandIconSize) => {
    setBrandIconSize(size);
    applyKiteBrandIcon(brandIcon, size);
  };

  const optionFor = (value: KiteBrandIcon) => KITE_BRAND_ICON_OPTIONS.find((o) => o.value === value);
  const recentOptions = [brandIcon, ...recentBrandIcons]
    .filter((value, idx, arr) => arr.indexOf(value) === idx)
    .map(optionFor)
    .filter(Boolean)
    .slice(0, 5) as KiteBrandIconOption[];

  return (
    <div>
      <div style={S.title}>APP / TAB ICON</div>
      <div style={S.sub}>Choose the icon shown before Sterling.</div>

      {recentOptions.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ ...S.label, marginBottom: 7 }}>RECENT 5</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {recentOptions.map((o) => (
              <IconChoice key={o.value} option={o} selected={brandIcon === o.value} size={brandIconSize} onPick={pickIcon} compact />
            ))}
          </div>
        </div>
      )}

      <div style={{ marginBottom: 14 }}>
        <div style={{ ...S.label, marginBottom: 7 }}>FAVICON SIZE</div>
        <div style={{ display: 'inline-flex', gap: 2, padding: 3, border: '1px solid var(--k-border)', borderRadius: 8, background: '#f6f6f7' }}>
          {KITE_BRAND_ICON_SIZES.map((size) => {
            const selected = brandIconSize === size.value;
            return (
              <button
                key={size.value}
                type="button"
                onClick={() => pickSize(size.value)}
                style={{
                  minHeight: 32, background: selected ? 'var(--k-bg)' : 'transparent',
                  color: selected ? 'var(--k-text)' : 'var(--k-ink-5)',
                  border: 'none', borderRadius: 6,
                  boxShadow: selected ? `inset 0 -2px ${ORANGE}, 0 1px 2px rgba(0,0,0,.08)` : 'none',
                  padding: '0 12px', cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
                  fontWeight: selected ? 700 : 500,
                }}
              >
                {size.label}
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ maxHeight: 360, overflowY: 'auto', padding: '8px 10px 10px', border: '1px solid var(--k-border)', borderRadius: 8, background: 'var(--k-bg)' }}>
        {KITE_BRAND_ICON_GROUPS.map((group, idx) => (
          <div key={group.category} style={{ paddingTop: idx === 0 ? 0 : 12, marginTop: idx === 0 ? 0 : 12, borderTop: idx === 0 ? 'none' : '1px solid var(--k-surface-hover-2)' }}>
            <div style={{ ...S.label, marginBottom: 8 }}>{group.category}</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(132px, 1fr))', gap: 8 }}>
              {group.options.map((o) => (
                <IconChoice key={o.value} option={o} selected={brandIcon === o.value} size={brandIconSize} onPick={pickIcon} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

interface FormValues { label: string; bot_token: string; chat_id: string; enabled: boolean }

/** Shared form for Add and Edit. On Edit, bot token is optional (blank = keep). */
function TargetForm({
  mode, initial, busy, error, onSubmit, onCancel,
}: {
  mode: 'add' | 'edit';
  initial?: Partial<FormValues>;
  busy: boolean;
  error?: string | null;
  onSubmit: (v: FormValues) => void;
  onCancel?: () => void;
}) {
  const [label, setLabel] = useState(initial?.label ?? '');
  const [botToken, setBotToken] = useState('');
  const [chatId, setChatId] = useState(initial?.chat_id ?? '');
  const [enabled, setEnabled] = useState(initial?.enabled ?? true);

  // For Add, require a token + chat id before enabling the button. For Edit a
  // blank token means "keep the existing one", so only chat id is required.
  const canSubmit = mode === 'add'
    ? botToken.trim().length > 0 && chatId.trim().length > 0
    : chatId.trim().length > 0;

  const submit = () => {
    if (!canSubmit) return;
    onSubmit({ label: label.trim() || 'Kite alerts', bot_token: botToken.trim(), chat_id: chatId.trim(), enabled });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div>
        <label style={S.label}>LABEL</label>
        <input style={S.input} value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. My alerts bot" />
      </div>
      <div>
        <label style={S.label}>BOT TOKEN</label>
        <input
          style={S.input}
          type="password"
          value={botToken}
          onChange={(e) => setBotToken(e.target.value)}
          placeholder={mode === 'edit' ? 'Leave blank to keep current token' : 'From @BotFather · 123456789:ABC-DEF…'}
          autoComplete="new-password"
        />
      </div>
      <div>
        <label style={S.label}>CHAT ID</label>
        <input
          style={S.input}
          value={chatId}
          onChange={(e) => setChatId(e.target.value)}
          placeholder="e.g. 123456789 or -100123456789 for groups"
        />
      </div>
      <label style={{ ...S.label, display: 'flex', gap: 6, alignItems: 'center', cursor: 'pointer' }}>
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Enabled
      </label>
      <div style={{ display: 'flex', gap: 8 }}>
        <button style={S.btnOrange} disabled={busy || !canSubmit} onClick={submit}>
          {busy ? (mode === 'add' ? 'ADDING…' : 'SAVING…') : (mode === 'add' ? 'ADD' : 'SAVE')}
        </button>
        {onCancel && <button style={S.btn} onClick={onCancel}>CANCEL</button>}
      </div>
      {error && <div style={S.err}>✗ {error}</div>}
    </div>
  );
}

function TargetRow({ target }: { target: KiteTelegramTarget }) {
  const update = useUpdateKiteTelegram();
  const del = useDeleteKiteTelegram();
  const test = useTestKiteTelegram();
  const [edit, setEdit] = useState(false);

  const toggleEnabled = () => update.mutate({ id: target.id, enabled: !target.enabled });
  const remove = () => {
    if (window.confirm(`Remove Telegram bot "${target.label}"? Alerts will stop going to this chat.`)) {
      del.mutate(target.id);
    }
  };

  return (
    <div style={S.row}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={dotStyle(target.reachable)} title={target.reachable ? 'Reachable' : 'Untested / unreachable'} />
          <span style={S.name}>{target.label}</span>
          {!target.enabled && <span style={{ ...S.meta, fontStyle: 'italic' }}>disabled</span>}
        </div>
        <span style={S.meta}>
          chat {target.chat_id} · token •••{target.bot_token_set ? target.bot_token_hint : '——'}
        </span>
      </div>

      {test.data && (
        <div style={test.data.reachable ? S.ok : S.err}>
          {test.data.reachable ? '✓ Test message delivered' : '✗ Could not deliver — check token & chat id'}
        </div>
      )}
      {test.error && <div style={S.err}>✗ {test.error.message}</div>}
      {update.error && <div style={S.err}>✗ {update.error.message}</div>}
      {del.error && <div style={S.err}>✗ {del.error.message}</div>}

      <div style={S.actions}>
        <label style={{ display: 'flex', gap: 6, alignItems: 'center', cursor: 'pointer', fontSize: 11, color: 'var(--k-dim)' }}>
          <input type="checkbox" checked={target.enabled} onChange={toggleEnabled} disabled={update.isPending} /> Enabled
        </label>
        <button style={S.btn} onClick={() => test.mutate(target.id)} disabled={test.isPending}>
          {test.isPending ? '…' : 'TEST'}
        </button>
        <button style={S.btn} onClick={() => setEdit((v) => !v)}>{edit ? 'CANCEL' : 'EDIT'}</button>
        <button style={S.btnRed} onClick={remove} disabled={del.isPending}>{del.isPending ? '…' : 'REMOVE'}</button>
      </div>

      {edit && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--k-border)' }}>
          <TargetForm
            mode="edit"
            initial={{ label: target.label, chat_id: target.chat_id, enabled: target.enabled }}
            busy={update.isPending}
            error={update.error?.message}
            onSubmit={(v) => update.mutate(
              {
                id: target.id, label: v.label, chat_id: v.chat_id, enabled: v.enabled,
                ...(v.bot_token ? { bot_token: v.bot_token } : {}),
              },
              { onSuccess: () => setEdit(false) },
            )}
            onCancel={() => setEdit(false)}
          />
        </div>
      )}
    </div>
  );
}

function AddTarget() {
  const add = useAddKiteTelegram();
  const [open, setOpen] = useState(false);
  if (!open) return <button style={S.btnOrange} onClick={() => setOpen(true)}>+ ADD BOT</button>;
  return (
    <div style={{ ...S.row, background: 'var(--k-bg)' }}>
      <div style={S.title}>ADD TELEGRAM BOT</div>
      <TargetForm
        mode="add"
        busy={add.isPending}
        error={add.error?.message}
        onSubmit={(v) => add.mutate(v, { onSuccess: () => setOpen(false) })}
        onCancel={() => setOpen(false)}
      />
    </div>
  );
}

export function KiteTelegramPanel() {
  const { data, isLoading, isError, error } = useKiteTelegramTargets();
  const targets = data?.targets ?? [];

  return (
    <div>
      <section style={{ padding: 18, background: 'var(--k-bg)', border: '1px solid var(--k-border)', borderRadius: 9, boxShadow: '0 1px 2px rgba(0,0,0,.025)' }}>
        <div style={S.title}>KITE TELEGRAM ALERTS</div>
        <div style={S.sub}>
          Send Kite signal alerts to your own Telegram bot(s) — separate from the crypto dashboard’s Telegram.
          Add one or more bots, enable the ones you want, and Test to confirm delivery.
        </div>

        {isLoading && <div style={S.hint}>Loading…</div>}

        {/* No backend yet during dev → treat errors like an empty list and show the
            first-run guide rather than crashing. */}
        {!isLoading && targets.length === 0 && (
          <>
            <FirstRunGuide />
            {isError && <div style={{ ...S.hint, marginBottom: 10 }}>Could not load saved bots ({error?.message}). Add one to get started.</div>}
            <AddTarget />
          </>
        )}

        {!isLoading && targets.length > 0 && (
          <>
            {targets.map((tg) => <TargetRow key={tg.id} target={tg} />)}
            <div style={{ marginTop: 4 }}><AddTarget /></div>
          </>
        )}
      </section>
    </div>
  );
}
