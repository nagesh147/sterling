/**
 * useKiteLiveTicks — module-level singleton consuming the Kite tick WebSocket.
 *
 * The backend already runs one KiteTicker per user and fans decoded ticks out to
 * the `kite_ticks:{userId}` channel over the shared `/api/v1/stream/ws` socket
 * (see services/exchanges/kite/ticker_manager.py). This module:
 *
 *   1. Opens ONE WebSocket and subscribes that channel.
 *   2. Keeps a `token → tick` map, notifying React subscribers on each UI batch.
 *   3. Reconciles a ref-counted union of "tokens someone wants" against the
 *      server-side subscription via POST /ticker/{subscribe,unsubscribe}.
 *
 * Price hooks (use