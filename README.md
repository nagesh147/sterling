# Sterling

Sterling is an Indian-market trading and research platform for NSE/BSE cash and derivatives. It combines a FastAPI backend with React and React Native clients, using Zerodha Kite and TrueData market data.

## Applications

- Web terminal: Kite dashboard, orders, holdings, positions, alerts, strategy engines, replay, and backtesting.
- Mobile terminal: Kite watchlist, orders, holdings, and positions.
- Backend: Indian-market data ingestion, scanners, strategy execution, safety controls, and audit persistence.

## Local development

    make setup
    make backend
    make frontend

Backend: `http://localhost:8000`  
Frontend: `http://localhost:5173`

## Primary API surfaces

- `/api/v1/kite`
- `/api/v1/kite-engine`
- `/api/v1/navigator`
- `/api/v1/adaptive-edge`
- `/api/v1/opening-volume-leaders`
- `/api/v1/pcr`
- `/api/v1/backtest`
- `/health`

All live orders must pass the shared kill-switch, idempotency, broker-session, and INR risk controls.
