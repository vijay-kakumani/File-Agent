import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoints(client):
    # Test GET /health
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "agent_ready" in data
    assert data["agent_ready"] is True

    # Test GET /api/health
    resp2 = client.get("/api/health")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert "status" in data2


def test_query_endpoint_empty(client):
    resp = client.post("/query", json={"query": "   "})
    assert resp.status_code == 400


def test_query_endpoint_search_structure(client):
    resp = client.post("/query", json={"query": "find document"})
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data
    assert "intent" in data
    assert "message" in data
    assert "results" in data
    assert "action" in data
    assert isinstance(data["results"], list)
    assert data["action"] in ["search", "search_open", "unknown"]


def test_query_endpoint_open_intent_distinction(client):
    # Plain find should have action "search"
    resp = client.post("/query", json={"query": "find report"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "search"

    # Find and open should have action "search_open"
    resp2 = client.post("/query", json={"query": "find report and open it"})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["action"] == "search_open"
