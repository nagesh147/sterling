import React from 'react';
import { useOrbSignals } from '../../hooks/useOrbSignals';

const fmt=(v:number|null,dp=2)=>v==null?'—':v.toFixed(dp);
const stateStyle=(state:string):React.CSSProperties=>({fontSize:9,fontWeight:700,letterSpacing:'0.08em',color:state==='SIGNAL'?'var(--accent)':state==='SIGNAL_UNRESOLVED'?'var(--warning,#d99000)':state==='ERROR'||state==='REJECTED'?'var(--danger,#d9534f)':'var(--text-dim)'});

export function NiftyOrbSignalsPanel(){
  const {signals,isLoading,isError,isRefreshing}=useOrbSignals(true);
  return <div style={{fontSize:11,color:'var(--text-primary)'}}>
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:10}}>
      <div style={{color:'var(--text-dim)',fontSize:10}}>REALTIME · MULTI-UNDERLYING · BUY OPTIONS ONLY</div>
      <div style={{color:'var(--text-faint)',fontSize:9}}>{isRefreshing?'SCANNING':'IDLE'} · 5s</div>
    </div>
    {isLoading&&<div style={{padding:'14px 0',color:'var(--text-dim)'}}>Scanning ORB universe…</div>}
    {isError&&<div style={{padding:'10px 0',color:'var(--danger,#d9534f)'}}>ORB signal feed unavailable.</div>}
    {!isLoading&&!signals.length&&!isError&&<div style={{padding:'14px 0',color:'var(--text-dim)'}}>No ORB signals in the configured universe.</div>}
    {!!signals.length&&<div style={{overflowX:'auto'}}><table style={{width:'100%',borderCollapse:'collapse',fontSize:10,minWidth:980}}><thead><tr>{['UNDERLYING','STATE','DIR','SPOT','ORB','VWAP','VOL','OPTION','EXPIRY','PREM','SL','TARGET','QTY','RISK','DATA'].map(h=><th key={h} style={{textAlign:'left',padding:'7px 6px',borderBottom:'1px solid var(--border)',color:'var(--text-faint)',fontWeight:600,fontSize:9,letterSpacing:'0.06em'}}>{h}</th>)}</tr></thead><tbody>{signals.map(s=><tr key={s.id}>{[
      <b>{s.underlying}</b>,<span style={stateStyle(s.state)}>{s.state}</span>,<span>{s.optionType||'—'}</span>,<span>{fmt(s.spot)}</span>,<span>{s.orHigh==null?'—':`${fmt(s.orHigh)}/${fmt(s.orbLow)}`}</span>,<span>{fmt(s.vwap)}</span>,<span>{s.volumeRatio==null?'—':`${fmt(s.volumeRatio)}x`}</span>,<span>{s.optionSymbol||'—'}</span>,<span>{s.optionExpiry||'—'}</span>,<span>{fmt(s.optionPremium)}</span>,<span>{fmt(s.stopPremium)}</span>,<span>{fmt(s.targetPremium)}</span>,<span>{s.quantity??'—'}</span>,<span>{s.riskInr==null?'—':`₹${Math.round(s.riskInr).toLocaleString('en-IN')}`}</span>,<span>{s.dataSource||'—'}</span>
    ].map((cell,i)=><td key={i} style={{padding:'7px 6px',borderBottom:'1px solid var(--border)',whiteSpace:'nowrap'}}>{cell}</td>)}</tr>)}</tbody></table></div>}
  </div>;
}
