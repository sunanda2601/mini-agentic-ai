
from datetime import datetime, timezone
from typing import Any
import copy
import hashlib
import json
import time
import uuid


class TraceIntegrityError(ValueError):
    """Raised when a trace is malformed or its integrity check fails."""


class Tracer:
    SENSITIVE_KEYS = {
        "password",
        "token",
        "api_key",
        "authorization",
        "secret",
        "credential",
    }

    GENESIS_HASH = "0" * 64

    def __init__(self):
        self.events: list[dict[str, Any]] = []
        self._last_hash = self.GENESIS_HASH

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            redacted = {}

            for key, item in value.items():
                if key.lower() in self.SENSITIVE_KEYS:
                    redacted[key] = "[REDACTED]"
                else:
                    redacted[key] = self._redact(item)

            return redacted

        if isinstance(value, list):
            return [self._redact(item) for item in value]

        if isinstance(value, tuple):
            return [self._redact(item) for item in value]

        return value

    @staticmethod
    def _canonical_json(event: dict[str, Any]) -> str:
        """Serialize an event deterministically for hashing."""
        try:
            return json.dumps(
                event,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise TraceIntegrityError(
                "Trace event contains non-JSON-compatible data."
            ) from exc

    @classmethod
    def _calculate_hash(cls, event: dict[str, Any]) -> str:
        """Hash an event, excluding its own hash field."""
        event_data = {
            key: value
            for key, value in event.items()
            if key != "event_hash"
        }

        serialized = cls._canonical_json(event_data)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def record(
        self,
        event_type: str,
        component: str,
        details: dict[str, Any] | None = None,
        latency_ms: float | None = None,
    ) -> None:
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be a non-empty string.")

        if not isinstance(component, str) or not component.strip():
            raise ValueError("component must be a non-empty string.")

        safe_details = self._redact(details or {})

        event = {
            "audit_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "component": component,
            "latency_ms": latency_ms,
            "details": safe_details,
            "previous_hash": self._last_hash,
        }

        event["event_hash"] = self._calculate_hash(event)

        self.events.append(event)
        self._last_hash = event["event_hash"]

    def get_events(self) -> list[dict[str, Any]]:
        """Return a defensive copy so callers cannot mutate internal events."""
        return copy.deepcopy(self.events)

    def clear(self) -> None:
        self.events.clear()
        self._last_hash = self.GENESIS_HASH

    def start_timer(self) -> float:
        return time.perf_counter()

    def elapsed_ms(self, start_time: float) -> float:
        return round((time.perf_counter() - start_time) * 1000, 2)

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        input_cost_per_1k: float = 0.0,
        output_cost_per_1k: float = 0.0,
    ) -> float:
        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k

        return round(input_cost + output_cost, 6)

    def export_trace(self) -> list[dict[str, Any]]:
        """Export a detached snapshot of the recorded trace."""
        return copy.deepcopy(self.events)

    @classmethod
    def verify_trace(
        cls,
        trace: list[dict[str, Any]],
    ) -> bool:
        """
        Verify event structure, hash values, and chain ordering.

        Returns True for a valid trace and raises TraceIntegrityError
        when the trace is malformed, altered, or reordered.
        """
        if not isinstance(trace, list):
            raise TraceIntegrityError("Trace must be a list.")

        previous_hash = cls.GENESIS_HASH
        seen_audit_ids = set()

        required_fields = {
            "audit_id",
            "timestamp",
            "event_type",
            "component",
            "latency_ms",
            "details",
            "previous_hash",
            "event_hash",
        }

        for index, event in enumerate(trace):
            if not isinstance(event, dict):
                raise TraceIntegrityError(
                    f"Event {index} must be a dictionary."
                )

            missing_fields = required_fields - event.keys()
            if missing_fields:
                raise TraceIntegrityError(
                    f"Event {index} is missing fields: "
                    f"{', '.join(sorted(missing_fields))}"
                )

            audit_id = event["audit_id"]
            if not isinstance(audit_id, str) or not audit_id:
                raise TraceIntegrityError(
                    f"Event {index} has an invalid audit_id."
                )

            if audit_id in seen_audit_ids:
                raise TraceIntegrityError(
                    f"Duplicate audit_id at event {index}."
                )
            seen_audit_ids.add(audit_id)

            if event["previous_hash"] != previous_hash:
                raise TraceIntegrityError(
                    f"Hash chain mismatch at event {index}."
                )

            expected_hash = cls._calculate_hash(event)
            if event["event_hash"] != expected_hash:
                raise TraceIntegrityError(
                    f"Event integrity check failed at event {index}."
                )

            previous_hash = event["event_hash"]

        return True

    def replay(
        self,
        trace: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return recorded events in order only after verifying their integrity.

        Replay does not execute workflow actions or repeat side effects.
        An optional exported trace can be verified independently.
        """
        candidate = (
            self.export_trace()
            if trace is None
            else copy.deepcopy(trace)
        )

        self.verify_trace(candidate)
        return candidate
