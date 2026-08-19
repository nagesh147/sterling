import React from 'react';
import { NiftyOrbOptionsSettings } from '../NiftyOrbOptionsSettings';
import { NiftyOrbUniverseSettings } from '../NiftyOrbUniverseSettings';
import { NiftyOrbSignalsTable } from '../NiftyOrbSignalsTable';

export function OrbMomentumOptionsSettingsPanel(){
  return <>
    <NiftyOrbOptionsSettings />
    <div style={{marginTop:18,paddingTop:18,borderTop:'1px solid var(--t-border)'}}><NiftyOrbSignalsTable /></div>
  </>;
}
export { NiftyOrbUniverseSettings };
export default OrbMomentumOptionsSettingsPanel;
