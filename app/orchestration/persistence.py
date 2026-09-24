import json
from pathlib import Path
from typing import Any


class WorkflowStateStore:
    def __init__(self, directory: str = "traces"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, workflow_id: str, state: dict[str, Any]) -> None:
        path = self.directory / f"{workflow_id}.json"
        path.write_text(
            json.dumps(state, indent=2, default=str),
            encoding="utf-8",
        )

    def load(self, workflow_id: str) -> dict[str, Any]:
        path = self.directory / f"{workflow_id}.json"

        if not path.exists():
            raise FileNotFoundError(
                f"Workflow state '{workflow_id}' was not found."
            )

        return json.loads(
            path.read_text(encoding="utf-8")
        )
