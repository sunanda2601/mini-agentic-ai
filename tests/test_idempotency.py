import pytest

from app.tools.idempotency import (
    IdempotencyConflictError,
    IdempotencyStore,
)


def test_repeated_key_executes_operation_once(tmp_path):
    store = IdempotencyStore(str(tmp_path / "idempotency.json"))
    calls = {"count": 0}

    def operation():
        calls["count"] += 1
        return {"success": True, "message": "simulated"}

    payload = {"service": "payment-service", "environment": "staging"}

    first = store.execute_once("incident-1:action-1", payload, operation)
    second = store.execute_once("incident-1:action-1", payload, operation)

    assert first == second
    assert calls["count"] == 1


def test_result_survives_new_store_instance(tmp_path):
    path = str(tmp_path / "idempotency.json")
    first_store = IdempotencyStore(path)

    first = first_store.execute_once(
        "incident-1:action-1",
        {"service": "payment-service"},
        lambda: {"success": True, "result": "completed"},
    )

    second_store = IdempotencyStore(path)

    def should_not_run():
        raise AssertionError("A persisted result should be reused.")

    second = second_store.execute_once(
        "incident-1:action-1",
        {"service": "payment-service"},
        should_not_run,
    )

    assert second == first


def test_same_key_with_different_payload_is_rejected(tmp_path):
    store = IdempotencyStore(str(tmp_path / "idempotency.json"))

    store.execute_once(
        "incident-1:action-1",
        {"service": "payment-service"},
        lambda: {"success": True},
    )

    with pytest.raises(IdempotencyConflictError):
        store.execute_once(
            "incident-1:action-1",
            {"service": "checkout-service"},
            lambda: {"success": True},
        )


def test_failed_result_is_not_cached(tmp_path):
    store = IdempotencyStore(str(tmp_path / "idempotency.json"))
    calls = {"count": 0}

    def operation():
        calls["count"] += 1
        return {"success": calls["count"] > 1}

    assert store.execute_once("retry-1", {"service": "payments"}, operation) == {
        "success": False
    }
    assert store.execute_once("retry-1", {"service": "payments"}, operation) == {
        "success": True
    }
    assert calls["count"] == 2


def test_empty_key_is_rejected(tmp_path):
    store = IdempotencyStore(str(tmp_path / "idempotency.json"))

    with pytest.raises(ValueError):
        store.execute_once("", {"service": "payments"}, lambda: {"success": True})
