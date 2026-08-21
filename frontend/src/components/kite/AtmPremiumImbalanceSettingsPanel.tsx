import React from 'react';
import { AtmPremiumImbalanceSettings } from '../AtmPremiumImbalanceSettings';

/**
 * Settings page for the ATM Premium Imbalance strategy.
 *
 * A thin wrapper, matching OrbMomentumOptionsSettingsPanel, so the settings hub
 * imports one component per section and the panel itself stays testable on its
 * own.
 */
export function AtmPremiumImbalanceSettingsPanel() {
  return <AtmPremiumImbalanceSettings />;
}

export default AtmPremiumImbalanceSettingsPanel;
