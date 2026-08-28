import React from 'react';
import { OiWallFlowSettings } from '../OiWallFlowSettings';

/**
 * Settings page for the OI Wall Flow strategy.
 *
 * A thin wrapper, matching GammaMoveSettingsPanel, so the settings hub
 * imports one component per section and the panel stays testable on its own.
 */
export function OiWallFlowSettingsPanel() {
  return <OiWallFlowSettings />;
}

export default OiWallFlowSettingsPanel;
