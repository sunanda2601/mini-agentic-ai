
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import copy
import hashlib
import json
import math
import threading
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

    # Shared locks coordinate tracer instances within this Python process.
    _file_locks_guard = threading.Lock()
    _file_locks: dict[str, threading.RLock] = {}

    def __init__(self, audit_path: str | None = None):
        self.events: list[dict[str, Any]] = []
        self._last_hash = self.GENESIS_HASH
        self.audit_path = Path(audit_path) if audit_path else None

        if self.audit_path is not None:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)

            with self._get_file_lock(self.audit_path):
                if self.audit_path.exists():
                    self.events = self._read_persisted_trace()
                    self.verify_trace(self.events)

                    if self.events:
                        self._last_hash = self.events[-1]["event_hash"]

    @classmethod
    def _get_file_lock(cls, audit_path: Path) -> threading.RLock:
        """Return a shared in-process lock for the given audit file."""
        key = str(audit_path.resolve())

        with cls._file_locks_guard:
            if key not in cls._file_locks:
                cls._file_locks[key] = threading.RLock()

            return cls._file_locks[key]

    def _redact(self, value: Any) -> Any:
        """Recursively redact sensitive dictionary values."""
        if isinstance(value, dict):
            redacted = {}

            for key, item in value.items():
                if isinstance(key, str) and key.lower() in self.SENSITIVE_KEYS:
                    redacted[key] = "[REDACTED]"
                else:
                    redacted[key] = self._redact(item)

            return redacted

        if isinstance(value, (list, tuple)):
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
        """Calculate the event hash, excluding its own event_hash field."""
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

        if self.audit_path is None:
            return events

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
                            f"Audit log line {line_number} "
                            "is not an event object."
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
        """Record an event using the latest persisted hash-chain head."""
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be a non-empty string.")

        if not isinstance(component, str) or not component.strip():
            raise ValueError("component must be a non-empty string.")

        if details is not None and not isinstance(details, dict):
            raise ValueError("details must be a dictionary or None.")

        if latency_ms is not None:
            if (
                isinstance(latency_ms, bool)
                or not isinstance(latency_ms, (int, float))
                or not math.isfinite(latency_ms)
                or latency_ms < 0
            ):
                raise ValueError(
                    "latency_ms must be a finite, non-negative number or None."
                )

        lock = (
            self._get_file_lock(self.audit_path)
            if self.audit_path is not None
            else threading.RLock()
        )

        with lock:
            if self.audit_path is not None:
                if self.audit_path.exists():
                    persisted_events = self._read_persisted_trace()
                    self.verify_trace(persisted_events)
                else:
                    persisted_events = []

                # Refresh in-memory state to avoid using a stale hash.
                self.events = persisted_events
                self._last_hash = (
                    persisted_events[-1]["event_hash"]
                    if persisted_events
                    else self.GENESIS_HASH
                )

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

            # Persist before updating in-memory state.
            if self.audit_path is not None:
                try:
                    with self.audit_path.open(
                        "a",
                        encoding="utf-8",
                        newline="\n",
                    ) as file:
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
        """Return a deep copy of in-memory events."""
        return copy.deepcopy(self.events)

    def clear(self) -> None:
        """Clear the trace and reset its hash chain."""
        lock = (
            self._get_file_lock(self.audit_path)
            if self.audit_path is not None
            else threading.RLock()
        )

        with lock:
            if self.audit_path is not None:
                try:
                    with self.audit_path.open(
                        "w",
                        encoding="utf-8",
                        newline="\n",
                    ):
                        pass
                except OSError as exc:
                    raise TraceIntegrityError(
                        f"Could not clear audit log: {exc}"
                    ) from exc

            self.events.clear()
            self._last_hash = self.GENESIS_HASH

    @classmethod
    def verify_trace(cls, trace: list[dict[str, Any]]) -> bool:
        """Verify event structure, uniqueness, hashes, and chain continuity."""
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
                    f"Event hash mismatch at event {index}."
                )

            previous_hash = event["event_hash"]

        return True

    def replay(
        self,
        trace: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Validate a trace and return a copy for inspection."""
        candidate = self.get_events() if trace is None else copy.deepcopy(trace)
        self.verify_trace(candidate)
        return candidate

    def export_trace(self) -> list[dict[str, Any]]:
        """Return a copy of the current in-memory trace."""
        return self.get_events()

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        input_cost_per_1k: float,
        output_cost_per_1k: float,
    ) -> float:
        """Estimate inference cost from token counts and per-1K-token rates."""
        values = (
            input_cost_per_1k,
            output_cost_per_1k,
        )

        if (
            isinstance(input_tokens, bool)
            or not isinstance(input_tokens, int)
            or input_tokens < 0
        ):
            raise ValueError("input_tokens must be a non-negative integer.")

        if (
            isinstance(output_tokens, bool)
            or not isinstance(output_tokens, int)
            or output_tokens < 0
        ):
            raise ValueError("output_tokens must be a non-negative integer.")

        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
            for value in values
        ):
            raise ValueError(
                "Token costs must be finite, non-negative numbers."
            )

        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k

        return round(input_cost + output_cost, 8)

    def start_timer(self) -> float:
        """Start a high-resolution timer."""
        return time.perf_counter()

    def elapsed_ms(self, start_time: float) -> float:
        """Return elapsed time in milliseconds, rounded to two decimals."""
        return round((time.perf_counter() - start_time) * 1000, 2)
