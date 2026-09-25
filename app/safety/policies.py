from dataclasses import dataclass
from enum import Enum


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    BLOCK = "BLOCK"


@dataclass
class PolicyResult:
    decision: PolicyDecision
    reasons: list[str]
    policy_ids: list[str]

    @property
    def allowed(self) -> bool:
        """Backward-compatible property for existing code."""
        return self.decision == PolicyDecision.ALLOW


ALLOWED_TOOLS = {
    "simulate_restart",
    "simulate_scale",
}


def check_action_policy(
    tool: str,
    service: str,
    environment: str,
) -> PolicyResult:

    reasons: list[str] = []
    policy_ids: list[str] = []

    # Policy 1: Only production actions are currently autonomous.
    if environment != "production":
        reasons.append(
            f"Environment '{environment}' is not allowed."
        )
        policy_ids.append("ENV-001")

    # Policy 2: Tool must be explicitly allowlisted.
    if tool not in ALLOWED_TOOLS:
        reasons.append(
            f"Tool '{tool}' is not allowed."
        )
        policy_ids.append("TOOL-001")

    # Policy 3: Sensitive database restart requires human approval.
    if (
        tool == "simulate_restart"
        and service == "payment-db"
    ):
        reasons.append(
            "Restarting payment-db requires manual approval."
        )
        policy_ids.append("APPROVAL-001")

        return PolicyResult(
            decision=PolicyDecision.REQUIRE_APPROVAL,
            reasons=reasons,
            policy_ids=policy_ids,
        )

    # Any policy violation other than approval requirement blocks action.
    if reasons:
        return PolicyResult(
            decision=PolicyDecision.BLOCK,
            reasons=reasons,
            policy_ids=policy_ids,
        )

    # No policy violations.
    return PolicyResult(
        decision=PolicyDecision.ALLOW,
        reasons=[],
        policy_ids=[],
    )