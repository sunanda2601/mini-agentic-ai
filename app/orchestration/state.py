from enum import Enum
from typing import Any, TypedDict


class State(str, Enum):
    PLANNING = "PLANNING"
    INVESTIGATING = "INVESTIGATING"
    ACTION_PROPOSED = "ACTION_PROPOSED"
    VERIFYING = "VERIFYING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"
    REJECTED = "REJECTED"


WorkflowStateStatus = State


class IllegalStateTransitionError(ValueError):
    """Raised when an invalid or disallowed state machine transition is attempted."""
    pass


TRANSITIONS: dict[State, set[State]] = {
    State.PLANNING: {
        State.INVESTIGATING,
        State.FAILED,
        State.STOPPED,
    },
    State.INVESTIGATING: {
        State.ACTION_PROPOSED,
        State.FAILED,
        State.STOPPED,
    },
    State.ACTION_PROPOSED: {
        State.VERIFYING,
        State.FAILED,
        State.STOPPED,
    },
    State.VERIFYING: {
        State.WAITING_FOR_APPROVAL,
        State.APPROVED,
        State.FAILED,
        State.STOPPED,
    },
    State.WAITING_FOR_APPROVAL: {
        State.APPROVED,
        State.REJECTED,
        State.STOPPED,
    },
    State.APPROVED: {
        State.COMPLETED,
        State.FAILED,
        State.STOPPED,
    },
    State.COMPLETED: set(),
    State.FAILED: set(),
    State.STOPPED: set(),
    State.REJECTED: set(),
}


def can_transition(
    current: str | State | None,
    target: str | State,
) -> tuple[bool, str]:
    """Check if a transition from current state to target state is legally allowed."""
    try:
        target_state = State(target)
    except ValueError:
        return False, f"Unknown target state: '{target}'."

    if current is None:
        if target_state == State.PLANNING:
            return True, ""
        return False, f"Initial state can only transition to '{State.PLANNING.value}'."

    try:
        curr_state = State(current)
    except ValueError:
        return False, f"Unknown current state: '{current}'."

    allowed_targets = TRANSITIONS.get(curr_state, set())
    if target_state in allowed_targets:
        return True, ""

    allowed_names = sorted(s.value for s in allowed_targets)
    return (
        False,
        f"Illegal transition from '{curr_state.value}' to '{target_state.value}'. "
        f"Allowed transitions from '{curr_state.value}': {allowed_names}.",
    )


def validate_transition(
    current: str | State | None,
    target: str | State,
) -> State:
    """Validate a transition, returning target State or raising IllegalStateTransitionError."""
    allowed, message = can_transition(current, target)
    if not allowed:
        raise IllegalStateTransitionError(message)
    return State(target)


class WorkflowState(TypedDict, total=False):
    incident: dict[str, Any]
    plan: dict[str, Any]
    investigation: dict[str, Any]
    action_proposal: dict[str, Any]
    verification: dict[str, Any]
    approval: dict[str, Any]
    action_result: dict[str, Any]
    status: str
    error: str | None