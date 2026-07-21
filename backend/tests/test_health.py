"""P0 test — health endpoint returns {status: ok}."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_content_type():
    response = client.get("/health")
    assert "application/json" in response.headers["content-type"]
