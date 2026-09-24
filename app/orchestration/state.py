from typing import Any, TypedDict


class WorkflowState(TypedDict, total=False):
    incident: dict[str, Any]

    plan: dict[str, Any]

    investigation: dict[str, Any]

    action_proposal: dict[str, Any]

    verification: dict[str, Any]

    action_result: dict[str, Any]

    status: str

    error: str | None