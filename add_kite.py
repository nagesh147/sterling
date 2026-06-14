import requests

try:
    response = requests.post(
        "http://127.0.0.1:8000/api/v1/exchanges",
        json={
            "name": "zerodha",
            "display_name": "Zerodha Kite",
            "api_key": "dummy_key",
            "api_secret": "dummy_secret",
            "is_paper": True
        }
    )
    print(response.status_code, response.text)
except Exception as e:
    print(e)
