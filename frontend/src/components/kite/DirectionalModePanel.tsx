import React, { useState } from 'react';
import type { EngineConfigModel, Vehicle, DeepItmMoneyness } from '../../types/kiteEngine';

// ─── Profile definitions ──────────────────────────────────────────────────────
// Each profile maps to specific backend config fields. The user picks a profile;
// the internal directional_mode / vehicle / target_delta fields are derived.

type ProfileId = 'otm' | 'atm' | 'slight_itm' | 'deep_itm' | 'futures';

interface ProfileDef {
  id: ProfileId;
  label: string;
  sublabel: string;
  delta: number;          // representative mid-range delta for this profile
  deltaLabel: string;     // display string
  thetaPctPerDay: number; // rough % of premium lost per day to theta
  color: string;
  desc: string;
  risk: string;
  isExperimental: boolean;
  // Rough premium relative to an ATM option (=1.0), used only for the
  // at-a-glance comparison. Real prices always come from the live chain.
  premiumMult: number;
  // backend fields this profile sets
  vehicle: Vehicle;
  directional: boolean;
  targetDelta: number | null;
}

const PROFILES: ProfileDef[] = [
  {
    id: 'otm',
    label: 'OTM',
    sublabel: 'Out of the Money',
    delta: 0.28, deltaLabel: 'δ 0.20 – 0.35',
    thetaPctPerDay: 3.5,
    color: '#1565c0',
    desc: 'Cheapest entry per lot. High leverage if a big move comes fast — but theta decay is brutal. The option loses ~3–4% of its premium every single day the market does nothing. You need the move to happen quickly.',
    risk: 'Max loss is exactly what you paid — nothing more. But time decay is your biggest enemy.',
    isExperimental: false, premiumMult: 0.4,
    vehicle: 'otm_options', directional: false, targetDelta: 0.28,
  },
  {
    id: 'atm',
    label: 'ATM',
    sublabel: 'At the Money',
    delta: 0.50, deltaLabel: 'δ 0.45 – 0.55',
    thetaPctPerDay: 2.0,
    color: '#2e7d32',
    desc: 'The default. Best liquidity and tightest bid-ask spreads. You capture roughly half of every point the underlying moves. Theta is still present (~2%/day) but more manageable than OTM.',
    risk: 'Max loss is the premium paid. Standard risk-reward. Most traders start here.',
    isExperimental: false, premiumMult: 1.0,
    vehicle: 'otm_options', directional: false, targetDelta: 0.50,
  },
  {
    id: 'slight_itm',
    label: 'Slight ITM',
    sublabel: 'In the Money',
    delta: 0.65, deltaLabel: 'δ 0.60 – 0.70',
    thetaPctPerDay: 1.0,
    color: '#e65100',
    desc: 'More intrinsic value, less time value. Theta slows down significantly. You pay more upfront, but a larger chunk of your premium is "real" value that doesn\'t melt away with time.',
    risk: 'Max loss is the premium paid. Higher cost per lot means fewer lots for the same capital.',
    isExperimental: true, premiumMult: 1.8,
    vehicle: 'deep_itm_options', directional: true, targetDelta: 0.65,
  },
  {
    id: 'deep_itm',
    label: 'Deep ITM',
    sublabel: 'High Delta',
    delta: 0.87, deltaLabel: 'δ 0.80 – 0.95',
    thetaPctPerDay: 0.2,
    color: '#6a1b9a',
    desc: 'Moves almost point-for-point with the index. Barely any theta — most of the premium is intrinsic value. Expensive per lot, but behaves the closest to trading the index itself with a defined-risk wrapper.',
    risk: 'Max loss is the premium paid (which is large per lot). Very few lots affordable per ₹1L of capital.',
    isExperimental: true, premiumMult: 4.0,
    vehicle: 'deep_itm_options', directional: true, targetDelta: 0.87,
  },
  {
    id: 'futures',
    label: 'Futures',
    sublabel: 'Index Future',
    delta: 1.0, deltaLabel: 'δ = 1.00',
    thetaPctPerDay: 0,
    color: '#b71c1c',
    desc: 'Pure index exposure. Every point the index moves, you gain or lose that exact amount. No premium, no theta, no IV crush. Bear signal goes short, bull goes long. The trail stop is your only protection.',
    risk: 'No premium floor — losses are unlimited beyond the stop. Requires margin (~12–15% of contract value). Validate in Paper mode first.',
    isExperimental: true, premiumMult: 0,
    vehicle: 'futures', directional: true, targetDelta: null,
  },
];

const ITM_DEPTH_OPTIONS: { value: DeepItmMoneyness; label: string; desc: string }[] = [
  { value: 'ITM5',  label: 'ITM-5',  desc: 'δ ≈ 0.75 — some theta still present' },
  { value: 'ITM10', label: 'ITM-10', desc: 'δ ≈ 0.85 — minimal theta bleed' },
  { value: 'ITM15', label: 'ITM-15', desc: 'δ ≈ 0.92 — near-futures behaviour' },
  { value: 'ITM20', label: 'ITM-20', desc: 'δ ≈ 0.96 — closest to trading futures outright' },
];

// Derive which profile the current config represents.
// NOTE: target_delta is clamped to [0.50, 0.99] by the backend, so it cannot
// distinguish OTM (≈0.28) from ATM (≈0.50). OTM vs ATM is therefore tracked via
// strike_moneyness, which round-trips cleanly.
function deriveActiveProfile(cfg: EngineConfigModel): ProfileId {
  if (cfg.vehicle === 'futures' && cfg.directional_mode) return 'futures';
  if (cfg.vehicle === 'deep_itm_options' && cfg.directional_mode) {
    const d = cfg.target_delta ?? 0.85;
    return d >= 0.78 ? 'deep_itm' : 'slight_itm';
  }
  // otm_options path — OTM if every selected strike is out-of-the-money.
  const sm = cfg.strike_moneyness ?? [];
  const allOtm = sm.length > 0 && sm.every(m => m.startsWith('OTM'));
  return allOtm ? 'otm' : 'atm';
}

// Build the config patch for selecting a profile.
function profilePatch(p: ProfileDef, cfg: EngineConfigModel): Partial<EngineConfigModel> {
  const patch: Partial<EngineConfigModel> = {
    vehicle: p.vehicle,
    directional_mode: p.directional,
    target_delta: p.targetDelta,
  };
  // OTM vs ATM is persisted through the scan ladder (target_delta can't hold it).
  if (p.id === 'otm')      patch.strike_moneyness = ['OTM1', 'OTM2'];
  else if (p.id === 'atm') patch.strike_moneyness = ['ATM'];
  // Auto-enable the vehicle in the allow-list if it isn't already.
  if (!cfg.enabled_vehicles.includes(p.vehicle)) {
    patch.enabled_vehicles = [...cfg.enabled_vehicles, p.vehicle];
  }
  return patch;
}

// ─── Config defaults (mirror EngineConfigModel) ───────────────────────────────
// Used to flag when a setting has been changed from its default and to show the
// user what the default was. Keep in sync with backend schemas.py.
const DEFAULTS = {
  profile: 'atm' as ProfileId,
  itm_depth: 'ITM10',
  futures_expiry: 'near',
  adx_min: null as number | null,
  atr_pct_min: null as number | null,
  wire_risk_infra: false,
};
const PROFILE_LABEL: Record<ProfileId, string> = {
  otm: 'OTM', atm: 'ATM', slight_itm: 'Slight ITM', deep_itm: 'Deep ITM', futures: 'Futures',
};

// A small inline "changed from default" chip. Renders nothing when at default.
function DefaultNote({ changed, defaultText }: { changed: boolean; defaultText: string }) {
  if (!changed) return null;
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, color: '#e65100', background: '#fff3e0',
      border: '1px solid #ffcc80', borderRadius: 3, padding: '1px 6px',
      marginLeft: 6, whiteSpace: 'nowrap',
    }}>
      ● CHANGED · default {defaultText}
    </span>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────
const S: Record<string, React.CSSProperties> = {
  card:        { background: '#fff', border: '1px solid #e0e0e0', borderRadius: 6, padding: 16, marginBottom: 14 },
  section:     { fontSize: 10, fontWeight: 700, letterSpacing: 1.2, color: '#9b9b9b', textTransform: 'uppercase' as const, marginBottom: 10 },
  hint:        { fontSize: 11, color: '#9b9b9b', lineHeight: 1.5 },
  divider:     { height: 1, background: '#f0f0f0', margin: '14px 0' },
  row:         { display: 'flex', alignItems: 'center', gap: 8 },
  filterRow:   { display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 10 },
  filterLabel: { fontSize: 11, color: '#444', lineHeight: 1.5 },
  numInput:    { width: 64, fontSize: 11, padding: '4px 8px', border: '1px solid #ddd', borderRadius: 4, textAlign: 'right' as const, fontFamily: 'inherit' },
  select:      { fontSize: 11, padding: '4px 8px', border: '1px solid #ddd', borderRadius: 4, background: '#fff', fontFamily: 'inherit' },
  toggle:      { width: 36, height: 18, borderRadius: 9, cursor: 'pointer', border: 'none', position: 'relative' as const, transition: 'background 0.2s', flexShrink: 0 },
  toggleDot:   { width: 14, height: 14, borderRadius: 7, background: '#fff', position: 'absolute' as const, top: 2, transition: 'left 0.2s', boxShadow: '0 1px 2px rgba(0,0,0,.2)' },
};

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  cfg: EngineConfigModel;
  onUpdate: (patch: Partial<EngineConfigModel>) => void;
  busy?: boolean;
  // Live values pulled from the latest ready signal so the calculator pre-fills
  // with real numbers instead of generic defaults. Undefined = no live signal yet.
  liveLotSize?: number;
  livePremium?: number;
  liveUnderlying?: string;
}

export function DirectionalModePanel({ cfg, onUpdate, busy, liveLotSize, livePremium, liveUnderlying }: Props) {
  const [simMove, setSimMove]       = useState(100);   // underlying pts to simulate
  const [simPremium, setSimPremium] = useState(livePremium && livePremium > 0 ? Math.round(livePremium) : 150);
  const [lotSize, setLotSize]       = useState(liveLotSize && liveLotSize > 0 ? liveLotSize : 75);
  const [customDelta, setCustomDelta] = useState('');  // delta override input
  const [userEdited, setUserEdited] = useState(false); // once true, stop auto-syncing from live

  // Pre-fill from the live signal when it arrives — but never clobber a value the
  // user has typed themselves.
  React.useEffect(() => {
    if (userEdited) return;
    if (livePremium && livePremium > 0) setSimPremium(Math.round(livePremium));
    if (liveLotSize && liveLotSize > 0) setLotSize(liveLotSize);
  }, [livePremium, liveLotSize, userEdited]);

  const activeId      = deriveActiveProfile(cfg);
  const activeProfile = PROFILES.find(p => p.id === activeId)!;
  const isFutures     = activeId === 'futures';

  const effectiveDelta  = customDelta ? parseFloat(customDelta) || activeProfile.delta : activeProfile.delta;
  const optionMove      = +(effectiveDelta * simMove).toFixed(1);
  const thetaDaily      = +(activeProfile.thetaPctPerDay / 100 * simPremium).toFixed(1);
  const breakEvenPts    = isFutures ? 0 : Math.round(simPremium / effectiveDelta);
  const daysToEatGain   = thetaDaily > 0 && optionMove > 0 ? Math.floor(optionMove / thetaDaily) : null;

  // Rough intrinsic / time-value split: intrinsicFraction ≈ max(0, (delta-0.5)×2)
  const intrinsicFrac   = Math.max(0, Math.min(1, (effectiveDelta - 0.5) * 2));
  const intrinsicAmt    = Math.round(simPremium * intrinsicFrac);
  const timeValueAmt    = simPremium - intrinsicAmt;

  // δ ≈ probability the option finishes in-the-money at expiry (option buyer's
  // rough win-odds if held to expiry). Futures have no such notion.
  const probItm         = Math.round(effectiveDelta * 100);

  // Per-lot rupee figures — what the per-share numbers actually mean in money.
  const perLotGain      = Math.round((isFutures ? simMove : optionMove) * lotSize);
  const perLotCost      = isFutures ? null : Math.round(simPremium * lotSize);
  const perLotThetaDay  = isFutures ? 0 : Math.round(thetaDaily * lotSize);

  // The active profile's anchor multiple, so other profiles scale relative to
  // whatever ATM-equivalent premium the user typed.
  const anchorMult      = activeProfile.premiumMult || 1;

  return (
    <div style={S.card}>

      {/* ── 1. Profile selector ─────────────────────────────────────────────── */}
      <div style={{ ...S.section, display: 'flex', alignItems: 'center' }}>
        HOW DO YOU WANT TO TRADE THE SIGNAL?
        <DefaultNote changed={activeId !== DEFAULTS.profile} defaultText={PROFILE_LABEL[DEFAULTS.profile]} />
      </div>

      <div style={{ display: 'flex', gap: 5, marginBottom: 12, flexWrap: 'wrap' as const }}>
        {PROFILES.map(p => {
          const active = p.id === activeId;
          return (
            <button
              key={p.id}
              disabled={busy}
              onClick={() => { setCustomDelta(''); onUpdate(profilePatch(p, cfg)); }}
              style={{
                flex: '1 1 56px', padding: '8px 4px', borderRadius: 6,
                border: `2px solid ${active ? p.color : '#e0e0e0'}`,
                background: active ? p.color + '14' : '#fafafa',
                cursor: busy ? 'default' : 'pointer',
                textAlign: 'center' as const, transition: 'all 0.15s',
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 700, color: active ? p.color : '#555' }}>{p.label}</div>
              <div style={{ fontSize: 9, color: active ? p.color : '#bbb', marginTop: 2 }}>{p.deltaLabel}</div>
            </button>
          );
        })}
      </div>

      {/* Active profile description card */}
      <div style={{
        padding: '10px 12px', borderRadius: 5, marginBottom: 10,
        background: activeProfile.color + '0d', border: `1px solid ${activeProfile.color}33`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: activeProfile.color }}>{activeProfile.sublabel}</span>
          {activeProfile.isExperimental && (
            <span style={{ fontSize: 9, fontWeight: 700, background: activeProfile.color, color: '#fff', padding: '1px 5px', borderRadius: 3 }}>
              EXPERIMENTAL
            </span>
          )}
        </div>
        <div style={{ fontSize: 11, color: '#444', lineHeight: 1.55, marginBottom: 5 }}>{activeProfile.desc}</div>
        <div style={{ fontSize: 10, color: '#777', lineHeight: 1.4, marginBottom: isFutures ? 0 : 5 }}>⚡ {activeProfile.risk}</div>
        {!isFutures && (
          <div style={{ fontSize: 10, color: activeProfile.color, lineHeight: 1.4, fontWeight: 600 }}>
            🎯 δ {effectiveDelta.toFixed(2)} ≈ {probItm}% chance of finishing in-the-money at expiry.
            {probItm < 40 && ' Most OTM buys expire worthless — you win big occasionally, lose small often.'}
            {probItm >= 40 && probItm < 60 && ' Roughly coin-flip odds at expiry, but you only need a quick move, not expiry.'}
            {probItm >= 60 && ' Favourable odds — you are paying up for a higher-probability position.'}
          </div>
        )}
      </div>

      {/* Custom delta override */}
      {!isFutures && (
        <div style={{ ...S.row, marginBottom: 4, flexWrap: 'wrap' as const }}>
          <span style={{ ...S.hint, flexShrink: 0 }}>Custom delta override:</span>
          <input
            type="number"
            style={{
              ...S.numInput, width: 72,
              ...(customDelta ? { borderColor: '#e65100', background: '#fff8f2', fontWeight: 700 } : {}),
            }}
            value={customDelta}
            placeholder={activeProfile.delta.toFixed(2)}
            step={0.05} min={0.10} max={0.99}
            onChange={e => {
              setCustomDelta(e.target.value);
              const d = parseFloat(e.target.value);
              if (d >= 0.10 && d <= 0.99) {
                const v: Vehicle = d >= 0.55 ? 'deep_itm_options' : 'otm_options';
                onUpdate({ target_delta: d, vehicle: v, directional_mode: d >= 0.55 });
              }
            }}
            disabled={busy}
          />
          {customDelta && (
            <button
              style={{ fontSize: 10, color: '#999', background: 'none', border: 'none', cursor: 'pointer', padding: '0 4px' }}
              onClick={() => { setCustomDelta(''); onUpdate(profilePatch(activeProfile, cfg)); }}
            >✕ clear</button>
          )}
          <DefaultNote changed={!!customDelta} defaultText={`profile δ ${activeProfile.delta.toFixed(2)}`} />
          {!customDelta && <span style={{ ...S.hint }}>Overrides the profile's default strike selection.</span>}
        </div>
      )}

      {/* ── 2. Vehicle-specific config ─────────────────────────────────────── */}
      {(activeId === 'slight_itm' || activeId === 'deep_itm') && (
        <>
          <div style={S.divider} />
          <div style={{ ...S.section, display: 'flex', alignItems: 'center' }}>
            STRIKE DEPTH (FALLBACK)
            <DefaultNote changed={(cfg.itm_depth || 'ITM10') !== DEFAULTS.itm_depth} defaultText={DEFAULTS.itm_depth} />
          </div>
          <div style={S.filterRow}>
            <span style={S.filterLabel}>
              Used when no live delta match is available.
            </span>
            <select
              style={S.select}
              value={cfg.itm_depth || 'ITM10'}
              onChange={e => onUpdate({ itm_depth: e.target.value as DeepItmMoneyness })}
              disabled={busy}
            >
              {ITM_DEPTH_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label} — {o.desc}</option>
              ))}
            </select>
          </div>
        </>
      )}

      {activeId === 'futures' && (
        <>
          <div style={S.divider} />
          <div style={{ ...S.section, display: 'flex', alignItems: 'center' }}>
            FUTURES EXPIRY
            <DefaultNote changed={cfg.futures_expiry !== DEFAULTS.futures_expiry} defaultText="near-month" />
          </div>
          <div style={S.filterRow}>
            <span style={S.filterLabel}>Which contract series to trade.</span>
            <select
              style={S.select}
              value={cfg.futures_expiry}
              onChange={e => onUpdate({ futures_expiry: e.target.value as 'near' | 'next' })}
              disabled={busy}
            >
              <option value="near">Near-month — lowest spread, most liquid</option>
              <option value="next">Next-month — more time before expiry</option>
            </select>
          </div>
        </>
      )}

      {/* ── 3. Trade impact calculator ─────────────────────────────────────── */}
      <div style={S.divider} />
      <div style={S.section}>TRADE IMPACT CALCULATOR</div>
      <div style={{ ...S.hint, marginBottom: 10 }}>
        {(livePremium || liveLotSize) && !userEdited
          ? <>Pre-filled from the latest ready signal{liveUnderlying ? ` (${liveUnderlying})` : ''}. Edit any field to explore other scenarios.</>
          : <>Adjust the inputs below to see how this profile behaves on your trade.</>}
      </div>

      {/* Simulator inputs */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap' as const }}>
        <div style={{ flex: '1 1 120px' }}>
          <div style={{ fontSize: 10, color: '#9b9b9b', marginBottom: 4, fontWeight: 600 }}>UNDERLYING MOVES</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <input type="number" style={{ ...S.numInput, flex: 1 }}
              value={simMove} min={10} max={2000} step={25}
              onChange={e => setSimMove(Math.max(10, Number(e.target.value) || 100))} />
            <span style={S.hint}>pts</span>
          </div>
        </div>
        {!isFutures && (
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: 10, color: '#9b9b9b', marginBottom: 4, fontWeight: 600 }}>YOUR ENTRY PREMIUM</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={S.hint}>₹</span>
              <input type="number" style={{ ...S.numInput, flex: 1 }}
                value={simPremium} min={10} max={5000} step={10}
                onChange={e => { setUserEdited(true); setSimPremium(Math.max(10, Number(e.target.value) || 150)); }} />
            </div>
          </div>
        )}
        <div style={{ flex: '1 1 100px' }}>
          <div style={{ fontSize: 10, color: '#9b9b9b', marginBottom: 4, fontWeight: 600 }}>LOT SIZE</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <input type="number" style={{ ...S.numInput, flex: 1 }}
              value={lotSize} min={1} max={10000} step={5}
              onChange={e => { setUserEdited(true); setLotSize(Math.max(1, Number(e.target.value) || 75)); }} />
            <span style={S.hint}>qty/lot</span>
          </div>
        </div>
      </div>

      {/* Impact rows */}
      <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 7 }}>

        <ImpactRow icon="📈" color="#2e7d32"
          label={`Underlying moves ${simMove} pts in your direction`}
          value={`+₹${perLotGain.toLocaleString('en-IN')} / lot`}
          sub={isFutures
            ? `δ = 1.00 — moves exactly 1:1 with the index. +₹${isFutures ? simMove : optionMove}/share × ${lotSize} qty.`
            : `δ ${effectiveDelta.toFixed(2)} × ${simMove} pts = +₹${optionMove}/share × ${lotSize} qty. The rest of the move doesn't reach you.`}
        />

        <ImpactRow icon="📉" color="#c62828"
          label={`Underlying moves ${simMove} pts against you`}
          value={isFutures ? `−₹${perLotGain.toLocaleString('en-IN')} / lot (until stop)` : `−₹${perLotGain.toLocaleString('en-IN')} / lot premium loss`}
          sub={isFutures
            ? `Stop exits at the trail level — loss is capped at (entry − stop) × ${lotSize} qty, not this full amount.`
            : `Your option still has remaining value. Actual P&L also depends on IV at exit.`}
        />

        {!isFutures && (
          <ImpactRow icon="⏳" color="#e65100"
            label="Daily theta — what you lose if the market does nothing"
            value={`−₹${perLotThetaDay.toLocaleString('en-IN')} / lot / day`}
            sub={`≈ ${activeProfile.thetaPctPerDay}% of your ₹${simPremium} premium (₹${thetaDaily}/share) disappears each calendar day. Weekends included.`}
          />
        )}

        {isFutures && (
          <ImpactRow icon="⏳" color="#2e7d32"
            label="Daily theta — what you lose if the market does nothing"
            value="₹0 — zero time decay"
            sub="Futures carry no premium, so there is no theta. You hold with margin instead of paying for time."
          />
        )}

        {!isFutures && (
          <ImpactRow icon="⚖️" color="#1565c0"
            label="Break-even — underlying must move at least"
            value={`${breakEvenPts} pts in your direction`}
            sub={`₹${simPremium} premium ÷ δ ${effectiveDelta.toFixed(2)} = ${breakEvenPts} pts just to recover your entry cost at expiry.`}
          />
        )}

        {!isFutures && daysToEatGain !== null && (
          <ImpactRow icon="🕐" color="#6a1b9a"
            label={`If underlying moves ${simMove} pts today, theta erodes that gain in`}
            value={`${daysToEatGain} day${daysToEatGain !== 1 ? 's' : ''} of flat market`}
            sub={`₹${optionMove} gain ÷ ₹${thetaDaily}/day decay. Don't let a winning trade sit and bleed to theta.`}
          />
        )}

        <ImpactRow icon="🛡️" color={isFutures ? '#c62828' : '#555'}
          label="Maximum possible loss"
          value={isFutures ? 'Trail stop distance × lot — no fixed cap' : `₹${perLotCost?.toLocaleString('en-IN')} / lot — what you paid`}
          sub={isFutures
            ? `No floor. The trail stop is the only thing limiting your loss — honour it.`
            : `Options cannot go below zero. Your loss is always capped at the ₹${simPremium}/share premium (₹${perLotCost?.toLocaleString('en-IN')}/lot).`}
        />

      </div>

      {/* Premium breakdown bar (options only) */}
      {!isFutures && (
        <>
          <div style={{ ...S.divider, marginTop: 12 }} />
          <div style={{ fontSize: 10, fontWeight: 600, color: '#9b9b9b', marginBottom: 8 }}>
            PREMIUM BREAKDOWN (APPROXIMATE) — ₹{simPremium} total
          </div>
          <div style={{ height: 14, borderRadius: 7, overflow: 'hidden', display: 'flex', marginBottom: 8 }}>
            <div style={{ width: `${intrinsicFrac * 100}%`, background: '#2e7d32', transition: 'width 0.35s', minWidth: intrinsicFrac > 0 ? 4 : 0 }} />
            <div style={{ flex: 1, background: '#e65100', opacity: 0.75 }} />
          </div>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' as const }}>
            <span style={{ fontSize: 10, color: '#2e7d32' }}>
              ■ Intrinsic value ≈ ₹{intrinsicAmt}
              <span style={{ color: '#9b9b9b' }}> — real value, doesn't decay</span>
            </span>
            <span style={{ fontSize: 10, color: '#e65100' }}>
              ■ Time value ≈ ₹{timeValueAmt}
              <span style={{ color: '#9b9b9b' }}> — theta eats this daily</span>
            </span>
          </div>
          {intrinsicFrac === 0 && (
            <div style={{ ...S.hint, marginTop: 6 }}>
              OTM options have zero intrinsic value — your entire ₹{simPremium} is time value subject to decay.
            </div>
          )}
          <div style={{ ...S.hint, marginTop: 8, padding: '6px 9px', background: '#fff8e1', borderRadius: 4, border: '1px solid #ffe082' }}>
            ⚡ <strong>IV crush risk:</strong> that ₹{timeValueAmt} of time value is also sensitive to implied
            volatility. After a big expected event (results, budget, RBI) IV often collapses — your option can
            lose value <em>even if the underlying moves your way</em>. Higher-delta profiles carry less time
            value and so less IV-crush exposure.
          </div>
        </>
      )}

      {/* ── 3b. At-a-glance profile comparison ──────────────────────────────── */}
      <div style={S.divider} />
      <div style={S.section}>SAME {simMove}-PT MOVE — EVERY PROFILE COMPARED</div>
      <div style={{ ...S.hint, marginBottom: 8 }}>
        How each profile would behave on this exact move. Premiums are rough estimates
        anchored to your ₹{simPremium} input — real prices come from the live chain.
      </div>
      <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 4 }}>
        {PROFILES.map(p => {
          const d         = p.id === 'futures' ? 1 : p.delta;
          const gainSh    = +(d * simMove).toFixed(0);
          const estPrem   = p.id === 'futures' ? null : Math.round(simPremium * (p.premiumMult / anchorMult));
          // Capital efficiency: ₹ gain per ₹100 of premium deployed (options only).
          const effic     = estPrem && estPrem > 0 ? Math.round((gainSh / estPrem) * 100) : null;
          const isActiveP = p.id === activeId;
          return (
            <div key={p.id}
              onClick={() => { if (!busy) { setCustomDelta(''); onUpdate(profilePatch(p, cfg)); } }}
              style={{
                display: 'grid', gridTemplateColumns: '74px 1fr 1fr 1fr', gap: 6, alignItems: 'center',
                padding: '7px 9px', borderRadius: 5, cursor: busy ? 'default' : 'pointer',
                background: isActiveP ? p.color + '14' : '#fafafa',
                border: `1px solid ${isActiveP ? p.color + '55' : '#f0f0f0'}`,
              }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: p.color }}>{p.label}</span>
              <span style={{ fontSize: 10, color: '#444' }}>
                <span style={{ color: '#999' }}>gain</span> +₹{gainSh}/sh
              </span>
              <span style={{ fontSize: 10, color: '#444' }}>
                <span style={{ color: '#999' }}>cost</span> {estPrem === null ? 'margin' : `₹${estPrem}/sh`}
              </span>
              <span style={{ fontSize: 10, color: '#444' }}>
                {p.id === 'futures'
                  ? <><span style={{ color: '#999' }}>decay</span> none</>
                  : <><span style={{ color: '#999' }}>×eff</span> {effic}%</>}
              </span>
            </div>
          );
        })}
      </div>
      <div style={{ ...S.hint, marginTop: 6 }}>
        <strong>gain</strong> = δ × move captured per share · <strong>cost</strong> = est. premium per share ·
        <strong> ×eff</strong> = ₹ gain per ₹100 of premium (higher = more leverage, but more decay/IV risk).
      </div>

      {/* ── 4. Entry quality filters ────────────────────────────────────────── */}
      <div style={S.divider} />
      <div style={S.section}>ENTRY QUALITY FILTERS</div>
      <div style={{ ...S.hint, marginBottom: 12 }}>
        Optional gates. When set, the engine skips signals where the trend is too weak or
        volatility too low. Applies to all profiles — OTM, deep ITM, and futures alike.
      </div>

      <div style={S.filterRow}>
        <span style={S.filterLabel}>
          <span style={{ display: 'flex', alignItems: 'center' }}>
            Min ADX
            <DefaultNote changed={cfg.adx_min !== DEFAULTS.adx_min} defaultText="off" />
          </span>
          <span style={{ ...S.hint, display: 'block' }}>
            Trend strength (0–100). 20 = decent trend forming. 30 = strong.
            40+ = very strong, rare. Leave blank to accept all signals.
          </span>
        </span>
        <input type="number"
          style={{ ...S.numInput, ...(cfg.adx_min !== DEFAULTS.adx_min ? { borderColor: '#e65100', background: '#fff8f2', fontWeight: 700 } : {}) }}
          value={cfg.adx_min ?? ''} placeholder="off"
          step={1} min={5} max={50}
          onChange={e => onUpdate({ adx_min: e.target.value ? parseFloat(e.target.value) : null })}
          disabled={busy}
        />
      </div>

      <div style={S.filterRow}>
        <span style={S.filterLabel}>
          <span style={{ display: 'flex', alignItems: 'center' }}>
            Min ATR %ile
            <DefaultNote changed={cfg.atr_pct_min !== DEFAULTS.atr_pct_min} defaultText="off" />
          </span>
          <span style={{ ...S.hint, display: 'block' }}>
            Volatility rank vs the past year (0–100). 50 = market is moving more
            than half its historical range. Higher = only trade when it's volatile.
          </span>
        </span>
        <input type="number"
          style={{ ...S.numInput, ...(cfg.atr_pct_min !== DEFAULTS.atr_pct_min ? { borderColor: '#e65100', background: '#fff8f2', fontWeight: 700 } : {}) }}
          value={cfg.atr_pct_min ?? ''} placeholder="off"
          step={5} min={10} max={95}
          onChange={e => onUpdate({ atr_pct_min: e.target.value ? parseFloat(e.target.value) : null })}
          disabled={busy}
        />
      </div>

      {/* ── 5. Risk infrastructure ──────────────────────────────────────────── */}
      <div style={S.divider} />
      <div style={{ ...S.section, display: 'flex', alignItems: 'center' }}>
        RISK INFRASTRUCTURE
        <DefaultNote changed={cfg.wire_risk_infra !== DEFAULTS.wire_risk_infra} defaultText="off" />
      </div>

      <div style={{ ...S.row, marginBottom: 8 }}>
        <button
          style={{ ...S.toggle, background: cfg.wire_risk_infra ? '#ff9800' : '#ccc' }}
          onClick={() => onUpdate({ wire_risk_infra: !cfg.wire_risk_infra })}
          disabled={busy}
        >
          <span style={{ ...S.toggleDot, left: cfg.wire_risk_infra ? 20 : 2 }} />
        </button>
        <span style={{ fontSize: 12, fontWeight: 600, color: cfg.wire_risk_infra ? '#ff9800' : '#999' }}>
          {cfg.wire_risk_infra ? 'ON' : 'OFF'}
        </span>
      </div>
      <div style={S.hint}>
        Wires two safety layers into every entry:
        <br />• <strong>Drawdown circuit breaker</strong> — if your account drops 5%/10%/15%, new position
        sizes are scaled down automatically, then entries are halted.
        <br />• <strong>Correlation penalty</strong> — if you already hold a position correlated with the
        new signal (e.g. Nifty and BankNifty moving together), the new lot size is reduced to avoid
        doubling up on the same risk.
        <br /><br />Applies to all profiles. Recommended once you run more than one position at a time.
      </div>

    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function ImpactRow({ icon, label, value, sub, color }: {
  icon: string; label: string; value: string; sub: string; color: string;
}) {
  return (
    <div style={{
      display: 'flex', gap: 10, padding: '9px 11px',
      background: '#fafafa', borderRadius: 6, border: '1px solid #f0f0f0',
    }}>
      <span style={{ fontSize: 15, flexShrink: 0, lineHeight: '1.5', paddingTop: 1 }}>{icon}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 10, color: '#888', marginBottom: 3 }}>{label}</div>
        <div style={{ fontSize: 13, fontWeight: 700, color, marginBottom: 3 }}>{value}</div>
        <div style={{ fontSize: 10, color: '#999', lineHeight: 1.45 }}>{sub}</div>
      </div>
    </div>
  );
}

export default DirectionalModePanel;
