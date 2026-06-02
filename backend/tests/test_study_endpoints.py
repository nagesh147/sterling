"""Tests for study API endpoints."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.api.v1.endpoints.derivatives import router
    api = FastAPI()
    api.include_router(router, prefix="/api/v1")
    return TestClient(api)


class TestStudyReportEndpoint:
    def test_returns_report_structure(self, client):
        resp = client.get("/api/v1/derivatives/study/report")
        assert resp.status_code == 200
        data = resp.json()
        assert "validation_method" in data
        assert "has_csv" in data


class TestStudyStatusEndpoint:
    def test_returns_404_for_unknown_run(self, client):
        resp = client.get("/api/v1/derivatives/study/status/nonexistent")
        assert resp.status_code == 404
