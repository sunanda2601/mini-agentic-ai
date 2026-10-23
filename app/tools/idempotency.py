import hashlib
import json
import threading
from pathlib import Path
from typing import Any


class IdempotencyConflictError(ValueError):
    """Raised when a key is reused for a different logical action."""


class IdempotencyStore:
    """Persist results for repeated simulated actions."""

    def __init__(self, path: str = "traces/idempotency.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @staticmethod
    def fingerprint(payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def execute_once(
        self,
        key: str,
        payload: dict[str, Any],
        operation,
    ) -> dict[str, Any]:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Idempotency key must be non-empty.")

        fingerprint = self.fingerprint(payload)

        with self._lock:
            records = self._read()

            if key in records:
                record = records[key]

                if record["fingerprint"] != fingerprint:
                    raise IdempotencyConflictError(
                        "Idempotency key was reused for a different action."
                    )

                return record["result"].copy()

            result = operation()

            if not isinstance(result, dict):
                raise TypeError("Idempotent operation must return a dictionary.")

            if result.get("success") is not True:
                return result.copy()

            records[key] = {
                "fingerprint": fingerprint,
                "result": result,
            }
            self._write(records)
            return result.copy()

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}

        data = json.loads(self.path.read_text(encoding="utf-8"))

        if not isinstance(data, dict):
            raise ValueError("Idempotency store must contain a JSON object.")

        return data

    def _write(self, records: dict[str, Any]) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(records, indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        temporary.replace(self.path)
