from app.orchestration.persistence import WorkflowStateStore


def test_workflow_state_persistence(tmp_path):
    store = WorkflowStateStore(
        directory=str(tmp_path)
    )

    workflow_id = "TEST-001"

    state = {
        "incident": {
            "incident_id": workflow_id,
            "service": "payment-service",
        },
        "status": "COMPLETED",
        "error": None,
    }

    store.save(
        workflow_id,
        state,
    )

    loaded_state = store.load(
        workflow_id
    )

    assert loaded_state == state