import re

file_path = "/home/nageshmadaram/Sterling/backend/app/engines/scalping/price_action.py"
with open(file_path, "r") as f:
    content = f.read()

# Make sure we add cfg to all the detect functions
content = content.replace("lookback: int", "cfg: ScalpingConfig")
content = content.replace("def detect_ascending_triangle(\n    highs: NDArray, lows: NDArray, closes: NDArray, cfg: ScalpingConfig\n)", "def detect_ascending_triangle(highs: NDArray, lows: NDArray, closes: NDArray, cfg: ScalpingConfig)")
content = content.replace("def detect_double_bottom(\n    highs: NDArray, lows: NDArray, closes: NDArray, cfg: ScalpingConfig\n)", "def detect_double_bottom(highs: NDArray, lows: NDArray, closes: NDArray, cfg: ScalpingConfig)")

content = re.sub(r'detect_ascending_triangle\(h15, l15, c15, lookback\)', 'detect_ascending_triangle(h15, l15, c15, cfg)', content)
content = re.sub(r'detect_double_bottom\(h15, l15, c15, lookback\)', 'detect_double_bottom(h15, l15, c15, cfg)', content)
content = re.sub(r'detect_bullish_consolidation\(h15, l15, c15, lookback\)', 'detect_bullish_consolidation(h15, l15, c15, cfg)', content)

content = re.sub(r'detect_descending_triangle\(h15, l15, c15, lookback\)', 'detect_descending_triangle(h15, l15, c15, cfg)', content)
content = re.sub(r'detect_double_top\(h15, l15, c15, lookback\)', 'detect_double_top(h15, l15, c15, cfg)', content)
content = re.sub(r'detect_bearish_consolidation\(h15, l15, c15, lookback\)', 'detect_bearish_consolidation(h15, l15, c15, cfg)', content)

# update double bottom implementation
db_impl = """
    lookback = cfg.pa_lookback_bars
    # 1. Identify local pivot lows (a low lower than 2 bars left and right)
    pivot_low_indices = []
    for idx in range(len(lows) - lookback, len(lows) - 2):
        if lows[idx] < lows[idx-1] and lows[idx] < lows[idx-2] and \\
           lows[idx] < lows[idx+1] and lows[idx] < lows[idx+2]:
            pivot_low_indices.append(idx)
            
    if len(pivot_low_indices) < 2:
        return None
        
    # Get the two most recent distinct pivot lows
    b1_idx = pivot_low_indices[-2]
    b2_idx = pivot_low_indices[-1]
    
    # Ensure they have adequate structural breathing room
    if (b2_idx - b1_idx) < cfg.pa_min_pivot_distance:
        return None
        
    b1_val = float(lows[b1_idx])
    b2_val = float(lows[b2_idx])
    
    # Check if the two bottoms are within a strict variance of each other
    if abs(b1_val - b2_val) / max(b1_val, 1e-6) > cfg.pa_max_bottom_variance:
        return None
        
    # 2. Extract Neckline: Find the distinct structural peak between the two bottoms
    inter_highs = highs[b1_idx:b2_idx + 1]
    neckline = float(np.max(inter_highs))
    
    # Ensure the neckline is a real structural peak
    avg_bottom = (b1_val + b2_val) / 2
    if (neckline - avg_bottom) / avg_bottom < cfg.pa_min_neckline_height:
        return None
"""

content = re.sub(r'    # 1\. Identify local pivot lows.*?if \(neckline - avg_bottom\) / avg_bottom < 0\.01:\n        return None', db_impl.strip('\n'), content, flags=re.DOTALL)

# update double top implementation
dt_impl = """
    lookback = cfg.pa_lookback_bars
    # 1. Identify local pivot highs (a high higher than 2 bars left and right)
    pivot_high_indices = []
    for idx in range(len(highs) - lookback, len(highs) - 2):
        if highs[idx] > highs[idx-1] and highs[idx] > highs[idx-2] and \\
           highs[idx] > highs[idx+1] and highs[idx] > highs[idx+2]:
            pivot_high_indices.append(idx)
            
    if len(pivot_high_indices) < 2:
        return None
        
    # Get the two most recent distinct pivot highs
    t1_idx = pivot_high_indices[-2]
    t2_idx = pivot_high_indices[-1]
    
    # Ensure they have adequate structural breathing room
    if (t2_idx - t1_idx) < cfg.pa_min_pivot_distance:
        return None
        
    t1_val = float(highs[t1_idx])
    t2_val = float(highs[t2_idx])
    
    # Check if the two tops are within a strict variance of each other
    if abs(t1_val - t2_val) / max(t1_val, 1e-6) > cfg.pa_max_bottom_variance:
        return None
        
    # 2. Extract Neckline: Find the distinct structural valley between the two tops
    inter_lows = lows[t1_idx:t2_idx + 1]
    neckline = float(np.min(inter_lows))
    
    # Ensure the neckline is a real structural valley
    avg_top = (t1_val + t2_val) / 2
    if (avg_top - neckline) / neckline < cfg.pa_min_neckline_height:
        return None
"""
content = re.sub(r'    # 1\. Identify local pivot highs.*?if \(avg_top - neckline\) / neckline < 0\.01:\n        return None', dt_impl.strip('\n'), content, flags=re.DOTALL)

with open(file_path, "w") as f:
    f.write(content)
