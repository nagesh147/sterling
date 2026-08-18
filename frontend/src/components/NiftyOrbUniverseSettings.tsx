import React from 'react';
import { InstrumentsGroup } from './kite/config/ScanSettings';

export function NiftyOrbUniverseSettings({ cfg, onChange }: { cfg: any; onChange: (next: Record<string, unknown>) => void }) {
  return <InstrumentsGroup
    idPrefix="NIFTY ORB"
    indices={cfg.scan_indices || ['NIFTY']}
    stocks={cfg.scan_stocks || []}
    allStocks={cfg.scan_all_stocks ?? false}
    stockContracts={cfg.scan_stock_contracts ?? true}
    onChange={onChange}
    allowEmptyIndices={false}
  />;
}

export default NiftyOrbUniverseSettings;
