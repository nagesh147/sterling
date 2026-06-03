from fastapi.testclient import TestClient
from main import create_app


def test_v2_health_and_config():
    client = TestClient(create_app())
    r = client.get("/api/v1/sterling-v2/health")
    assert r.status_code == 200
    assert r.json()["engine"] == "sterling_v2"
    c = client.get("/api/v1/sterling-v2/config")
    assert c.status_code == 200
    assert c.json()["enabled"] is False
    assert c.json()["auto_execute"] is False
