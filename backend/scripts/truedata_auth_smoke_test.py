"""Real-authentication and read-only TrueData connectivity smoke test script.

Strict Requirements:
1. Retrieves active credential ONLY from `truedata_credentials` SQLite table.
2. Does NOT read `TRUEDATA_USERNAME` or `TRUEDATA_PASSWORD` from environment.
3. Does NOT create fake credentials or test accounts when no credential is configured.
4. If no active credential exists, fails cleanly with 'No active TrueData credential configured'.
5. Does NOT expose passwords, access tokens, or session tokens.
6. Does NOT unlock execution, alter ExecutionGate, or touch Kite.
"""
from __future__ import annotations

import sys
import asyncio
from datetime import datetime, timedelta, timezone

from app.services import db
from app.services.providers import truedata as truedata_service
from app.services.providers.truedata.adapter import TrueDataMarketDataAdapter


async def main() -> None:
    db.init()
    truedata_service.bootstrap()

    user_id = "default"
    # 1. Retrieve ONLY active credential from truedata_credentials DB
    acct = truedata_service.get_active(user_id)

    if not acct or acct.id == "TD-ENV":
        print("FAILURE: No active TrueData credential configured in database.")
        sys.exit(1)

    print("=== CREDENTIAL CONFIGURED ===")
    print(f"Account ID: {acct.id}")
    print(f"User ID: {acct.user_id}")
    print(f"Username Hint: {acct.username_hint()}")
    print(f"Is Active: {acct.is_active}")
    print(f"Has Encrypted Password: {bool(acct.password_enc)}")

    # Construct client using in-memory decrypted password (never env vars)
    client = truedata_service.build_client(acct)

    try:
        print("\n=== REAL AUTHENTICATION ===")
        print("Authenticating against https://auth.truedata.in/token...")
        token = await client.authenticate()

        if not token or not token.access_token:
            print("AUTHENTICATION FAILED: Provider did not return an access token.")
            sys.exit(1)

        print("AUTHENTICATION SUCCESS")

        # Perform one minimal read-only historical data request
        symbol = "NIFTY 50"
        print("\n=== READ-ONLY HISTORICAL DATA ===")
        print(f"Requesting last 10 1-minute bars for symbol: {symbol}...")
        
        try:
            bars = await client.get_last_bars(symbol, n=10, interval="1min")
        except Exception:
            # Fallback to date range query
            today = datetime.now(timezone.utc)
            start_str = (today - timedelta(days=5)).strftime("%y%m%dT09:15:00")
            end_str = (today - timedelta(days=5)).strftime("%y%m%dT15:30:00")
            bars = await client.get_bars(symbol, start_str, end_str, interval="1min")

        if not bars:
            print("READ-ONLY HISTORICAL DATA: FAILED (No bar records returned)")
            sys.exit(1)

        print(f"READ-ONLY HISTORICAL DATA: SUCCESS ({len(bars)} bars received)")

        # Map to CanonicalMarketEvent and verify fields
        raw_bar = bars[0]
        receipt_iso = datetime.now(timezone.utc).isoformat()
        canonical_event = TrueDataMarketDataAdapter.create_bar_event(
            symbol,
            raw_bar,
            receipt_time_iso=receipt_iso,
        )

        print("\n=== CANONICAL MARKET EVENT ===")
        print("CANONICAL EVENT CREATED")
        print(f"  record_id:      {canonical_event.record_id}")
        print(f"  event_type:     {canonical_event.event_type}")
        print(f"  instrument_id:  {canonical_event.instrument_id}")
        print(f"  event_time:     {canonical_event.event_time}")
        print(f"  available_at:   {canonical_event.available_at}")
        print(f"  source:         {canonical_event.source}")
        print(f"  source_version: {canonical_event.source_version}")
        print(f"  provenance:     {dict(canonical_event.provenance)}")
        print(f"  payload keys:   {list(canonical_event.payload.keys())}")
        assert canonical_event.available_at >= canonical_event.event_time, "Causal invariant violation: available_at < event_time"
        print("  invariant:      available_at >= event_time [VERIFIED]")

    except truedata_service.TrueDataAuthError as auth_err:
        print("\nAUTHENTICATION FAILED")
        print(f"Provider Error: {auth_err}")
    except truedata_service.TrueDataError as td_err:
        print("\nREAD-ONLY HISTORICAL DATA: FAILED")
        print(f"Provider Error: {td_err}")
    except Exception as exc:
        print(f"\nUNEXPECTED FAILURE: {exc}")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
