

import pytest

from app.tracing.tracer import Tracer, TraceIntegrityError


def test_audit_events_persist_across_tracer_instances(tmp_path):
    audit_file = tmp_path / "audit.jsonl"

    first = Tracer(audit_path=str(audit_file))
    first.record("workflow_started", "graph", {"workflow_id": "W-001"})
    first.record("approval_requested", "graph", {"status": "PENDING"})

    second = Tracer(audit_path=str(audit_file))

    assert len(second.get_events()) == 2
    assert Tracer.verify_trace(second.export_trace()) is True


def test_new_events_continue_existing_hash_chain(tmp_path):
    audit_file = tmp_path / "audit.jsonl"

    first = Tracer(audit_path=str(audit_file))
    first.record("started", "graph", {})

    second = Tracer(audit_path=str(audit_file))
    second.record("completed", "graph", {})

    trace = second.export_trace()

    assert len(trace) == 2
    assert trace[1]["previous_hash"] == trace[0]["event_hash"]
    assert Tracer.verify_trace(trace) is True


def test_persisted_tampering_is_detected(tmp_path):
    audit_file = tmp_path / "audit.jsonl"

    tracer = Tracer(audit_path=str(audit_file))
    tracer.record("started", "graph", {"workflow_id": "W-001"})

    text = audit_file.read_text(encoding="utf-8")
    audit_file.write_text(
        text.replace("W-001", "W-999"),
        encoding="utf-8",
    )

    with pytest.raises(TraceIntegrityError):
        Tracer(audit_path=str(audit_file))


def test_malformed_jsonl_is_rejected(tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    audit_file.write_text("{invalid json}\n", encoding="utf-8")

    with pytest.raises(TraceIntegrityError):
        Tracer(audit_path=str(audit_file))


def test_sensitive_values_are_not_written_to_disk(tmp_path):
    audit_file = tmp_path / "audit.jsonl"

    tracer = Tracer(audit_path=str(audit_file))
    tracer.record(
        "credential_check",
        "test",
        {"api_key": "top-secret"},
    )

    persisted = audit_file.read_text(encoding="utf-8")

    assert "top-secret" not in persisted
    assert "[REDACTED]" in persisted


def test_clear_resets_persistent_trace(tmp_path):
    audit_file = tmp_path / "audit.jsonl"

    tracer = Tracer(audit_path=str(audit_file))
    tracer.record("started", "graph", {})
    tracer.clear()
    tracer.record("restarted", "graph", {})

    trace = tracer.export_trace()

    assert len(trace) == 1
    assert trace[0]["previous_hash"] == Tracer.GENESIS_HASH
    assert Tracer.verify_trace(trace) is True


def test_stale_tracer_does_not_break_existing_hash_chain(tmp_path):
    audit_file = tmp_path / "shared-audit.jsonl"

    first = Tracer(audit_path=str(audit_file))
    first.record("started", "graph", {})

    second = Tracer(audit_path=str(audit_file))

    first.record("first_update", "graph", {})
    second.record("second_update", "graph", {})

    # Every event should link to the event immediately before it.
    trace = Tracer(audit_path=str(audit_file)).export_trace()

    assert Tracer.verify_trace(trace) is True
