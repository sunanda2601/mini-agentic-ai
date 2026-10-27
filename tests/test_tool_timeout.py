import time

from app.orchestration.graph import IncidentWorkflow
from app.orchestration.persistence import WorkflowStateStore
from app.tools.schemas import SimulateScaleResponse


def test_slow_tool_does_not_complete_after_timeout(
    tmp_path,
    monkeypatch,
):
    """A tool exceeding its timeout must not complete the workflow."""
    monkeypatch.setattr(
        "app.orchestration.graph.PlannerAgent",
        lambda: None,
    )
    monkeypatch.setattr(
        "app.orchestration.graph.InvestigatorAgent",
        lambda: None,
    )
    monkeypatch.setattr(
        "app.orchestration.graph.OpsAgent",
        lambda: None,
    )
    monkeypatch.setattr(
        "app.orchestration.graph.VerifierAgent",
        lambda: None,
    )

    workflow = IncidentWorkflow()
    workflow.state_store = WorkflowStateStore(
        directory=str(tmp_path)
    )

    monkeypatch.setattr(
        "app.orchestration.graph.settings.tool_timeout_seconds",
        0.1,
    )
    monkeypatch.setattr(
        "app.orchestration.graph.settings.max_retries",
        0,
    )

    calls = {"scale": 0}

    def slow_scale(request):
        calls["scale"] += 1
        time.sleep(0.5)

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
        slow_scale,
    )

    state = {
        "incident": {
            "incident_id": "TIMEOUT-TEST-001",
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

    started = time.perf_counter()
    result = workflow._execute_approved_action(state)
    elapsed = time.perf_counter() - started

    assert result["status"] == "FAILED"
    error_message = result["error"].lower()
    assert (
        "timeout" in error_message
        or "timed out" in error_message
        or "exceeded" in error_message
    )
    assert elapsed < 0.4
    assert calls["scale"] == 1