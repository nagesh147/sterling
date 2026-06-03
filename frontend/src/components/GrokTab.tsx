import React, { useState } from 'react';
import { ThreeColumnLayout, LeftSection, RightSection } from './ThreeColumnLayout';
import { GrokSignalPane } from './GrokSignalPane';
import { GrokSettingsPane } from './GrokSettingsPane';
import { GrokLogsPane } from './GrokLogsPane';
import { useSignals } from '../hooks/useSignals';
import { usePositions } from '../hooks/usePositions';
import { ExecLog } from './scalping/ScalpingTab';
import { useRouterMode } from '../hooks/useRouterMode';
import { card, alpha } from '../styles/terminalUI';

export function GrokTab() {
  const { data } = useSignals();
  const { data: positionsData } = usePositions();
  const activePositions = positionsData?.positions || [];
  const { mode: routerMode } = useRouterMode();
  
  const [trackFilter, setTrackFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [profileFilter, setProfileFilter] = useState('all');
  const [execLog, setExecLog] = useState<any[]>([]);
  const [settingsDrawer, setSettingsDrawer] = useState(false);

  const signals = data?.signals || [];
  
  const getSignalStatus = (s: any) => {
    if (activePositions.some((p: any) => p.underlying === s.underlying)) return 'open';
    if (s.direction === 'long' || s.direction === 'short') return 'ready';
    return 'idle';
  };
  


  const trackNavItems = [
    { id: 'all', label: 'All Tracks', color: 'var(--t-bright)' },
    { id: 'vcp', label: 'VCP', color: 'var(--t-amber)' },
    { id: 'trend_following', label: 'Trend Following', color: 'var(--t-green)' },
    { id: 'mean_reversion', label: 'Mean Reversion', color: 'var(--t-purple)' },
  ];

  const statusNavItems = [
    { id: 'all', label: 'All Statuses', color: 'var(--t-bright)' },
    { id: 'open', label: 'Open', color: 'var(--t-blue)' },
    { id: 'ready', label: 'Ready (Armed)', color: 'var(--t-green)' },
    { id: 'idle', label: 'Idle', color: 'var(--t-dim)' },
  ];

  const profileNavItems = [
    { id: 'all', label: 'All Profiles', color: 'var(--t-bright)' },
    { id: 'intraday', label: 'Intraday', color: 'var(--t-cyan)' },
    { id: 'scalping', label: 'Scalping', color: 'var(--t-orange)' },
    { id: 'aggressive', label: 'Aggressive', color: 'var(--t-red)' },
  ];

  const renderNavGroup = (items: {id: string, label: string, color: string, count?: number}[], active: string, onClick: (id: string) => void) => (
    <>
      {items.map((item) => {
        const isActive = active === item.id;
          const count = item.id === 'all' 
            ? signals.length 
            : items === trackNavItems
              ? signals.filter(s => s.track === item.id).length
              : items === statusNavItems
                ? signals.filter(s => getSignalStatus(s) === item.id).length
                : signals.filter(s => (s.profile?.toLowerCase() || 'scalping') === item.id).length;

        return (
          <button key={item.id} onClick={() => onClick(item.id)} style={{
            display: 'flex', alignItems: 'center', gap: 10, width: '100%',
            padding: '10px 12px', borderRadius: 8, cursor: 'pointer', fontFamily: 'inherit',
            background: isActive ? `var(--t-bg)` : 'transparent',
            border: isActive ? `1px solid var(--t-border)` : '1px solid transparent',
            color: isActive ? item.color : 'var(--t-muted)',
            marginBottom: 4, transition: 'all .2s ease',
            transform: isActive ? 'translateX(2px)' : 'none'
          }}>
            <div style={{ width: 8, height: 8, borderRadius: 4, background: item.color, flexShrink: 0, opacity: isActive ? 1 : 0.6 }} />
            <span style={{ fontSize: 11, fontWeight: isActive ? 700 : 600, letterSpacing: '0.02em' }}>{item.label}</span>
            <span style={{ marginLeft: 'auto', fontSize: 10, fontWeight: 700, opacity: 0.8 }}>{count}</span>
          </button>
        );
      })}
    </>
  );

  return (
    <>
      <ThreeColumnLayout
        leftWidth={280}
        rightWidth={340}
        leftSidebar={<>
          <LeftSection label="Tools" collapsible defaultOpen>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button
                onClick={() => setSettingsDrawer(true)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                  padding: '10px 12px', borderRadius: 'var(--radius-md)', cursor: 'pointer', fontFamily: 'inherit',
                  border: '1px solid var(--t-border)',
                  background: 'transparent',
                  color: 'var(--t-dim)', transition: 'all .1s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.05)';
                  e.currentTarget.style.color = 'var(--t-bright)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = 'var(--t-dim)';
                }}
              >
                <span style={{ fontSize: 12 }}>⚙</span>
                <span style={{ fontSize: 11, fontWeight: 600 }}>Global Strategy Config</span>
              </button>
            </div>
          </LeftSection>

          <LeftSection label="Tracks" collapsible defaultOpen>
            {renderNavGroup(trackNavItems, trackFilter, setTrackFilter)}
          </LeftSection>
          <LeftSection label="Profiles" collapsible defaultOpen>
            {renderNavGroup(profileNavItems, profileFilter, setProfileFilter)}
          </LeftSection>
          <LeftSection label="Status" collapsible defaultOpen>
            {renderNavGroup(statusNavItems, statusFilter, setStatusFilter)}
          </LeftSection>
          <LeftSection label="Exec Log" collapsible defaultOpen>
            <div style={{ marginTop: 8 }}>
              <ExecLog entries={execLog} mode={routerMode || 'PAPER'} />
              {execLog.length > 0 && (
                <button onClick={() => setExecLog([])} style={{
                  fontSize: 9, fontWeight: 700, padding: '4px 8px', borderRadius: 4,
                  background: 'transparent', border: '1px solid var(--t-border)',
                  color: 'var(--t-dim)', cursor: 'pointer', marginTop: 8, width: '100%'
                }}>CLEAR EXEC LOG</button>
              )}
            </div>
          </LeftSection>
        </>}
        centerHeader={<>
          <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>Arbitrator Signals</div>
          <div style={{ fontSize: 10, color: 'var(--t-dim)', marginTop: 1 }}>Live signals passing statistical robustness thresholds</div>
        </>}
        centerContent={
          <div style={{ padding: 16 }}>
            <div style={{ ...card, height: '100%' }}>
              <GrokSignalPane 
                trackFilter={trackFilter} 
                statusFilter={statusFilter} 
                profileFilter={profileFilter} 
                logExec={(e) => setExecLog(l => [e, ...l].slice(0, 40))} 
              />
            </div>
          </div>
        }
        rightSidebar={<>
          <RightSection label="Execution Logs">
            <GrokLogsPane />
          </RightSection>
        </>}
      />


      {settingsDrawer && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: alpha('var(--t-bg)', 0.9), backdropFilter: 'blur(4px)',
          zIndex: 100, display: 'flex', justifyContent: 'flex-start',
        }}>
          <div style={{
            width: 480, height: '100%', background: 'var(--t-bg)',
            borderRight: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column',
          }}>
            <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 16, flex: 1, overflowY: 'auto' }}>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: '0.04em', color: 'var(--t-bright)' }}>Arbitrator Configuration</div>
                  <div style={{ fontSize: 11, color: 'var(--t-dim)', marginTop: 2 }}>Manage robustness thresholds and strategy gates</div>
                </div>
                <button onClick={() => setSettingsDrawer(false)} title="Close (Esc)" style={{
                  marginLeft: 'auto', fontSize: 16, lineHeight: 1, background: 'none',
                  border: '1px solid var(--t-border)', borderRadius: 6, color: 'var(--t-dim)',
                  width: 30, height: 30, cursor: 'pointer', fontFamily: 'inherit',
                }}>×</button>
              </div>
              <GrokSettingsPane />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
