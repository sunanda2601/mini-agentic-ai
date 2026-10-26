from app.orchestration.persistence import WorkflowStateStore


def test_workflow_state_persistence(tmp_path):
    store = WorkflowStateStore(directory=str(tmp_path))

    workflow_id = "TEST-001"

    state = {
        "incident": {
            "incident_id": workflow_id,
            "service": "payment-service",
        },
        "status": "COMPLETED",
        "error": None,
    }

    store.save(workflow_id, state)
    loaded_state = store.load(workflow_id)

    assert loaded_state == state


def test_pending_approval_survives_workflow_restart(tmp_path):
    from app.orchestration.graph import IncidentWorkflow

    workflow_id = "restart-recovery-test"

    pending_state = {
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
                    "environment": "production",
                }
            }
        },
        "approval": {
            "required": True,
            "status": "PENDING",
            "reasons": ["Manual approval required."],
            "policy_ids": ["APPROVAL-001"],
        },
        "status": "WAITING_FOR_APPROVAL",
        "error": None,
    }

    # Simulate the first application instance saving pending state.
    first_workflow = IncidentWorkflow()
    first_workflow.state_store = WorkflowStateStore(
        directory=str(tmp_path)
    )
    first_workflow.state_store.save(workflow_id, pending_state)

    # Simulate an application restart with a new workflow instance.
    restarted_workflow = IncidentWorkflow()
    restarted_workflow.state_store = WorkflowStateStore(
        directory=str(tmp_path)
    )

    recovered_state = restarted_workflow.state_store.load(workflow_id)

    assert recovered_state["status"] == "WAITING_FOR_APPROVAL"
    assert recovered_state["approval"]["status"] == "PENDING"
    assert recovered_state["approval"]["required"] is True
    assert (
        recovered_state["verification"]["payload"]["proposed_action"]["tool"]
        == "simulate_restart"
    )