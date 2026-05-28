import json
import websocket
import threading

class DeltaCandleStream:
    def __init__(self, symbol: str, on_candle_close_callback):
        self.symbol = symbol
        self.callback = on_candle_close_callback
        self.ws_url = "wss://api.india.delta.exchange/v2/websocket"
        
    def start(self):
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error
        )
        # Spin stream consumer off into a dedicated background execution thread
        threading.Thread(target=self.ws.run_forever, daemon=True).start()

    def _on_open(self, ws):
        print(f"🌐 WebSocket connection established. Subscribing to 1m updates for {self.symbol}...")
        payload = {
            "type": "subscribe",
            "channels": [
                {
                    "name": "candlestick_1m",
                    "symbols": [self.symbol]
                }
            ]
        }
        ws.send(json.dumps(payload))

    def _on_message(self, ws, message):
        msg_data = json.loads(message)
        
        # Intercept and map candle events
        if "channel" in msg_data and msg_data["channel"] == f"candlestick_1m":
            candle_payload = msg_data.get("data", {})
            
            # Check if this data block marks a true 1m structural bar confirmation close
            if candle_payload.get("is_closed", True): 
                normalized_bar = {
                    "timestamp": int(candle_payload["candle_start_time"]),
                    "open": float(candle_payload["open"]),
                    "high": float(candle_payload["high"]),
                    "low": float(candle_payload["low"]),
                    "close": float(candle_payload["close"]),
                    "volume": float(candle_payload["volume"])
                }
                # Dispatch candle straight to strategy pipeline execution loop
                self.callback(self.symbol, normalized_bar)

    def _on_error(self, ws, error):
        print(f"🛑 WebSocket Stream Exception: {str(error)}")
