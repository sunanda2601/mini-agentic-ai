from dataclasses import dataclass


@dataclass
class PolicyResult:
    allowed: bool
    reasons: list[str]


ALLOWED_TOOLS = {
    "simulate_restart",
    "simulate_scale",
}


def check_action_policy(
    tool: str,
    service: str,
    environment: str,
) -> PolicyResult:

    reasons = []

    if environment != "production":
        reasons.append(
            f"Environment '{environment}' is not allowed."
        )

    if tool not in ALLOWED_TOOLS:
        reasons.append(
            f"Tool '{tool}' is not allowed."
        )

    if (
        tool == "simulate_restart"
        and service == "payment-db"
    ):
        reasons.append(
            "Restarting payment-db requires manual approval."
        )

    return PolicyResult(
        allowed=len(reasons) == 0,
        reasons=reasons,
    )