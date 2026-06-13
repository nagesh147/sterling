import React from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import { useKiteMargins, useKiteProfile } from '../../hooks/useKite';

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 10, padding: 14, marginBottom: 14 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 10, fontWeight: 700 },
  row: { display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '4px 0', borderBottom: `1px solid ${tint(t.border, 50)}` },
  k: { color: t.dim },
  v: { color: t.bright, fontWeight: 700 },
  hint: { color: t.dim, fontSize: 11 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12 },
  pill: { background: tint(t.blue, 13), color: t.blue, border: `1px solid ${t.blue}`, padding: '1px 7px', borderRadius: 999, fontSize: 9, fontWeight: 700 },
};

const inr = (v: any) => `₹${Number(v ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;

function SegmentCard({ seg, info }: { seg: string; info: any }) {
  const avail = info?.available || {};
  const used = info?.utilised || {};
  return (
    <div style={{ ...S.card, marginBottom: 0 }}>
      <div style={S.title}>{seg.toUpperCase()} · NET {inr(info?.net)}</div>
      <div style={S.row}><span style={S.k}>Available cash</span><span style={S.v}>{inr(avail.live_balance ?? avail.cash)}</span></div>
      <div style={S.row}><span style={S.k}>Opening balance</span><span style={S.v}>{inr(avail.opening_balance)}</span></div>
      <div style={S.row}><span style={S.k}>Collateral</span><span style={S.v}>{inr(avail.collateral)}</span></div>
      <div style={S.row}><span style={S.k}>Used (debits)</span><span style={{ ...S.v, color: t.red }}>{inr(used.debits)}</span></div>
      <div style={S.row}><span style={S.k}>Span / Exposure</span><span style={S.v}>{inr(used.span)} / {inr(used.exposure)}</span></div>
      <div style={{ ...S.row, borderBottom: 'none' }}><span style={S.k}>M2M (real / unreal)</span><span style={S.v}>{inr(used.m2m_realised)} / {inr(used.m2m_unrealised)}</span></div>
    </div>
  );
}

export function FundsPane() {
  const { data: profile, error: pErr } = useKiteProfile(true);
  const { data: margins, error: mErr, isLoading } = useKiteMargins(true);
  const segs = margins && typeof margins === 'object' ? Object.entries(margins).filter(([, v]) => v && typeof v === 'object') : [];

  return (
    <div>
      <div style={S.card}>
        <div style={S.title}>PROFILE</div>
        {pErr && <div style={{ color: t.red, fontSize: 11 }}>✗ {(pErr as Error).message}</div>}
        {profile && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <span style={{ fontWeight: 800, color: t.bright, fontSize: 15 }}>{profile.user_name || profile.user_shortname || '—'}</span>
              <span style={S.pill}>{profile.user_id}</span>
              <span style={{ ...S.pill, color: t.dim, borderColor: t.border, background: t.bg }}>{profile.broker}</span>
            </div>
            <div style={S.row}><span style={S.k}>Email</span><span style={S.v}>{profile.email}</span></div>
            <div style={S.row}><span style={S.k}>Exchanges</span><span style={S.v}>{(profile.exchanges || []).join(', ')}</span></div>
            <div style={{ ...S.row, borderBottom: 'none' }}><span style={S.k}>Products / Order types</span><span style={S.v}>{(profile.products || []).join(', ')} · {(profile.order_types || []).join(', ')}</span></div>
          </>
        )}
        {!profile && !pErr && <div style={S.hint}>Connect a live session to load your profile.</div>}
      </div>

      <div style={S.title}>FUNDS &amp; MARGINS</div>
      {isLoading && <div style={S.hint}>Loading…</div>}
      {mErr && <div style={{ color: t.red, fontSize: 11 }}>✗ {(mErr as Error).message}</div>}
      {segs.length > 0 ? (
        <div style={S.grid}>
          {segs.map(([seg, info]) => <SegmentCard key={seg} seg={seg} info={info} />)}
        </div>
      ) : (!isLoading && !mErr && <div style={S.hint}>No funds data — connect a live session.</div>)}
    </div>
  );
}
