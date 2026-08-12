/**
 * Data-lake status panel.
 *
 * The whole point of this component is what it does when the data is *missing*. A drive
 * that is out is shown in amber with the reason and concrete next steps — never a red
 * error, never a stack trace — and because the hook keeps polling, plugging the drive back
 * in makes the panel recover by itself.
 */
import { useCallback, useEffect, useState } from 'react';
import { c, tint } from '../../styles/terminalUI';
import { useDataLake, type TierPlan } from '../../hooks/useDataLake';
import FolderPicker from './FolderPicker';

/** Default window: the last ~6 months, which is what the tier costs are quoted for. */
function defaultRange(): { frm: string; to: string } {
  const to = new Date();
  const frm = new Date(to.getTime() - 182 * 86_400_000);
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  return { frm: iso(frm), to: iso(to) };
}

const box: React.CSSProperties = {
  background: c.surface,
  border: `1px solid ${c.border}`,
  borderRadius: 14,
  fontFamily: c.fontFamily,
};

const btn = (tone: string, solid = false): React.CSSProperties => ({
  background: solid ? tone : 'transparent',
  color: solid ? c.bg : tone,
  border: `1px solid ${tone}`,
  borderRadius: 10,
  padding: '7px 14px',
  fontSize: 12,
  fontWeight: 600,
  cursor: 'pointer',
  fontFamily: c.fontFamily,
});

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div
      style={{
        background: c.raised,
        border: `1px solid ${c.border}`,
        borderRadius: 10,
        padding: '9px 12px',
        minWidth: 120,
      }}
    >
      <div style={{ color: c.dim, fontSize: 10.5, textTransform: 'uppercase', letterSpacing: 0.4 }}>
        {label}
      </div>
      <div style={{ color: tone || c.bright, fontSize: 15, fontWeight: 700, marginTop: 2 }}>
        {value}
      </div>
    </div>
  );
}

export default function DataLakePanel({ interval = 'minute' }: { interval?: string }) {
  const {
    summary, loading, error, refresh, listVolumes, browse, setRoot, activateRoot, tierPlan,
  } = useDataLake(interval);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [plan, setPlan] = useState<TierPlan | null>(null);
  const [planError, setPlanError] = useState('');

  const available = summary?.available ?? false;
  const stats = summary?.stats ?? {};

  const loadPlan = useCallback(async () => {
    const { frm, to } = defaultRange();
    try {
      setPlan(await tierPlan(frm, to));
      setPlanError('');
    } catch (e) {
      // Usually just "instrument master not synced yet" — informational, not a failure.
      setPlanError(e instanceof Error ? e.message : 'tier costs unavailable');
      setPlan(null);
    }
  }, [tierPlan]);

  useEffect(() => {
    if (available) void loadPlan();
  }, [available, loadPlan]);

  return (
    <div style={{ ...box, padding: 0, overflow: 'hidden' }}>
      {/* header */}
      <div
        style={{
          padding: '14px 18px',
          borderBottom: `1px solid ${c.border}`,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              color: c.bright,
              fontWeight: 700,
              fontSize: 14,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: 4,
                background: loading ? c.muted : available ? c.green : c.amber,
                display: 'inline-block',
              }}
            />
            Offline Market Data
          </div>
          <div
            style={{
              color: c.dim,
              fontSize: 11.5,
              marginTop: 3,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {loading
              ? 'checking…'
              : available
                ? `${summary?.label || 'data folder'} · ${summary?.root}`
                : 'no data folder available'}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => void refresh()} style={btn(c.muted)}>
            Refresh
          </button>
          <button onClick={() => setPickerOpen(true)} style={btn(c.blue, !available)}>
            {available ? 'Change folder' : 'Choose folder'}
          </button>
        </div>
      </div>

      <div style={{ padding: 16 }}>
        {/* Backend unreachable is a real fault — distinguish it from a missing drive. */}
        {error && (
          <div
            style={{
              color: c.red,
              fontSize: 12,
              background: tint(c.red, 10),
              border: `1px solid ${tint(c.red, 35)}`,
              borderRadius: 10,
              padding: 10,
              marginBottom: 12,
            }}
          >
            Cannot reach the backend: {error}
          </div>
        )}

        {/* ── unavailable: guidance, not an error ───────────────────────── */}
        {!loading && !available && summary && (
          <div
            style={{
              background: tint(c.amber, 8),
              border: `1px solid ${tint(c.amber, 32)}`,
              borderRadius: 12,
              padding: 14,
            }}
          >
            <div style={{ color: c.amber, fontSize: 13, fontWeight: 700 }}>
              {summary.volume_present_unmounted
                ? 'The drive is connected but not mounted'
                : summary.reason || 'The data folder is not available'}
            </div>
            <ul style={{ margin: '10px 0 0', paddingLeft: 18, color: c.text, fontSize: 12 }}>
              {(summary.guidance ?? []).map((g, i) => (
                <li key={i} style={{ marginBottom: 4 }}>
                  {g}
                </li>
              ))}
            </ul>

            {summary.last_path && (
              <div style={{ color: c.dim, fontSize: 11.5, marginTop: 10 }}>
                Last seen at <code style={{ color: c.cyan }}>{summary.last_path}</code>
              </div>
            )}

            {/* One-click adoption of any writable volume detected right now. */}
            {(summary.candidates ?? []).length > 0 && (
              <div style={{ marginTop: 12 }}>
                <div style={{ color: c.dim, fontSize: 11, marginBottom: 6 }}>
                  Available now — click to use:
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {summary.candidates.slice(0, 4).map((v) => (
                    <button
                      key={v.path}
                      onClick={() =>
                        void setRoot(
                          v.lake_at || `${v.path.replace(/\/$/, '')}/SterlingLake`,
                          v.label,
                        ).catch(() => setPickerOpen(true))
                      }
                      style={btn(v.lake_at ? c.green : c.blue)}
                      title={v.path}
                    >
                      {v.lake_at ? '↩ ' : '+ '}
                      {v.label || v.path} · {v.free_gib} GiB
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Previously-used folders: re-activating is one click. */}
            {(summary.known ?? []).length > 0 && (
              <div style={{ marginTop: 12 }}>
                <div style={{ color: c.dim, fontSize: 11, marginBottom: 6 }}>
                  Previously used:
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {summary.known.slice(0, 4).map((k) => (
                    <button
                      key={k.lake_id}
                      onClick={() => void activateRoot(k.lake_id).catch(() => setPickerOpen(true))}
                      style={btn(c.muted)}
                      title={k.last_path}
                    >
                      {k.label || k.last_path}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div style={{ color: c.dim, fontSize: 11, marginTop: 12 }}>
              Nothing is lost while the folder is away — reads and downloads simply pause,
              and resume where they left off once it is back.
            </div>
          </div>
        )}

        {/* ── available: what we hold ───────────────────────────────────── */}
        {available && (
          <>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <Stat label="Free space" value={`${summary?.free_gib ?? 0} GiB`} />
              <Stat label="Instruments" value={(stats.symbols ?? 0).toLocaleString()} />
              <Stat label="Bars stored" value={(stats.candles ?? 0).toLocaleString()} />
              <Stat label="On disk" value={`${stats.gib ?? 0} GiB`} />
              <Stat
                label="Complete"
                value={`${stats.pct_complete ?? 0}%`}
                tone={(stats.pct_complete ?? 0) >= 99.5 ? c.green : c.amber}
              />
            </div>

            {typeof stats.chunks_total === 'number' && stats.chunks_total > 0 && (
              <div style={{ marginTop: 14 }}>
                <div
                  style={{
                    height: 6,
                    background: c.raised,
                    borderRadius: 3,
                    overflow: 'hidden',
                    border: `1px solid ${c.border}`,
                  }}
                >
                  <div
                    style={{
                      width: `${Math.min(100, stats.pct_complete ?? 0)}%`,
                      height: '100%',
                      background: c.green,
                    }}
                  />
                </div>
                <div style={{ color: c.dim, fontSize: 11, marginTop: 6 }}>
                  {(stats.chunks_settled ?? 0).toLocaleString()} of{' '}
                  {(stats.chunks_total ?? 0).toLocaleString()} chunks done ·{' '}
                  {(stats.chunks_remaining ?? 0).toLocaleString()} remaining
                </div>
              </div>
            )}

            {/* ── the three nested tiers ─────────────────────────────────── */}
            {plan && (
              <div style={{ marginTop: 18 }}>
                <div
                  style={{
                    color: c.bright,
                    fontSize: 12.5,
                    fontWeight: 700,
                    marginBottom: 2,
                  }}
                >
                  Download plan · {plan.frm} → {plan.to} · {plan.rate} req/s
                </div>
                <div style={{ color: c.dim, fontSize: 11, marginBottom: 8 }}>
                  The three universes are nested, so each tier only fetches what the ones
                  before it did not. Running all three costs{' '}
                  {plan.total_requests.toLocaleString()} requests, not{' '}
                  {plan.naive_requests.toLocaleString()} — the ledger skips the{' '}
                  {plan.requests_saved_by_dedup.toLocaleString()}-request overlap.
                </div>
                <div style={{ overflowX: 'auto' }}>
                  <table
                    style={{
                      borderCollapse: 'collapse',
                      fontSize: 11.5,
                      color: c.text,
                      minWidth: 520,
                      width: '100%',
                    }}
                  >
                    <thead>
                      <tr style={{ color: c.dim, textAlign: 'right' }}>
                        <th style={{ textAlign: 'left', padding: '4px 8px' }}>Tier</th>
                        <th style={{ padding: '4px 8px' }}>Instruments</th>
                        <th style={{ padding: '4px 8px' }}>New</th>
                        <th style={{ padding: '4px 8px' }}>Requests</th>
                        <th style={{ padding: '4px 8px' }}>ETA</th>
                        <th style={{ padding: '4px 8px' }}>Size</th>
                        <th style={{ padding: '4px 8px' }}>Done by</th>
                      </tr>
                    </thead>
                    <tbody>
                      {plan.tiers.map((t) => (
                        <tr
                          key={t.universe}
                          style={{ borderTop: `1px solid ${c.border2}`, textAlign: 'right' }}
                        >
                          <td style={{ textAlign: 'left', padding: '5px 8px', color: c.bright }}>
                            {t.tier}. {t.universe}
                          </td>
                          <td style={{ padding: '5px 8px' }}>
                            {t.instruments.toLocaleString()}
                          </td>
                          <td style={{ padding: '5px 8px', color: c.cyan }}>
                            +{t.new_instruments.toLocaleString()}
                          </td>
                          <td style={{ padding: '5px 8px' }}>
                            {t.requests_incremental.toLocaleString()}
                          </td>
                          <td style={{ padding: '5px 8px' }}>{t.eta_incremental}</td>
                          <td style={{ padding: '5px 8px' }}>
                            {t.est_gib_incremental.toFixed(2)} GiB
                          </td>
                          <td style={{ padding: '5px 8px', color: c.bright }}>
                            {t.cumulative_eta}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div style={{ color: c.dim, fontSize: 11, marginTop: 8 }}>
                  Total {plan.total_instruments.toLocaleString()} instruments ·{' '}
                  {plan.total_eta} · {plan.total_gib.toFixed(1)} GiB
                  {summary && summary.free_gib < plan.total_gib && (
                    <span style={{ color: c.amber }}>
                      {' '}
                      — only {summary.free_gib} GiB free, which may not be enough
                    </span>
                  )}
                </div>
                <div style={{ color: c.dim, fontSize: 11, marginTop: 6 }}>
                  Start it with{' '}
                  <code style={{ color: c.cyan }}>
                    kitelake download --tiers --interval {plan.interval} --from {plan.frm} --to{' '}
                    {plan.to}
                  </code>
                </div>
              </div>
            )}
            {planError && !plan && (
              <div style={{ color: c.dim, fontSize: 11.5, marginTop: 14 }}>
                Tier costs unavailable — sync the instrument master first
                (<code>kitelake instruments</code>).
              </div>
            )}

            {/* Readiness hints: the two things that block a download. */}
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 14 }}>
              {summary?.has_credentials === false && (
                <div style={{ color: c.amber, fontSize: 11.5 }}>
                  No Kite session — run <code>kitelake auth</code> before downloading
                  (tokens expire daily).
                </div>
              )}
              {summary?.instrument_master_age_hours == null && (
                <div style={{ color: c.amber, fontSize: 11.5 }}>
                  Instrument master not synced — run <code>kitelake instruments</code>.
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <FolderPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onChoose={(path, label) => setRoot(path, label)}
        listVolumes={listVolumes}
        browse={browse}
      />
    </div>
  );
}
