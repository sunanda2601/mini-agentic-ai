
from copy import deepcopy
from pathlib import Path

from app.orchestration.graph import IncidentWorkflow
from app.orchestration.state import State
from app.tracing.tracer import Tracer


class FakeStateStore:
    """Minimal state store for testing workflow audit persistence."""

    def __init__(self, directory: Path, state: dict):
        self.directory = str(directory)
        self.state = deepcopy(state)

    def load(self, workflow_id: str) -> dict:
        return deepcopy(self.state)

    def save(self, workflow_id: str, state: dict) -> None:
        self.state = deepcopy(state)


def make_workflow(state_store: FakeStateStore) -> IncidentWorkflow:
    """Create a workflow without initializing heavyweight AI agents."""
    workflow = IncidentWorkflow.__new__(IncidentWorkflow)
    workflow.state_store = state_store
    workflow.audit_directory = None
    workflow._workflow_tracers = {}
    workflow.tracer = Tracer()
    return workflow


def test_stopped_workflow_audit_persists_and_reloads(tmp_path):
    workflow_id = "audit-persistence-test"

    initial_state = {
        "incident": {"incident_id": workflow_id},
        "status": State.WAITING_FOR_APPROVAL.value,
        "approval": {
            "required": True,
            "status": "PENDING",
        },
        "error": None,
    }

    state_store = FakeStateStore(tmp_path / "state", initial_state)
    workflow = make_workflow(state_store)

    result = workflow.stop(
        workflow_id,
        reason="Integration test stop",
    )

    assert result["status"] == State.STOPPED.value
    assert result["approval"]["status"] == "STOPPED"

    events = workflow.tracer.get_events()

    assert len(events) == 1
    assert events[0]["event_type"] == "workflow_stopped"
    assert events[0]["component"] == "orchestrator"
    assert events[0]["details"]["incident_id"] == workflow_id
    assert events[0]["details"]["reason"] == "Integration test stop"
    assert (
        events[0]["details"]["previous_status"]
        == State.WAITING_FOR_APPROVAL.value
    )

    # Verify that a JSONL audit file was actually created.
    audit_directory = Path(state_store.directory) / "audit"
    audit_files = list(audit_directory.glob("*.jsonl"))

    assert len(audit_files) == 1
    assert audit_files[0].is_file()

    # Recreate the workflow to simulate loading the same workflow later.
    reloaded_workflow = make_workflow(state_store)
    reloaded_tracer = reloaded_workflow._get_tracer(workflow_id)

    reloaded_events = reloaded_tracer.get_events()

    assert reloaded_events == events
    assert Tracer.verify_trace(reloaded_events) is True
    assert reloaded_events[-1]["event_hash"] == events[-1]["event_hash"]
