import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_evaluation_health_unauthorized():
    # Calling protected endpoint without token returns 401
    res = client.get("/api/v1/evaluation/health")
    assert res.status_code == 401


def test_evaluation_runs_unauthorized():
    res = client.get("/api/v1/evaluation/runs")
    assert res.status_code == 401
