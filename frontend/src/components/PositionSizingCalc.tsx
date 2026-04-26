import React, { useState } from 'react';
import { useRiskConfig } from '../hooks/useRiskConfig';
import { fmtN, fmtUSD } from '../utils/fmt';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 14 },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 14 },
  field: { display: 'flex', flexDirection: 'column', gap: 4 },
  label: { color: '#555', fontSize: 10, letterSpacing: 1 },
  input: { background: '#111', color: '#e0e0e0', border: '1px solid #2a2a2a', borderRadius: 3, padding: '6px 8px', fontFamily: 'inherit', fontSize: 13 },
  results: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, background: '#0d1a0d', border: '1px solid #44cc88' + '22', borderRadius: 4, padding: 12 },
  cell: { display: 'flex', flexDirection: 'column', gap: 3 },
  key: { color: '#555', fontSize: 10, letterSpacing: 1 },
  val: { fontSize: 16, fontWeight: 700 },
  warn: { color: '#cc4444', fontSize: 11, marginTop: 8 },
};

function calcSize(capital: number, riskPct: number, maxLossPerContract: number) {
  if (maxLossPerContract <= 0) return null;
  const maxRisk = capital * (riskPct / 100);
  const contracts = Math.max(1, Math.floor(maxRisk / maxLossPerContract));
  const totalRisk = contracts * maxLossPerContract;
  const actualRiskPct = (totalRisk / capital) * 100;
  const breakEvenMove = (totalRisk / capital) * 100;
  return { contracts, totalRisk, actualRiskPct, breakEvenMove };
}

export function PositionSizingCalc() {
  const { data: riskConfig } = useRiskConfig();
  const [capital, setCapital] = useState('');
  const [riskPct, setRiskPct] = useState('');
  const [maxLoss, setMaxLoss] = useState('');
  const [premium, setPremium] = useState('');

  const cap = parseFloat(capital) || riskConfig?.capital || 100000;
  const rp = parseFloat(riskPct) || (riskConfig ? riskConfig.max_position_pct * 100 : 5);
  const ml = parseFloat(maxLoss) || parseFloat(premium) || 0;

  const result = ml > 0 ? calcSize(cap, rp, ml) : null;
  const maxContractsGuard = riskConfig?.max_contracts ?? 10;
  const clampedContracts = result ? Math.min(result.contracts, maxContractsGuard) : null;
  const clamped = clampedContracts !== null && result && clampedContracts < result.contracts;

  return (
    <div style={S.card}>
      <div style={S.title}>POSITION SIZING CALCULATOR</div>
      <div style={S.grid}>
        <div style={S.field}>
          <label style={S.label}>ACCOUNT CAPITAL ($)</label>
          <input style={S.input} type="number" placeholder={String(riskConfig?.capital ?? 100000)}
            value={capital} onChange={e => setCapital(e.target.value)} />
        </div>
        <div style={S.field}>
          <label style={S.label}>RISK PER TRADE (%)</label>
          <input style={S.input} type="number" step="0.5" placeholder={String((riskConfig?.max_position_pct ?? 0.05) * 100)}
            value={riskPct} onChange={e => setRiskPct(e.target.value)} />
        </div>
        <div style={S.field}>
          <label style={S.label}>MAX LOSS / CONTRACT ($)</label>
          <input style={S.input} type="number" placeholder="e.g. 500 (option premium)"
            value={maxLoss} onChange={e => setMaxLoss(e.target.value)} />
        </div>
        <div style={S.field}>
          <label style={S.label}>OPTION PREMIUM ($) [if naked]</label>
          <input style={S.input} type="number" placeholder="e.g. 420"
            value={premium} onChange={e => setPremium(e.target.value)} />
        </div>
        <div style={S.field}>
          <label style={S.label}>MAX CONTRACTS (config)</label>
          <input style={{ ...S.input, color: '#555' }} readOnly value={maxContractsGuard} />
        </div>
      </div>

      {result ? (
        <div style={S.results}>
          <div style={S.cell}>
            <span style={S.key}>CONTRACTS</span>
            <span style={{ ...S.val, color: clamped ? '#f0a500' : '#44cc88' }}>
              {clampedContracts}
              {clamped && <span style={{ fontSize: 10, color: '#f0a500' }}> (capped)</span>}
            </span>
          </div>
          <div style={S.cell}>
            <span style={S.key}>MAX RISK $</span>
            <span style={{ ...S.val, color: '#ff8844' }}>
              ${fmtUSD(clampedContracts! * ml)}
            </span>
          </div>
          <div style={S.cell}>
            <span style={S.key}>CAPITAL AT RISK</span>
            <span style={{ ...S.val, color: result.actualRiskPct > 5 ? '#cc4444' : '#44cc88' }}>
              {fmtN((clampedContracts! * ml / cap) * 100, 2)}%
            </span>
          </div>
          <div style={S.cell}>
            <span style={S.key}>POSITION VALUE $</span>
            <span style={{ ...S.val, color: '#ccc', fontSize: 14 }}>
              ${fmtUSD(clampedContracts! * (parseFloat(premium) || ml))}
            </span>
          </div>
        </div>
      ) : (
        <div style={{ color: '#444', fontSize: 12 }}>
          Enter max loss per contract (or option premium) to calculate position size.
        </div>
      )}

      {result && result.actualRiskPct > (riskConfig?.max_position_pct ?? 0.05) * 100 * 1.5 && (
        <div style={S.warn}>
          ⚠ Risk {result.actualRiskPct.toFixed(1)}% exceeds configured max {((riskConfig?.max_position_pct ?? 0.05) * 100).toFixed(1)}% — reduce size or tighten stop.
        </div>
      )}
    </div>
  );
}
