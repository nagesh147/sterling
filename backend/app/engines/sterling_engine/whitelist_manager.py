import json
import os
import time

WHITELIST_PATH = os.path.join(os.path.dirname(__file__), "whitelist.json")

_cache = {}
_last_mtime = 0

def get_whitelist():
    global _cache, _last_mtime
    if not os.path.exists(WHITELIST_PATH):
        return {}
        
    mtime = os.path.getmtime(WHITELIST_PATH)
    if mtime > _last_mtime:
        try:
            with open(WHITELIST_PATH, "r") as f:
                _cache = json.load(f)
            _last_mtime = mtime
        except Exception:
            pass
    return _cache

def is_whitelisted(strategy: str, symbol: str, timeframe: str) -> bool:
    """
    Returns True if the strategy is allowed to run on this symbol/timeframe.
    Defaults to True if no rule exists (fail-open for safety/testing).
    """
    wl = get_whitelist()
    if strategy in wl:
        strat_wl = wl[strategy]
        if symbol in strat_wl:
            sym_wl = strat_wl[symbol]
            if timeframe in sym_wl:
                return sym_wl[timeframe]
    return True
