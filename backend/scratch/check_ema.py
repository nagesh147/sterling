import numpy as np
from tests.conftest import make_bearish_candles
from app.engines.indicators.ema import ema_dual

candles = make_bearish_candles(100, base=50000.0)
closes = np.array([c.close for c in candles], dtype=np.float64)
ema21, ema55 = ema_dual(closes, 21, 55)

print("Starting close:", closes[0])
print("Ending close:", closes[-1])
print("EMA21 ending:", ema21[-1])
print("EMA55 ending:", ema55[-1])
print("Close series:", closes)
