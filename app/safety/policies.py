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


ALLOWED_ENVIRONMENTS = {"staging", "production"}
ALLOWED_TOOLS = {
    "simulate_restart",
    "simulate_scale",
}
RESTRICTED_SERVICES = {
    "payment-db",
    "user-db",
}


def is_database_service(service: str | None) -> bool:
    if not service:
        return False
    srv = service.strip().lower()
    return (
        srv in RESTRICTED_SERVICES
        or srv.endswith("-db")
        or srv.endswith("-database")
    )


def check_action_policy(
    tool: str | None,
    service: str | None,
    environment: str | None,
    action_environment: str | None = None,
) -> PolicyResult:
    reasons: list[str] = []
    policy_ids: list[str] = []

    # 1. Fail closed for missing scope
    if not tool or not service or not environment:
        reasons.append("Missing required action scope (tool, service, environment).")
        policy_ids.append("SCOPE-001")
        return PolicyResult(
            decision=PolicyDecision.BLOCK,
            reasons=reasons,
            policy_ids=policy_ids,
        )

    # 2. Cross-environment boundary check
    if action_environment and action_environment != environment:
        reasons.append(
            f"Cross-environment action rejected: action environment '{action_environment}' "
            f"does not match incident environment '{environment}'."
        )
        policy_ids.append("ENV-CROSS")

    # 3. Environment allowlist check (fail closed for unknown/sandbox/dev envs)
    if environment not in ALLOWED_ENVIRONMENTS:
        reasons.append(f"Environment '{environment}' is not allowed or unknown.")
        policy_ids.append("ENV-001")

    # 4. Tool allowlist check
    if tool not in ALLOWED_TOOLS:
        reasons.append(f"Tool '{tool}' is not allowlisted.")
        policy_ids.append("TOOL-001")

    # If any hard policy violation, block execution immediately
    if reasons:
        return PolicyResult(
            decision=PolicyDecision.BLOCK,
            reasons=reasons,
            policy_ids=policy_ids,
        )

    # 5. Sensitive database restart requires manual approval in any environment
    if tool == "simulate_restart" and is_database_service(service):
        reasons.append(
            f"Restarting database service '{service}' requires manual approval."
        )
        policy_ids.append("APPROVAL-001")
        return PolicyResult(
            decision=PolicyDecision.REQUIRE_APPROVAL,
            reasons=reasons,
            policy_ids=policy_ids,
        )

    # 6. Every production mutation strictly requires explicit human approval
    if environment == "production":
        reasons.append(
            "All production remediation actions require explicit human approval."
        )
        policy_ids.append("APPROVAL-PROD")
        return PolicyResult(
            decision=PolicyDecision.REQUIRE_APPROVAL,
            reasons=reasons,
            policy_ids=policy_ids,
        )

    # 7. Staging remediation: autonomous execution allowed when all checks pass
    if environment == "staging":
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reasons=[],
            policy_ids=[],
        )

    # Fallback fail closed
    return PolicyResult(
        decision=PolicyDecision.BLOCK,
        reasons=["Action failed closed under safety policy."],
        policy_ids=["POLICY-UNKNOWN"],
    )