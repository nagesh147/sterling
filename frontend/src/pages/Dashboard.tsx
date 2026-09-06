import { SimpleTerminal } from './SimpleTerminal';
import { Terminal } from './Terminal';
import { useAppMode } from '../store/useStore';

/**
 * Sterling is an Indian-markets application. The basic workspace hosts the
 * Zerodha/Kite terminal; the pro workspace is the future advanced Indian
 * markets terminal.
 */
export function Dashboard() {
  const appMode = useAppMode();
  return appMode === 'pro' ? <Terminal /> : <SimpleTerminal />;
}
