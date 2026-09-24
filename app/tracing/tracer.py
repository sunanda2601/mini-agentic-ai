from datetime import datetime, timezone
from typing import Any
import time


class Tracer:
    SENSITIVE_KEYS = {
        "password",
        "token",
        "api_key",
        "authorization",
        "secret",
        "credential",
    }

    def __init__(self):
        self.events: list[dict[str, Any]] = []

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
            return [
                self._redact(item)
                for item in value
            ]

        return value

    def record(
        self,
        event_type: str,
        component: str,
        details: dict[str, Any] | None = None,
        latency_ms: float | None = None,
    ) -> None:
        safe_details = self._redact(
            details or {}
        )

        event = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "event_type": event_type,
            "component": component,
            "latency_ms": latency_ms,
            "details": safe_details,
        }

        self.events.append(event)

    def get_events(self) -> list[dict[str, Any]]:
        return self.events

    def clear(self) -> None:
        self.events.clear()

    def start_timer(self) -> float:
        return time.perf_counter()

    def elapsed_ms(
        self,
        start_time: float,
    ) -> float:
        return round(
            (time.perf_counter() - start_time) * 1000,
            2,
        )

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        input_cost_per_1k: float = 0.0,
        output_cost_per_1k: float = 0.0,
    ) -> float:
        input_cost = (
            input_tokens / 1000
        ) * input_cost_per_1k

        output_cost = (
            output_tokens / 1000
        ) * output_cost_per_1k

        return round(
            input_cost + output_cost,
            6,
        )

    def export_trace(
        self,
    ) -> list[dict[str, Any]]:
        return [
            event.copy()
            for event in self.events
        ]

    def replay(
        self,
    ) -> list[dict[str, Any]]:
        return [
            event.copy()
            for event in self.events
        ]