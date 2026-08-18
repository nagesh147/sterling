import React from 'react';
import { NiftyOrbOptionsSettings } from '../NiftyOrbOptionsSettings';

/**
 * Signal-engine settings adapter.
 *
 * The canonical NIFTY ORB configuration surface lives in the shared component
 * so it can also be embedded by other terminal surfaces without duplicating
 * field semantics or API wiring.
 */
export function OrbMomentumOptionsSettingsPanel() {
  return <NiftyOrbOptionsSettings />;
}

export default OrbMomentumOptionsSettingsPanel;
