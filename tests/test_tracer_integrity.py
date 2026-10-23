
import copy

import pytest

from app.tracing.tracer import Tracer, TraceIntegrityError


def make_trace():
    tracer = Tracer()
    tracer.record("workflow_started", "graph", {"workflow_id": "W-001"})
    tracer.record("approval_requested", "graph", {"status": "PENDING"})
    tracer.record("workflow_stopped", "graph", {"reason": "operator"})
    return tracer


def test_valid_trace_passes_verification():
    tracer = make_trace()

    assert Tracer.verify_trace(tracer.export_trace()) is True


def test_replay_returns_verified_events_in_order():
    tracer = make_trace()

    replayed = tracer.replay()

    assert [event["event_type"] for event in replayed] == [
        "workflow_started",
        "approval_requested",
        "workflow_stopped",
    ]


def test_modified_event_is_detected():
    tracer = make_trace()
    trace = tracer.export_trace()
    trace[0]["details"]["workflow_id"] = "TAMPERED"

    with pytest.raises(TraceIntegrityError):
        tracer.replay(trace)


def test_reordered_events_are_detected():
    tracer = make_trace()
    trace = tracer.export_trace()
    trace[0], trace[1] = trace[1], trace[0]

    with pytest.raises(TraceIntegrityError):
        Tracer.verify_trace(trace)


def test_removed_event_is_detected():
    tracer = make_trace()
    trace = tracer.export_trace()
    del trace[1]

    with pytest.raises(TraceIntegrityError):
        Tracer.verify_trace(trace)


def test_exported_trace_cannot_mutate_internal_events():
    tracer = make_trace()
    exported = tracer.export_trace()
    exported[0]["details"]["workflow_id"] = "TAMPERED"

    assert tracer.replay()[0]["details"]["workflow_id"] == "W-001"


def test_sensitive_values_are_redacted_before_hashing():
    tracer = Tracer()
    tracer.record(
        "credential_check",
        "test",
        {
            "api_key": "do-not-store",
            "nested": {"password": "also-secret"},
        },
    )

    event = tracer.replay()[0]

    assert event["details"]["api_key"] == "[REDACTED]"
    assert event["details"]["nested"]["password"] == "[REDACTED]"
    assert Tracer.verify_trace([event]) is True


def test_clear_resets_trace_chain():
    tracer = make_trace()
    tracer.clear()
    tracer.record("new_workflow", "graph", {})

    trace = tracer.export_trace()

    assert len(trace) == 1
    assert trace[0]["previous_hash"] == Tracer.GENESIS_HASH
    assert Tracer.verify_trace(trace) is True


def test_empty_trace_is_valid():
    assert Tracer.verify_trace([]) is True
    assert Tracer().replay() == []
