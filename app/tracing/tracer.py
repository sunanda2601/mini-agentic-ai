
from datetime import datetime, timezone
from pathlib import Path
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

    def __init__(self, audit_path: str | None = None):
        self.events: list[dict[str, Any]] = []
        self._last_hash = self.GENESIS_HASH
        self.audit_path = Path(audit_path) if audit_path else None

        if self.audit_path is not None:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)

            if self.audit_path.exists():
                self.events = self._read_persisted_trace()
                self.verify_trace(self.events)

                if self.events:
                    self._last_hash = self.events[-1]["event_hash"]

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            redacted = {}
            for key, item in value.items():
                if key.lower() in self.SENSITIVE_KEYS:
                    redacted[key] = "[REDACTED]"
                else:
                    redacted[key] = self._redact(item)
            return redacted

        if isinstance(value, (list, tuple)):
            return [self._redact(item) for item in value]

        return value

    @staticmethod
    def _canonical_json(event: dict[str, Any]) -> str:
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
        event_data = {
            key: value
            for key, value in event.items()
            if key != "event_hash"
        }
        serialized = cls._canonical_json(event_data)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _read_persisted_trace(self) -> list[dict[str, Any]]:
        """Load JSONL events, rejecting malformed records."""
        events = []

        try:
            with self.audit_path.open("r", encoding="utf-8") as file:
                for line_number, line in enumerate(file, start=1):
                    if not line.strip():
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise TraceIntegrityError(
                            f"Invalid JSON in audit log at line {line_number}."
                        ) from exc

                    if not isinstance(event, dict):
                        raise TraceIntegrityError(
                            f"Audit log line {line_number} is not an event object."
                        )

                    events.append(event)

        except OSError as exc:
            raise TraceIntegrityError(
                f"Could not read audit log: {exc}"
            ) from exc

        return events

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

        event = {
            "audit_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "component": component,
            "latency_ms": latency_ms,
            "details": self._redact(details or {}),
            "previous_hash": self._last_hash,
        }
        event["event_hash"] = self._calculate_hash(event)

        # Persist before updating memory, so a failed write is reported.
        if self.audit_path is not None:
            try:
                with self.audit_path.open("a", encoding="utf-8") as file:
                    file.write(
                        json.dumps(
                            event,
                            sort_keys=True,
                            ensure_ascii=False,
                            allow_nan=False,
                        )
                        + "\n"
                    )
                    file.flush()
            except (OSError, TypeError, ValueError) as exc:
                raise TraceIntegrityError(
                    f"Could not persist audit event: {exc}"
                ) from exc

        self.events.append(event)
        self._last_hash = event["event_hash"]

    def get_events(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.events)

    def clear(self) -> None:
        if self.audit_path is not None:
            try:
                with self.audit_path.open("w", encoding="utf-8"):
                    pass
            except OSError as exc:
                raise TraceIntegrityError(
                    f"Could not clear audit log: {exc}"
                ) from exc

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
        return copy.deepcopy(self.events)

    @classmethod
    def verify_trace(cls, trace: list[dict[str, Any]]) -> bool:
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
        candidate = (
            self.export_trace()
            if trace is None
            else copy.deepcopy(trace)
        )
        self.verify_trace(candidate)
        return candidate
