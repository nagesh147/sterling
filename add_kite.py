"""Dev helper: register a Zerodha Kite exchange account via the local API.

Credentials must come from the environment — never hardcode secrets.
  KITE_API_KEY / KITE_API_SECRET  (preferred)
  or ZERODHA_API_KEY / ZERODHA_API_SECRET
"""
import os
import sys

import requests

api_key = os.environ.get("KITE_API_KEY") or os.environ.get("ZERODHA_API_KEY")
api_secret = os.environ.get("KITE_API_SECRET") or os.environ.get("ZERODHA_API_SECRET")
if not api_key or not api_secret:
    print(
        "Set KITE_API_KEY and KITE_API_SECRET (or ZERODHA_API_KEY / ZERODHA_API_SECRET) "
        "in the environment before running this script.",
        file=sys.stderr,
    )
    sys.exit(1)

base_url = os.environ.get("STERLING_API_URL", "http://127.0.0.1:8000").rstrip("/")

try:
    response = requests.post(
        f"{base_url}/api/v1/exchanges",
        json={
            "name": "zerodha",
            "display_name": "Zerodha Kite",
            "api_key": api_key,
            "api_secret": api_secret,
            "is_paper": True,
        },
        timeout=30,
    )
    print(response.status_code, response.text)
except Exception as e:
    print(e)
