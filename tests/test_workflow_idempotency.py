
from app.orchestration.graph import IncidentWorkflow
from app.orchestration.persistence import WorkflowStateStore
from app.tools.schemas import SimulateScaleResponse


def create_approved_state(workflow_id: str) -> dict:
    """Create a fresh approved state for the same logical action."""
    return {
        "incident": {
            "incident_id": workflow_id,
            "tenant_id": "demo-tenant",
            "service": "payment-service",
            "environment": "staging",
        },
        "verification": {
            "payload": {
                "proposed_action": {
                    "tool": "simulate_scale",
                    "service": "payment-service",
                    "environment": "staging",
                    "replicas": 3,
                }
            }
        },
        "approval": {
            "required": False,
            "status": "NOT_REQUIRED",
        },
        "status": "APPROVED",
        "error": None,
    }


def test_duplicate_workflow_action_executes_tool_only_once(
    tmp_path,
    monkeypatch,
):
    workflow = IncidentWorkflow()
    workflow.state_store = WorkflowStateStore(
        directory=str(tmp_path)
    )

    workflow_id = "workflow-idempotency-test-001"
    calls = {"scale": 0}

    def fake_scale(request):
        calls["scale"] += 1

        return SimulateScaleResponse(
            success=True,
            tenant_id=request.tenant_id,
            service=request.service,
            environment=request.environment,
            requested_replicas=request.replicas,
            action="scale",
            simulated=True,
            message="Scale simulated",
            version="1.0.0",
            error=None,
        )

    monkeypatch.setattr(
        "app.orchestration.graph.simulate_scale",
        fake_scale,
    )

    # First execution: the underlying tool should run.
    first_result = workflow._execute_approved_action(
        create_approved_state(workflow_id)
    )

    assert first_result["status"] == "COMPLETED"
    assert first_result["action_result"]["success"] is True
    assert calls["scale"] == 1

    # Second execution: same workflow ID and identical action.
    # The persisted idempotency record should supply the result.
    second_result = workflow._execute_approved_action(
        create_approved_state(workflow_id)
    )

    assert second_result["status"] == "COMPLETED"
    assert second_result["action_result"]["success"] is True

    # The tool must not execute a second time.
    assert calls["scale"] == 1

    # Both executions should produce the same action result.
    assert (
        second_result["action_result"]
        == first_result["action_result"]
    )
