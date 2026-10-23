
import pytest

from app.orchestration.graph import IncidentWorkflow
from app.orchestration.persistence import WorkflowStateStore
from app.orchestration.state import (
    State,
    TRANSITIONS,
    can_transition,
    validate_transition,
    IllegalStateTransitionError,
)


def test_state_enum_members():
    assert State.PLANNING.value == "PLANNING"
    assert State.INVESTIGATING.value == "INVESTIGATING"
    assert State.ACTION_PROPOSED.value == "ACTION_PROPOSED"
    assert State.VERIFYING.value == "VERIFYING"
    assert State.WAITING_FOR_APPROVAL.value == "WAITING_FOR_APPROVAL"
    assert State.APPROVED.value == "APPROVED"
    assert State.COMPLETED.value == "COMPLETED"
    assert State.FAILED.value == "FAILED"
    assert State.STOPPED.value == "STOPPED"
    assert State.REJECTED.value == "REJECTED"


def test_valid_sequential_transitions():
    assert can_transition(None, State.PLANNING)[0] is True
    assert can_transition(State.PLANNING, State.INVESTIGATING)[0] is True
    assert can_transition(State.INVESTIGATING, State.ACTION_PROPOSED)[0] is True
    assert can_transition(State.ACTION_PROPOSED, State.VERIFYING)[0] is True
    assert can_transition(State.VERIFYING, State.WAITING_FOR_APPROVAL)[0] is True
    assert can_transition(State.WAITING_FOR_APPROVAL, State.APPROVED)[0] is True
    assert can_transition(State.APPROVED, State.COMPLETED)[0] is True


def test_autonomous_staging_transition():
    # In staging, verifier can allow autonomous execution: VERIFYING -> APPROVED
    assert can_transition(State.VERIFYING, State.APPROVED)[0] is True
    assert can_transition(State.APPROVED, State.COMPLETED)[0] is True


def test_approval_rejection_transition():
    assert can_transition(State.WAITING_FOR_APPROVAL, State.REJECTED)[0] is True


def test_invalid_transition_raises_error():
    # Cannot jump from PLANNING directly to APPROVED
    with pytest.raises(IllegalStateTransitionError) as exc_info:
        validate_transition(State.PLANNING, State.APPROVED)

    assert "Illegal transition from 'PLANNING' to 'APPROVED'" in str(
        exc_info.value
    )


def test_cannot_bypass_approval_state():
    # Attempting to jump from WAITING_FOR_APPROVAL to COMPLETED is blocked
    with pytest.raises(IllegalStateTransitionError) as exc_info:
        validate_transition(State.WAITING_FOR_APPROVAL, State.COMPLETED)

    assert "Illegal transition from 'WAITING_FOR_APPROVAL' to 'COMPLETED'" in str(
        exc_info.value
    )


def test_terminal_states_have_no_transitions():
    for terminal in (
        State.COMPLETED,
        State.FAILED,
        State.STOPPED,
        State.REJECTED,
    ):
        assert len(TRANSITIONS[terminal]) == 0

        with pytest.raises(IllegalStateTransitionError):
            validate_transition(terminal, State.PLANNING)

        with pytest.raises(IllegalStateTransitionError):
            validate_transition(terminal, State.APPROVED)


def test_stoppable_states():
    stoppable = [
        State.PLANNING,
        State.INVESTIGATING,
        State.ACTION_PROPOSED,
        State.VERIFYING,
        State.WAITING_FOR_APPROVAL,
        State.APPROVED,
    ]

    for state in stoppable:
        assert can_transition(state, State.STOPPED)[0] is True


def test_execution_boundary_blocks_unapproved_execution(tmp_path, monkeypatch):
    """Execution layer blocks actions when workflow status is not APPROVED."""
    workflow = IncidentWorkflow()
    workflow.state_store = WorkflowStateStore(directory=str(tmp_path))

    def fail_if_called(_request):
        raise AssertionError(
            "simulate_restart must not be called when status is unapproved."
        )

    monkeypatch.setattr(
        "app.orchestration.graph.simulate_restart",
        fail_if_called,
    )

    unapproved_state = {
        "incident": {
            "incident_id": "BYPASS-001",
            "service": "payment-service",
            "environment": "production",
        },
        "verification": {
            "payload": {
                "proposed_action": {
                    "tool": "simulate_restart",
                    "service": "payment-service",
                }
            }
        },
        "approval": {
            "required": True,
            "status": "PENDING",
        },
        "status": "WAITING_FOR_APPROVAL",
    }

    with pytest.raises(IllegalStateTransitionError) as exc_info:
        workflow._execute_approved_action(unapproved_state)

    assert "Workflow must be in 'APPROVED' state" in str(exc_info.value)


def test_execution_boundary_blocks_approved_status_without_human_approval(
    tmp_path, monkeypatch
):
    """A forced APPROVED status cannot bypass required human approval."""
    workflow = IncidentWorkflow()
    workflow.state_store = WorkflowStateStore(directory=str(tmp_path))

    def fail_if_called(_request):
        raise AssertionError(
            "simulate_restart must not be called without verified human approval."
        )

    monkeypatch.setattr(
        "app.orchestration.graph.simulate_restart",
        fail_if_called,
    )

    tampered_state = {
        "incident": {
            "incident_id": "TAMPER-001",
            "service": "payment-service",
            "environment": "production",
        },
        "verification": {
            "payload": {
                "proposed_action": {
                    "tool": "simulate_restart",
                    "service": "payment-service",
                }
            }
        },
        "approval": {
            "required": True,
            "status": "PENDING",
        },
        "status": "APPROVED",
    }

    result = workflow._execute_approved_action(tampered_state)

    assert result["status"] == "FAILED"
    assert (
        "Execution boundary rejected: Production action lacks required human approval"
        in result["error"]
    )


def test_approved_scale_action_calls_scale_tool(tmp_path, monkeypatch):
    """An approved scale action calls simulate_scale, never simulate_restart."""
    workflow = IncidentWorkflow()
    workflow.state_store = WorkflowStateStore(directory=str(tmp_path))

    calls = {"scale": [], "restart": []}

    class FakeScaleResult:
        success = True
        message = "Scale simulated"
        simulated = True

        def model_dump(self):
            return {
                "success": True,
                "tenant_id": "demo-tenant",
                "service": "payment-service",
                "environment": "staging",
                "requested_replicas": 3,
                "action": "scale",
                "simulated": True,
                "message": "Scale simulated",
                "version": "1.0.0",
                "error": None,
            }

    def fake_scale(request):
        calls["scale"].append(request)
        return FakeScaleResult()

    def fake_restart(request):
        calls["restart"].append(request)
        raise AssertionError(
            "simulate_restart must not be called for a simulate_scale action."
        )

    monkeypatch.setattr("app.orchestration.graph.simulate_scale", fake_scale)
    monkeypatch.setattr("app.orchestration.graph.simulate_restart", fake_restart)

    approved_state = {
        "incident": {
            "incident_id": "SCALE-TEST-001",
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
    }

    result = workflow._execute_approved_action(approved_state)

    assert len(calls["scale"]) == 1
    assert calls["restart"] == []
    assert result["status"] == "COMPLETED"
    assert result["action_result"]["success"] is True
    assert result["action_result"]["simulated"] is True


def test_execution_boundary_blocks_stopped_workflow(
    tmp_path, monkeypatch
):
    """A stopped workflow must never execute its proposed action."""
    workflow = IncidentWorkflow()
    workflow.state_store = WorkflowStateStore(directory=str(tmp_path))

    def fail_if_called(_request):
        raise AssertionError(
            "simulate_restart must not execute for a stopped workflow."
        )

    monkeypatch.setattr(
        "app.orchestration.graph.simulate_restart",
        fail_if_called,
    )

    stopped_state = {
        "incident": {
            "incident_id": "STOPPED-EXEC-001",
            "service": "payment-service",
            "environment": "production",
        },
        "verification": {
            "payload": {
                "proposed_action": {
                    "tool": "simulate_restart",
                    "service": "payment-service",
                }
            }
        },
        "approval": {
            "required": True,
            "status": "STOPPED",
        },
        "status": "STOPPED",
        "error": "Operator stopped the workflow.",
    }

    result = workflow._execute_approved_action(stopped_state)

    assert result["status"] == "STOPPED"
    assert result["error"] == "Operator stopped the workflow."
