import pytest
from fastapi.testclient import TestClient

from app.api import app, workflow
from app.orchestration.persistence import WorkflowStateStore


@pytest.fixture
def client(tmp_path):
    workflow.state_store = WorkflowStateStore(directory=str(tmp_path))
    return TestClient(app)


def test_api_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "mini-agentic-ai"


def test_api_create_incident_production_requires_approval(client, monkeypatch):
    """Production incidents require human approval and transition to WAITING_FOR_APPROVAL."""
    payload = {
        "incident_id": "API-PROD-001",
        "service": "payment-service",
        "environment": "production",
        "description": "Payment timeouts observed in production.",
        "severity": "high",
    }
    response = client.post("/incidents", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "WAITING_FOR_APPROVAL"
    assert data["approval"]["required"] is True
    assert data["approval"]["status"] == "PENDING"


def test_api_create_incident_staging_auto_completes(client, monkeypatch):
    """Staging incidents execute autonomously to COMPLETED when safety invariants pass."""
    payload = {
        "incident_id": "API-STAGING-001",
        "service": "payment-service",
        "environment": "staging",
        "description": "Payment timeouts observed in staging.",
    }
    response = client.post("/incidents", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["action_result"]["success"] is True


def test_api_create_incident_invalid_request(client):
    # Missing required field "service"
    payload = {
        "incident_id": "API-INV-001",
        "environment": "staging",
        "description": "Missing service field.",
    }
    response = client.post("/incidents", json=payload)
    assert response.status_code == 422


def test_api_get_incident_found_and_not_found(client):
    # Not found
    resp404 = client.get("/incidents/NONEXISTENT-001")
    assert resp404.status_code == 404

    # Found
    payload = {
        "incident_id": "API-GET-001",
        "service": "payment-service",
        "environment": "staging",
        "description": "Test get incident",
    }
    client.post("/incidents", json=payload)
    resp200 = client.get("/incidents/API-GET-001")
    assert resp200.status_code == 200
    assert resp200.json()["incident"]["incident_id"] == "API-GET-001"


def test_api_approve_incident(client):
    # Create production incident waiting for approval
    payload = {
        "incident_id": "API-APPROVE-001",
        "service": "payment-service",
        "environment": "production",
        "description": "Payment errors in prod.",
    }
    client.post("/incidents", json=payload)

    # Approve
    approve_resp = client.post("/incidents/API-APPROVE-001/approve")
    assert approve_resp.status_code == 200
    data = approve_resp.json()
    assert data["status"] == "COMPLETED"
    assert data["approval"]["status"] == "APPROVED"
    assert data["approval"]["approved_by"] == "human"


def test_api_reject_incident(client):
    payload = {
        "incident_id": "API-REJECT-001",
        "service": "payment-service",
        "environment": "production",
        "description": "Payment errors in prod.",
    }
    client.post("/incidents", json=payload)

    reject_resp = client.post(
        "/incidents/API-REJECT-001/reject",
        json={"reason": "Safety team rejected execution."},
    )
    assert reject_resp.status_code == 200
    data = reject_resp.json()
    assert data["status"] == "REJECTED"
    assert data["approval"]["status"] == "REJECTED"
    assert data["approval"]["rejection_reason"] == "Safety team rejected execution."


def test_api_stop_incident(client):
    payload = {
        "incident_id": "API-STOP-001",
        "service": "payment-service",
        "environment": "production",
        "description": "Payment errors in prod.",
    }
    client.post("/incidents", json=payload)

    stop_resp = client.post(
        "/incidents/API-STOP-001/stop",
        json={"reason": "Manual operator abort."},
    )
    assert stop_resp.status_code == 200
    data = stop_resp.json()
    assert data["status"] == "STOPPED"
    assert data["error"] == "Manual operator abort."


def test_api_approve_invalid_status_returns_400(client):
    # Incident that completed cannot be approved again
    payload = {
        "incident_id": "API-DOUBLE-001",
        "service": "payment-service",
        "environment": "staging",
        "description": "Staging auto completes.",
    }
    client.post("/incidents", json=payload)
    resp = client.post("/incidents/API-DOUBLE-001/approve")
    assert resp.status_code == 400
    assert "not waiting for approval" in resp.json()["detail"].lower()
