from app.services.providers.truedata.orb_realtime import TrueDataOrbRealtime

def test_completed_minute_bar_is_emitted_on_next_minute():
    agg=TrueDataOrbRealtime()
    assert agg.on_tick("NIFTY",{"timestamp":"2026-08-19 09:15:01","ltp":100,"volume":10}) is None
    assert agg.on_tick("NIFTY",{"timestamp":"2026-08-19 09:15:30","ltp":102,"volume":20}) is None
    bar=agg.on_tick("NIFTY",{"timestamp":"2026-08-19 09:16:00","ltp":101,"volume":5})
    assert bar is not None
    assert (bar.open,bar.high,bar.low,bar.close)==(100,102,100,20)

def test_latest_tick_is_available_for_quote_freshness():
    agg=TrueDataOrbRealtime();tick={"timestamp":"2026-08-19 09:15:01","ltp":100,"bid":99.9,"ask":100.1}
    agg.on_tick("NIFTY",tick)
    assert agg.latest_tick("NIFTY")["ask"]==100.1
