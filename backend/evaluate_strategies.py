import sys
from collections import defaultdict
import numpy as np
from app.engines.sterling_engine.config import EngineConfig, ScalpingProfile
from app.engines.sterling_engine.optimizer import _pf_exp
from app.services.ohlcv_store import get_candles, get_status
from app.schemas.market import Candle

def load_candles():
    status = get_status()
    # Find a symbol with decent amount of 4h and 15m data
    sym = 'BTC-USD'
    syms_15m = [s['symbol'] for s in status if s['resolution'] == '15m']
    syms_4h = [s['symbol'] for s in status if s['resolution'] == '4h']
    valid = set(syms_15m) & set(syms_4h)
    
    if not valid:
        print("No data in OHLCV store.")
        return None, None, None
        
    for preferred in ["BTCUSD", "ETHUSD", "SOLUSD", list(valid)[0]]:
        if preferred in valid:
            sym = preferred
            break

    # Use dict to filter out any fields not in Candle
    cM_dicts = get_candles(sym, "4h", limit=1000)
    cE_dicts = get_candles(sym, "15m", limit=3000)
    
    # ensure timestamp_ms if 'time' is returned
    for c in cM_dicts:
        if 'timestamp_ms' not in c and 'time' in c:
            c['timestamp_ms'] = c['time']
    for c in cE_dicts:
        if 'timestamp_ms' not in c and 'time' in c:
            c['timestamp_ms'] = c['time']

    cM = [Candle(**c) for c in cM_dicts]
    cE = [Candle(**c) for c in cE_dicts]
    
    cM.reverse()
    cE.reverse()
    
    print(f"Loaded {len(cM)} 4h candles and {len(cE)} 15m candles for {sym}")
    return sym, cM, cE

def main():
    sym, cM, cE = load_candles()
    if not sym: return
    
    tsM = [c.timestamp_ms for c in cM]
    
    strategies = [
        ("price_action", "enable_price_action"),
        ("smc", "enable_smc"),
        ("ma_crossover", "enable_ma_crossover"),
        ("mean_reversion", "enable_mean_reversion"),
        ("breakout", "enable_breakout"),
    ]
    
    print(f"{'Strategy':<18} | {'Trades':<6} | {'PF':<6} | {'Win Rate':<8} | {'Exp':<8}")
    print("-" * 50)
    
    for name, flag in strategies:
        profile = ScalpingProfile()
        
        # Disable all
        for _, f in strategies:
            setattr(profile, f, False)
        # Enable just one
        setattr(profile, flag, True)
        
        # replay
        try:
            # Since _replay_symbol is hardcoded to evaluate_price_action, 
            # we need to override it locally to use scan_symbol
            def patched_replay_symbol(sym, cM, cE, cfg, tsM, step, maxh):
                import bisect
                from app.engines.sterling_engine.levels import detect_levels
                from app.engines.sterling_engine.optimizer import W_EXEC, W_MACRO, _exit_fixed
                from app.engines.sterling_engine.scanner import scan_symbol
                
                out = []
                cooldown, cj, levels = -1, -1, []
                n = len(cE)
                i = W_EXEC
                while i < n - 1:
                    if i <= cooldown:
                        i += step; continue
                    j = bisect.bisect_right(tsM, cE[i].timestamp_ms)
                    if j < W_MACRO:
                        i += step; continue
                    
                    signals = scan_symbol(sym, cM[j - W_MACRO:j], cE[i - W_EXEC:i + 1], cfg, 20, 20)
                    # Filter for only this strategy and valid entry signals
                    sig = None
                    for s in signals:
                        if s.strategy == name and s.entry_ok and s.direction in ("long", "short"):
                            sig = s
                            break
                            
                    if sig and sig.entry and sig.stop_loss and sig.take_profit:
                        is_long = sig.direction == "long"
                        ex, ck = _exit_fixed(cE, i, is_long, sig.entry, sig.stop_loss, sig.take_profit, maxh)
                        out.append((i, (1 if is_long else -1) * (ex - sig.entry) / abs(sig.entry - sig.stop_loss)))
                        cooldown = ck
                    i += step
                return out

            out = patched_replay_symbol(sym, cM, cE, profile, tsM, 2, 96)
            trades = [t[1] for t in out]
            pf, exp, n = _pf_exp(trades)
            wins = sum(1 for t in trades if t > 0)
            wr = wins / n if n > 0 else 0
            print(f"{name:<18} | {n:<6} | {pf:<6} | {wr*100:>5.1f}%   | {exp:<8.3f}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"{name:<18} | Error: {e}")

if __name__ == "__main__":
    main()
