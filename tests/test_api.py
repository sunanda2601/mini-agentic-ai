import pytest
from fastapi.testclient import TestClient

from app.api import app, workflow
from app.orchestration.persistence import WorkflowStateStore

import hashlib
import json

from app.tracing.tracer import Tracer


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

def test_api_rejects_invalid_severity(client):
    payload = {
        "incident_id": "API-INVALID-SEVERITY",
        "service": "payment-service",
        "environment": "staging",
        "description": "Test invalid severity.",
        "severity": "urgent",
    }

    response = client.post("/incidents", json=payload)

    assert response.status_code == 422
    assert "severity" in response.text.lower()


def test_api_rejects_blank_service(client):
    payload = {
        "incident_id": "API-BLANK-SERVICE",
        "service": "   ",
        "environment": "staging",
        "description": "Test blank service.",
    }

    response = client.post("/incidents", json=payload)

    assert response.status_code == 422


def test_api_rejects_empty_description(client):
    payload = {
        "incident_id": "API-EMPTY-DESCRIPTION",
        "service": "payment-service",
        "environment": "staging",
        "description": "",
    }

    response = client.post("/incidents", json=payload)

    assert response.status_code == 422


def test_api_normalizes_uppercase_severity(client):
    payload = {
        "incident_id": "API-UPPERCASE-SEVERITY",
        "service": "payment-service",
        "environment": "production",
        "description": "Test uppercase severity.",
        "severity": "HIGH",
    }

    response = client.post("/incidents", json=payload)

    assert response.status_code == 201
    assert response.json()["incident"]["severity"] == "high"


def test_api_defaults_severity_to_medium(client):
    payload = {
        "incident_id": "API-DEFAULT-SEVERITY",
        "service": "payment-service",
        "environment": "production",
        "description": "Test default severity.",
    }

    response = client.post("/incidents", json=payload)

    assert response.status_code == 201
    assert response.json()["incident"]["severity"] == "medium"



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


def test_api_get_audit_trace(client):
    payload = {
        "incident_id": "API-AUDIT-001",
        "service": "payment-service",
        "environment": "staging",
        "description": "Test audit retrieval.",
    }

    create_response = client.post("/incidents", json=payload)
    assert create_response.status_code == 201

    response = client.get("/incidents/API-AUDIT-001/audit")

    assert response.status_code == 200
    data = response.json()

    assert data["workflow_id"] == "API-AUDIT-001"
    assert data["event_count"] > 0
    assert any(
        event["event_type"] == "workflow_started"
        for event in data["events"]
    )


def test_api_verify_audit_trace(client):
    payload = {
        "incident_id": "API-AUDIT-VERIFY-001",
        "service": "payment-service",
        "environment": "staging",
        "description": "Test audit verification.",
    }

    client.post("/incidents", json=payload)

    response = client.get(
        "/incidents/API-AUDIT-VERIFY-001/audit/verify"
    )

    assert response.status_code == 200
    data = response.json()

    assert data["valid"] is True
    assert data["event_count"] > 0


def test_api_replay_audit_does_not_reexecute_actions(
    client,
    monkeypatch,
):
    payload = {
        "incident_id": "API-AUDIT-REPLAY-001",
        "service": "payment-service",
        "environment": "staging",
        "description": "Test audit-only replay.",
    }

    client.post("/incidents", json=payload)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Workflow execution must not be repeated.")

    monkeypatch.setattr(workflow, "run", fail_if_called)

    response = client.get(
        "/incidents/API-AUDIT-REPLAY-001/audit/replay"
    )

    assert response.status_code == 200
    data = response.json()

    assert data["valid"] is True
    assert data["replay_mode"] == "audit_only"
    assert data["actions_reexecuted"] is False
    assert data["event_count"] > 0


def test_api_audit_unknown_workflow_returns_404(client):
    response = client.get(
        "/incidents/UNKNOWN-AUDIT-001/audit"
    )

    assert response.status_code == 404


def test_api_audit_missing_trace_returns_404(client):
    # Save a state without creating a corresponding audit trace.
    workflow.state_store.save(
        "API-AUDIT-NO-TRACE",
        {
            "incident": {"incident_id": "API-AUDIT-NO-TRACE"},
            "status": "COMPLETED",
        },
    )

    response = client.get(
        "/incidents/API-AUDIT-NO-TRACE/audit"
    )

    assert response.status_code == 404


def test_api_audit_corruption_returns_409(client):
    workflow_id = "API-AUDIT-CORRUPT-001"

    payload = {
        "incident_id": workflow_id,
        "service": "payment-service",
        "environment": "staging",
        "description": "Test corrupted audit detection.",
    }

    client.post("/incidents", json=payload)

    base_directory = (
        workflow.audit_directory
        if workflow.audit_directory is not None
        else workflow.state_store.directory / "audit"
    )

    safe_name = hashlib.sha256(
        workflow_id.encode("utf-8")
    ).hexdigest()

    audit_path = base_directory / f"{safe_name}.jsonl"

    # Tamper with a persisted event without recalculating its hash.
    events = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    events[0]["component"] = "tampered-component"

    audit_path.write_text(
        "".join(
            json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n"
            for event in events
        ),
        encoding="utf-8",
    )

    response = client.get(
        f"/incidents/{workflow_id}/audit/verify"
    )

    assert response.status_code == 409
    assert "integrity" in response.json()["detail"].lower()
