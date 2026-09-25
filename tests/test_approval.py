from types import SimpleNamespace

import pytest

from app.orchestration.graph import IncidentWorkflow
from app.orchestration.persistence import WorkflowStateStore


def create_waiting_state(workflow_id: str) -> dict:
    return {
        "incident": {
            "incident_id": workflow_id,
            "service": "payment-db",
            "environment": "production",
        },
        "verification": {
            "payload": {
                "proposed_action": {
                    "tool": "simulate_restart",
                    "service": "payment-db",
                }
            }
        },
        "approval": {
            "required": True,
            "status": "PENDING",
            "reasons": [
                "Restarting payment-db requires manual approval."
            ],
            "policy_ids": ["APPROVAL-001"],
        },
        "status": "WAITING_FOR_APPROVAL",
        "error": None,
    }


def fake_restart(_request):
    return SimpleNamespace(
        success=True,
        simulated=True,
        error=None,
        model_dump=lambda: {
            "success": True,
            "simulated": True,
            "error": None,
        },
    )


def test_human_approval_executes_verified_action(
    tmp_path,
    monkeypatch,
):
    workflow = IncidentWorkflow()
    workflow.state_store = WorkflowStateStore(
        directory=str(tmp_path)
    )

    workflow_id = "approval-test-001"

    workflow.state_store.save(
        workflow_id,
        create_waiting_state(workflow_id),
    )

    monkeypatch.setattr(
        "app.orchestration.graph.simulate_restart",
        fake_restart,
    )

    result = workflow.approve(workflow_id)

    assert result["approval"]["status"] == "APPROVED"
    assert result["approval"]["approved_by"] == "human"
    assert result["status"] == "COMPLETED"
    assert result["action_result"]["success"] is True


def test_human_rejection_does_not_execute_action(
    tmp_path,
    monkeypatch,
):
    workflow = IncidentWorkflow()
    workflow.state_store = WorkflowStateStore(
        directory=str(tmp_path)
    )

    workflow_id = "approval-test-002"

    workflow.state_store.save(
        workflow_id,
        create_waiting_state(workflow_id),
    )

    def fail_if_called(_request):
        raise AssertionError(
            "simulate_restart must not execute after rejection."
        )

    monkeypatch.setattr(
        "app.orchestration.graph.simulate_restart",
        fail_if_called,
    )

    result = workflow.reject(
        workflow_id,
        reason="Human reviewer rejected the action.",
    )

    assert result["approval"]["status"] == "REJECTED"
    assert result["approval"]["rejected_by"] == "human"
    assert (
        result["approval"]["rejection_reason"]
        == "Human reviewer rejected the action."
    )
    assert result["status"] == "REJECTED"
    assert result["error"] == (
        "Human reviewer rejected the action."
    )
    assert "action_result" not in result


def test_approval_requires_pending_workflow(
    tmp_path,
):
    workflow = IncidentWorkflow()
    workflow.state_store = WorkflowStateStore(
        directory=str(tmp_path)
    )

    workflow_id = "approval-test-003"

    workflow.state_store.save(
        workflow_id,
        {
            "status": "COMPLETED",
            "approval": {
                "required": False,
                "status": "NOT_REQUIRED",
            },
        },
    )

    with pytest.raises(ValueError):
        workflow.approve(workflow_id)


def test_human_can_stop_waiting_workflow(
    tmp_path,
):
    workflow = IncidentWorkflow()
    workflow.state_store = WorkflowStateStore(
        directory=str(tmp_path)
    )

    workflow_id = "stop-test-001"

    workflow.state_store.save(
        workflow_id,
        create_waiting_state(workflow_id),
    )

    result = workflow.stop(
        workflow_id,
        reason="Operator stopped the workflow.",
    )

    assert result["status"] == "STOPPED"
    assert result["error"] == (
        "Operator stopped the workflow."
    )

    assert result["approval"]["status"] == "STOPPED"
    assert result["approval"]["stopped_by"] == "operator"
    assert (
        result["approval"]["stop_reason"]
        == "Operator stopped the workflow."
    )

    events = workflow.tracer.get_events()

    stopped_events = [
        event
        for event in events
        if event["event_type"] == "workflow_stopped"
    ]

    assert len(stopped_events) == 1
    assert (
        stopped_events[0]["details"]["previous_status"]
        == "WAITING_FOR_APPROVAL"
    )


def test_stopped_workflow_is_persisted(
    tmp_path,
):
    workflow = IncidentWorkflow()
    workflow.state_store = WorkflowStateStore(
        directory=str(tmp_path)
    )

    workflow_id = "stop-test-002"

    workflow.state_store.save(
        workflow_id,
        create_waiting_state(workflow_id),
    )

    workflow.stop(workflow_id)

    saved_state = workflow.state_store.load(
        workflow_id
    )

    assert saved_state["status"] == "STOPPED"
    assert saved_state["error"] == (
        "Workflow stopped by operator."
    )
    assert saved_state["approval"]["status"] == "STOPPED"


def test_completed_workflow_cannot_be_stopped(
    tmp_path,
):
    workflow = IncidentWorkflow()
    workflow.state_store = WorkflowStateStore(
        directory=str(tmp_path)
    )

    workflow_id = "stop-test-003"

    workflow.state_store.save(
        workflow_id,
        {
            "status": "COMPLETED",
            "approval": {
                "required": False,
                "status": "NOT_REQUIRED",
            },
        },
    )

    with pytest.raises(ValueError):
        workflow.stop(workflow_id)