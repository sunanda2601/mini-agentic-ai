from app.models.messages import A2AMessage
from app.safety.blast_radius import BlastRadiusCalculator
from app.safety.policies import (
    PolicyDecision,
    check_action_policy,
)


class VerifierAgent:
    name = "verifier"

    def verify(self, proposal: A2AMessage) -> A2AMessage:
        payload = proposal.payload
        action = payload.get("proposed_action", {})

        reasons: list[str] = []
        policy_ids: list[str] = []

        incident_service = payload.get("service")
        incident_environment = payload.get("environment")

        action_tool = action.get("tool")
        action_service = action.get("service")
        action_environment = action.get("environment")

        # ---------------------------------------------------------
        # 1. Central policy evaluation
        # ---------------------------------------------------------
        policy_result = check_action_policy(
            tool=action_tool,
            service=action_service,
            environment=incident_environment,
            action_environment=action_environment,
        )

        policy_ids.extend(policy_result.policy_ids)
        reasons.extend(policy_result.reasons)

        # ---------------------------------------------------------
        # 2. Incident/service boundary validation
        # ---------------------------------------------------------
        if not action_service or action_service != incident_service:
            reasons.append(
                f"Action service '{action_service}' does not match incident service '{incident_service}'."
            )
            policy_ids.append("SERVICE-001")

        # ---------------------------------------------------------
        # 3. Blast-radius validation
        # ---------------------------------------------------------
        if action_service:
            blast_radius_result = BlastRadiusCalculator().calculate(action_service)
            if not blast_radius_result.get("within_limit", False):
                reasons.append(
                    f"Blast radius of {blast_radius_result['blast_radius']} "
                    f"exceeds the maximum allowed limit of {blast_radius_result['max_allowed_blast_radius']}."
                )
                policy_ids.append("BLAST-001")
        else:
            reasons.append("Missing action service for blast radius validation.")
            policy_ids.append("BLAST-002")

        # ---------------------------------------------------------
        # 4. Dependency health validation (e.g. payment-service restart)
        # ---------------------------------------------------------
        if action_service == "payment-service" and action_tool == "simulate_restart":
            dependency_metrics = payload.get("dependency_metrics", {})
            payment_db = dependency_metrics.get("payment-db")

            if not payment_db:
                reasons.append("Payment-db health information is missing.")
                policy_ids.append("DEPENDENCY-001")
            elif not payment_db.get("success"):
                reasons.append("Payment-db health check failed.")
                policy_ids.append("DEPENDENCY-002")
            elif not payment_db.get("metrics", {}).get("healthy", False):
                reasons.append("Payment-db is unhealthy. Restart cannot be approved.")
                policy_ids.append("DEPENDENCY-003")

        # ---------------------------------------------------------
        # 5. Determine final verification state
        # ---------------------------------------------------------
        # Hard policy blocks or safety invariant failures block execution.
        has_blocking_violations = (
            policy_result.decision == PolicyDecision.BLOCK
            or any(pid in {"SERVICE-001", "BLAST-001", "BLAST-002", "DEPENDENCY-001", "DEPENDENCY-002", "DEPENDENCY-003", "ENV-CROSS", "ENV-001", "TOOL-001", "SCOPE-001"} for pid in policy_ids)
        )

        if has_blocking_violations:
            final_decision = PolicyDecision.BLOCK
        elif policy_result.decision == PolicyDecision.REQUIRE_APPROVAL:
            final_decision = PolicyDecision.REQUIRE_APPROVAL
        else:
            final_decision = PolicyDecision.ALLOW

        approved = (final_decision == PolicyDecision.ALLOW)

        # ---------------------------------------------------------
        # 6. Return structured verification result
        # ---------------------------------------------------------
        return A2AMessage(
            message_id=f"{payload.get('incident_id', 'UNKNOWN')}-VERIFICATION",
            sender=self.name,
            receiver="orchestrator",
            message_type="verification_result",
            payload={
                "incident_id": payload.get("incident_id"),
                "service": incident_service,
                "approved": approved,
                "decision": final_decision.value,
                "policy_ids": list(dict.fromkeys(policy_ids)),
                "reasons": list(dict.fromkeys(reasons)),
                "proposed_action": action,
            },
        )