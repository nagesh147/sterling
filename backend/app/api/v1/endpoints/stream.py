from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from pydantic import BaseModel
from typing import Dict, List, Any
import json
import asyncio
import logging

log = logging.getLogger(__name__)

router = APIRouter()

class AnalyticsResponse(BaseModel):
    ofi: int
    unrealized_pnl: float
    drift_bps: float
    timestamp_ms: int


@router.get("/analytics/{symbol}", response_model=AnalyticsResponse)
async def get_analytics(symbol: str, request: Request):
    """REST endpoint for V4AnalyticsDashboard — returns current OFI, PnL, drift."""
    now_ms = int(__import__('time').time() * 1000)

    # OFI from l2_manager
    try:
        from app.services.delta_l2_socket import l2_manager
        ofi = l2_manager.get_ofi(symbol.upper()) or 0
    except Exception:
        ofi = 0

    # PnL from paper_store via _build_pnl_event logic
    unrealized_pnl = 0.0
    try:
        from app.api.v1.endpoints.directional import _paper_store, _stream_last_prices
        active = [p for p in _paper_store.list_positions()
                  if p.status.value in ("open", "partially_closed")]
        from app.api.v1.endpoints.positions import _estimate_pnl
        for pos in active:
            if pos.underlying != symbol.upper():
                continue
            spot = _stream_last_prices.get(pos.underlying)
            if spot is not None:
                spot_move = spot - pos.entry_spot_price
                direction_sign = 1 if pos.sized_trade.structure.direction.value == "long" else -1
                pnl = _estimate_pnl(pos.sized_trade, spot_move, direction_sign,
                                      pos.sized_trade.max_risk_usd, pos.sized_trade.structure.max_gain)
                unrealized_pnl += pnl or 0.0
    except Exception:
        pass

    # Drift: compare entry_spot vs current spot for active positions
    drift_bps = 0.0
    try:
        from app.api.v1.endpoints.directional import _paper_store, _stream_last_prices
        active = [p for p in _paper_store.list_positions()
                  if p.status.value in ("open", "partially_closed") and p.underlying == symbol.upper()]
        if active:
            total_drift = 0.0
            for pos in active:
                spot = _stream_last_prices.get(pos.underlying)
                if spot and pos.entry_spot_price:
                    drift_pct = ((spot - pos.entry_spot_price) / pos.entry_spot_price) * 10_000
                    total_drift += drift_pct
            drift_bps = round(total_drift / len(active), 2) if active else 0.0
    except Exception:
        pass

    return AnalyticsResponse(
        ofi=ofi,
        unrealized_pnl=round(unrealized_pnl, 2),
        drift_bps=drift_bps,
        timestamp_ms=now_ms,
    )

class StreamManager:
    def __init__(self):
        # Map channel names (e.g., symbols) to a list of active websocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Keep track of which connections are open to avoid exceptions on disconnected sockets
        self.all_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.all_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.all_connections:
            self.all_connections.remove(websocket)
        for channel in list(self.active_connections.keys()):
            if websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)
                if not self.active_connections[channel]:
                    del self.active_connections[channel]

    def subscribe(self, websocket: WebSocket, channel: str):
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        if websocket not in self.active_connections[channel]:
            self.active_connections[channel].append(websocket)

    async def broadcast_to_channel(self, channel: str, message: dict):
        if channel in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    log.warning(f"Failed to send to websocket, removing: {e}")
                    dead_connections.append(connection)
            
            for dead in dead_connections:
                self.disconnect(dead)

stream_manager = StreamManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await stream_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                action = payload.get("action")
                channel = payload.get("channel")
                
                if action == "subscribe" and channel:
                    stream_manager.subscribe(websocket, channel)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        stream_manager.disconnect(websocket)
