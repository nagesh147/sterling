/**
 * Graphical folder chooser for the market-data lake.
 *
 * Two ways to pick, because users arrive with different information:
 *  - **Volumes** — a one-click list of mounted drives with free space, flagged when a lake
 *    is already stored there. This is the path for "just use my USB stick".
 *  - **Browse** — a directory walker for anywhere else on the machine.
 *
 * Rendered through a portal onto `document.body`: Sterling's `.term-root > * { z-index: 1 }`
 * rule traps modals rendered inside the page tree, which makes them appear *behind* the
 * content.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { c, tint } from '../../styles/terminalUI';
import type { BrowseResult, LakeVolume } from '../../hooks/useDataLake';

interface Props {
  open: boolean;
  onClose: () => void;
  onChoose: (path: string, label: string) => Promise<unknown>;
  listVolumes: () => Promise<{ volumes: LakeVolume[]; error: string }>;
  browse: (path?: string, showHidden?: boolean) => Promise<BrowseResult>;
  /** Suggested sub-folder name when the user picks a bare volume root. */
  defaultFolderName?: string;
}

type Tab = 'volumes' | 'browse';

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

export default function FolderPicker({
  open,
  onClose,
  onChoose,
  listVolumes,
  browse,
  defaultFolderName = 'SterlingLake',
}: Props) {
  const [tab, setTab] = useState<Tab>('volumes');
  const [volumes, setVolumes] = useState<LakeVolume[]>([]);
  const [listing, setListing] = useState<BrowseResult | null>(null);
  const [selected, setSelected] = useState('');
  const [folderName, setFolderName] = useState(defaultFolderName);
  const [label, setLabel] = useState('');
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState('');
  const [showHidden, setShowHidden] = useState(false);

  // True only when the user picked a bare drive root that does NOT already hold a lake;
  // in that case we offer a named subfolder so bars/ and manifest/ don't litter the root.
  // An existing lake path is already the final folder and must be used verbatim.
  const isVolumeRoot = useMemo(
    () => volumes.some((v) => v.path === selected && !v.lake_at),
    [volumes, selected],
  );
  const finalPath = useMemo(() => {
    if (!selected) return '';
    return isVolumeRoot ? `${selected.replace(/\/$/, '')}/${folderName}` : selected;
  }, [selected, isVolumeRoot, folderName]);

  const load = useCallback(async () => {
    setProblem('');
    try {
      const [vols, home] = await Promise.all([listVolumes(), browse(undefined, showHidden)]);
      setVolumes(vols.volumes ?? []);
      setListing(home);
      if (vols.error) setProblem(vols.error);
    } catch (e) {
      setProblem(e instanceof Error ? e.message : 'could not read volumes');
    }
  }, [listVolumes, browse, showHidden]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const go = useCallback(
    async (path: string) => {
      setProblem('');
      try {
        const next = await browse(path, showHidden);
        setListing(next);
        setSelected(next.path);
        if (next.error) setProblem(next.error);
      } catch (e) {
        setProblem(e instanceof Error ? e.message : 'could not open that folder');
      }
    },
    [browse, showHidden],
  );

  const confirm = useCallback(async () => {
    if (!finalPath) return;
    setBusy(true);
    setProblem('');
    try {
      await onChoose(finalPath, label);
      onClose();
    } catch (e) {
      // The backend returns the full remediation text (including the exact sudo command
      // for a root-owned mount point), so show it verbatim rather than summarising.
      setProblem(e instanceof Error ? e.message : 'could not use that folder');
    } finally {
      setBusy(false);
    }
  }, [finalPath, label, onChoose, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Choose the market-data folder"
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.85)',
        // Must beat `.term-root > * { z-index: 1 }`; see the module docstring.
        zIndex: 10050,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: c.surface,
          border: `1px solid ${c.border}`,
          borderRadius: 18,
          width: 'min(760px, 96vw)',
          maxHeight: '88vh',
          display: 'flex',
          flexDirection: 'column',
          fontFamily: c.fontFamily,
          boxShadow: '0 8px 40px rgba(0,0,0,0.45)',
        }}
      >
        {/* header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: `1px solid ${c.border}`,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ color: c.bright, fontWeight: 700, fontSize: 15 }}>
              Where should market data be stored?
            </div>
            <div style={{ color: c.dim, fontSize: 11.5, marginTop: 3 }}>
              Pick any folder — a USB drive is ideal. It is remembered by identity, so it
              keeps working even if the drive reconnects at a different path.
            </div>
          </div>
          <button onClick={onClose} style={{ ...btn(c.muted), padding: '4px 10px' }}>
            ✕
          </button>
        </div>

        {/* tabs */}
        <div style={{ display: 'flex', gap: 8, padding: '12px 20px 0' }}>
          {(['volumes', 'browse'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                ...btn(tab === t ? c.green : c.muted, tab === t),
                textTransform: 'capitalize',
              }}
            >
              {t === 'volumes' ? 'Drives' : 'Browse folders'}
            </button>
          ))}
          <div style={{ flex: 1 }} />
          <button onClick={() => void load()} style={btn(c.muted)}>
            Rescan
          </button>
        </div>

        {/* body */}
        <div style={{ padding: 16, overflowY: 'auto', flex: 1 }}>
          {tab === 'volumes' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {volumes.length === 0 && (
                <div style={{ color: c.dim, fontSize: 12 }}>No mounted volumes detected.</div>
              )}
              {volumes.map((v) => {
                // A drive that already HOLDS a lake is selectable even when its own root
                // is not writable — and that is the common case, not an edge case. A
                // freshly formatted USB drive has a root-owned root, so `sudo install -d`
                // grants ownership of the lake subfolder only. Picking that existing lake
                // never writes to the drive root, so gating on root writability disabled
                // exactly the drive the user was trying to choose.
                const target = v.lake_at || v.path;
                const usable = v.writable || !!v.lake_at;
                const chosen = selected === target;
                return (
                  <button
                    key={v.path}
                    onClick={() => setSelected(target)}
                    disabled={!usable}
                    title={
                      v.lake_at
                        ? `${v.lake_at} — existing data found here, click to use it`
                        : v.writable
                          ? v.path
                          : `${v.path} is owned by root, so a new folder cannot be created ` +
                            `here. Grant yourself one:\n\n` +
                            `sudo install -d -o "$USER" -g "$USER" -m 755 ` +
                            `"${v.path.replace(/\/$/, '')}/${defaultFolderName}"`
                    }
                    style={{
                      textAlign: 'left',
                      background: chosen ? tint(c.green, 14) : c.raised,
                      border: `1px solid ${chosen ? c.green : c.border}`,
                      borderRadius: 12,
                      padding: '10px 12px',
                      cursor: usable ? 'pointer' : 'not-allowed',
                      opacity: usable ? 1 : 0.5,
                      fontFamily: c.fontFamily,
                      display: 'flex',
                      justifyContent: 'space-between',
                      gap: 12,
                      alignItems: 'center',
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div
                        style={{
                          color: c.bright,
                          fontSize: 12.5,
                          fontWeight: 600,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {v.label || v.path}
                        {v.removable && (
                          <span style={{ color: c.cyan, fontSize: 10, marginLeft: 8 }}>
                            REMOVABLE
                          </span>
                        )}
                        {v.lake_at && (
                          <span style={{ color: c.green, fontSize: 10, marginLeft: 8 }}>
                            DATA FOUND{v.lake_label ? ` · ${v.lake_label}` : ''}
                          </span>
                        )}
                        {/* Only flag write permission when it actually blocks the user:
                            a drive holding an existing lake is usable regardless. */}
                        {!v.writable && !v.lake_at && (
                          <span style={{ color: c.amber, fontSize: 10, marginLeft: 8 }}>
                            NEEDS PERMISSION
                          </span>
                        )}
                      </div>
                      <div style={{ color: c.dim, fontSize: 11, marginTop: 2 }}>
                        {v.path} · {v.fstype}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <div style={{ color: c.bright, fontSize: 12.5, fontWeight: 600 }}>
                        {v.free_gib} GiB
                      </div>
                      <div style={{ color: c.dim, fontSize: 10.5 }}>free of {v.total_gib}</div>
                    </div>
                  </button>
                );
              })}
              {volumes.some((v) => !v.writable && !v.lake_at) && (
                <div style={{ color: c.dim, fontSize: 11, marginTop: 2, lineHeight: 1.6 }}>
                  A freshly-formatted drive keeps a root-owned root, so a new folder cannot
                  be created on it until you grant yourself one. Hover a greyed-out drive for
                  the exact one-line command. Drives that already hold data stay selectable —
                  using an existing folder needs no permission on the drive root.
                </div>
              )}
            </div>
          )}

          {tab === 'browse' && listing && (
            <div>
              <div
                style={{
                  display: 'flex',
                  gap: 8,
                  alignItems: 'center',
                  marginBottom: 10,
                  flexWrap: 'wrap',
                }}
              >
                <button
                  onClick={() => listing.parent && void go(listing.parent)}
                  disabled={!listing.parent}
                  style={{ ...btn(c.muted), opacity: listing.parent ? 1 : 0.4 }}
                >
                  ↑ Up
                </button>
                <code
                  style={{
                    color: c.bright,
                    fontSize: 11.5,
                    background: c.raised,
                    border: `1px solid ${c.border}`,
                    borderRadius: 8,
                    padding: '6px 10px',
                    flex: 1,
                    minWidth: 200,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {listing.path}
                </code>
                <label style={{ color: c.dim, fontSize: 11, display: 'flex', gap: 5 }}>
                  <input
                    type="checkbox"
                    checked={showHidden}
                    onChange={(e) => {
                      setShowHidden(e.target.checked);
                      void browse(listing.path, e.target.checked).then(setListing);
                    }}
                  />
                  hidden
                </label>
                <button
                  onClick={() => setSelected(listing.path)}
                  style={btn(selected === listing.path ? c.green : c.blue, selected === listing.path)}
                >
                  Use this folder
                </button>
              </div>
              <div style={{ color: c.dim, fontSize: 11, marginBottom: 8 }}>
                {listing.free_gib} GiB free ·{' '}
                {listing.writable ? 'writable' : 'not writable by your user'}
              </div>
              <div
                style={{
                  border: `1px solid ${c.border}`,
                  borderRadius: 10,
                  maxHeight: 280,
                  overflowY: 'auto',
                }}
              >
                {listing.entries.length === 0 && (
                  <div style={{ color: c.dim, fontSize: 12, padding: 12 }}>
                    No sub-folders here.
                  </div>
                )}
                {listing.entries.map((e) => (
                  <div
                    key={e.path}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '7px 12px',
                      borderBottom: `1px solid ${c.border2}`,
                      background: selected === e.path ? tint(c.green, 12) : 'transparent',
                    }}
                  >
                    <button
                      onClick={() => void go(e.path)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: c.bright,
                        fontSize: 12,
                        cursor: 'pointer',
                        fontFamily: c.fontFamily,
                        padding: 0,
                        textAlign: 'left',
                      }}
                    >
                      📁 {e.name}
                      {e.has_lake && (
                        <span style={{ color: c.green, fontSize: 10, marginLeft: 8 }}>
                          DATA FOUND{e.lake_label ? ` · ${e.lake_label}` : ''}
                        </span>
                      )}
                      {!e.writable && (
                        <span style={{ color: c.amber, fontSize: 10, marginLeft: 8 }}>RO</span>
                      )}
                    </button>
                    <button onClick={() => setSelected(e.path)} style={btn(c.muted)}>
                      Select
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* footer */}
        <div style={{ padding: '14px 20px', borderTop: `1px solid ${c.border}` }}>
          {isVolumeRoot && (
            <div
              style={{
                display: 'flex',
                gap: 8,
                alignItems: 'center',
                marginBottom: 10,
                flexWrap: 'wrap',
              }}
            >
              <span style={{ color: c.dim, fontSize: 11 }}>Subfolder on the drive:</span>
              <input
                value={folderName}
                onChange={(e) => setFolderName(e.target.value.replace(/[^\w.-]/g, ''))}
                style={{
                  background: c.raised,
                  border: `1px solid ${c.border}`,
                  borderRadius: 8,
                  color: c.bright,
                  padding: '5px 9px',
                  fontSize: 12,
                  width: 180,
                  minWidth: 0,
                  fontFamily: c.fontFamily,
                }}
              />
              <span style={{ color: c.dim, fontSize: 11 }}>keeps the drive root tidy</span>
            </div>
          )}
          <div
            style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}
          >
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Name this location (optional)"
              style={{
                background: c.raised,
                border: `1px solid ${c.border}`,
                borderRadius: 8,
                color: c.bright,
                padding: '7px 10px',
                fontSize: 12,
                flex: 1,
                minWidth: 160,
                fontFamily: c.fontFamily,
              }}
            />
            <button onClick={onClose} style={btn(c.muted)}>
              Cancel
            </button>
            <button
              onClick={() => void confirm()}
              disabled={!finalPath || busy}
              style={{ ...btn(c.green, true), opacity: !finalPath || busy ? 0.45 : 1 }}
            >
              {busy ? 'Setting up…' : 'Use this folder'}
            </button>
          </div>
          {finalPath && (
            <div style={{ color: c.dim, fontSize: 11, marginTop: 8 }}>
              Data will be stored in <code style={{ color: c.cyan }}>{finalPath}</code>
            </div>
          )}
          {problem && (
            <pre
              style={{
                color: c.amber,
                fontSize: 11,
                marginTop: 10,
                whiteSpace: 'pre-wrap',
                background: tint(c.amber, 10),
                border: `1px solid ${tint(c.amber, 35)}`,
                borderRadius: 8,
                padding: 10,
                maxHeight: 160,
                overflowY: 'auto',
              }}
            >
              {problem}
            </pre>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
