import React from 'react';
import { GammaMoveSettings } from '../GammaMoveSettings';

/**
 * Settings page for the Gamma Move strategy.
 *
 * A thin wrapper, matching AtmPremiumImbalanceSettingsPanel, so the settings hub
 * imports one component per section and the panel stays testable on its own.
 */
export function GammaMoveSettingsPanel() {
  return <GammaMoveSettings />;
}

export default GammaMoveSettingsPanel;
