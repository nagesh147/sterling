import React from 'react';
import { useNiftyOrbSignals } from '../hooks/useNiftyOrbSignals';

const cell:React.CSSProperties={padding:'8px 9px',borderBottom:'1px solid var(--t-border)',fontSize:10,whiteSpace:'nowrap'};

export function NiftyOrbSignalsTable(){
 const {data,isLoading,error}=useNiftyOrbSignals(true);
 if(isLoading)return <div style={{padding:12,color:'var(--t-dim)',fontSize:10}}>Scanning ORB universe…</div>;
 if(error)return <div style={{padding:12,color:'var(--t-red)',fontSize:10}}>ORB signal feed unavailable: {(error as Error).message}</div>;
 const rows=data?.signals||[];
 return <div style={{width:'100%',overflowX:'auto',border:'1px solid var(--t-border)',borderRadius:6,background:'var(--t-bg)'}}>
  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'9px 11px',borderBottom:'1px solid var(--t-border)'}}>
   <div style={{fontSize:10,fontWeight:600,letterSpacing:'0.1em',color:'var(--t-bright)'}}>ORB SIGNALS</div>
   <div style={{fontSize:9,color:'var(--t-dim)'}}>{data?.signal_count||0} actionable · {data?.universe?.length||0} scanned · {data?.data_source==='truedata'?'TrueData':'Kite'}</div>
  </div>
  <table style={{width:'100%',borderCollapse:'collapse',fontFamily:'monospace'}}>
   <thead><tr>{['Instrument','Status','Direction','Spot','Option','Strike','Expiry','Entry','SL','Target','Risk'].map(x=><th key={x} style={{...cell,textAlign:'left',color:'var(--t-dim)',fontWeight:500}}>{x}</th>)}</tr></thead>
   <tbody>{rows.map(row=>{
    const s=row.signal;const t=row.trade;const active=row.status==='signal';
    return <tr key={row.underlying}>
     <td style={{...cell,color:'var(--t-bright)',fontWeight:600}}>{row.underlying}</td>
     <td style={{...cell,color:active?'var(--t-green)':row.status==='error'?'var(--t-red)':'var(--t-dim)'}}>{active?'SIGNAL':row.status==='signal_unresolved'?'UNRESOLVED':row.status==='watching'?'WATCHING':row.status.toUpperCase()}</td>
     <td style={{...cell,color:s?.direction==='LONG'?'var(--t-green)':s?.direction==='SHORT'?'var(--t-red)':'var(--t-dim)',fontWeight:600}}>{s?.direction||'—'}</td>
     <td style={{...cell,textAlign:'right'}}>{row.spot?.toFixed(2)||'—'}</td>
     <td style={{...cell,color:t?.option_type==='CE'?'var(--t-green)':t?.option_type==='PE'?'var(--t-red)':'var(--t-dim)',fontWeight:600}}>{t?.contract?.symbol||'—'}</td>
     <td style={{...cell,textAlign:'right'}}>{t?.contract?.strike??'—'}</td>
     <td style={cell}>{t?.contract?.expiry||'—'}</td>
     <td style={{...cell,textAlign:'right'}}>{t?.entry_premium?.toFixed(2)||'—'}</td>
     <td style={{...cell,textAlign:'right'}}>{t?.stop_premium?.toFixed(2)||'—'}</td>
     <td style={{...cell,textAlign:'right'}}>{t?.target_premium?.toFixed(2)||'—'}</td>
     <td style={{...cell,textAlign:'right'}}>{t?.risk_inr?.toFixed(0)||'—'}</td>
    </tr>;
   })}</tbody>
  </table>
  {!rows.length&&<div style={{padding:16,color:'var(--t-dim)',fontSize:10}}>No configured underlyings are producing ORB signals.</div>}
 </div>;
}

export default NiftyOrbSignalsTable;
