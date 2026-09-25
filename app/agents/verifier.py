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
        action = payload["proposed_action"]

        reasons: list[str] = []
        policy_ids: list[str] = []

        # ---------------------------------------------------------
        # 1. Central policy evaluation
        # ---------------------------------------------------------
        policy_result = check_action_policy(
            tool=action["tool"],
            service=action["service"],
            environment=payload["environment"],
        )

        policy_ids.extend(policy_result.policy_ids)

        if policy_result.decision == PolicyDecision.BLOCK:
            reasons.extend(policy_result.reasons)

        elif policy_result.decision == PolicyDecision.REQUIRE_APPROVAL:
            reasons.extend(policy_result.reasons)

        # ---------------------------------------------------------
        # 2. Blast-radius validation
        # ---------------------------------------------------------
        blast_radius_result = BlastRadiusCalculator().calculate(
            action["service"]
        )

        if not blast_radius_result["within_limit"]:
            reasons.append(
                f"Blast radius of "
                f"{blast_radius_result['blast_radius']} "
                f"exceeds the maximum allowed limit of "
                f"{blast_radius_result['max_allowed_blast_radius']}."
            )
            policy_ids.append("BLAST-001")

        # ---------------------------------------------------------
        # 3. Incident/service boundary validation
        # ---------------------------------------------------------
        if action["service"] != payload["service"]:
            reasons.append(
                "Action service does not match incident service."
            )
            policy_ids.append("SERVICE-001")

        # ---------------------------------------------------------
        # 4. Payment database dependency validation
        # ---------------------------------------------------------
        if (
            action["service"] == "payment-service"
            and action["tool"] == "simulate_restart"
        ):
            dependency_metrics = payload.get(
                "dependency_metrics",
                {},
            )

            payment_db = dependency_metrics.get("payment-db")

            if not payment_db:
                reasons.append(
                    "Payment-db health information is missing."
                )
                policy_ids.append("DEPENDENCY-001")

            elif not payment_db.get("success"):
                reasons.append(
                    "Payment-db health check failed."
                )
                policy_ids.append("DEPENDENCY-002")

            elif not payment_db.get("metrics", {}).get(
                "healthy",
                False,
            ):
                reasons.append(
                    "Payment-db is unhealthy. "
                    "Restart cannot be approved."
                )
                policy_ids.append("DEPENDENCY-003")

        # ---------------------------------------------------------
        # 5. Determine final verification state
        # ---------------------------------------------------------

        # Hard policy violations or safety failures block execution.
        if reasons and policy_result.decision == PolicyDecision.BLOCK:
            final_decision = PolicyDecision.BLOCK

        # Any additional safety failure is also a block.
        elif len(reasons) > (
            len(policy_result.reasons)
            if policy_result.decision
            == PolicyDecision.REQUIRE_APPROVAL
            else 0
        ):
            final_decision = PolicyDecision.BLOCK

        # Policy explicitly requires human approval.
        elif (
            policy_result.decision
            == PolicyDecision.REQUIRE_APPROVAL
        ):
            final_decision = PolicyDecision.REQUIRE_APPROVAL

        else:
            final_decision = PolicyDecision.ALLOW

        approved = final_decision == PolicyDecision.ALLOW

        # ---------------------------------------------------------
        # 6. Return structured verification result
        # ---------------------------------------------------------
        return A2AMessage(
            message_id=f"{payload['incident_id']}-VERIFICATION",
            sender=self.name,
            receiver="orchestrator",
            message_type="verification_result",
            payload={
                "incident_id": payload["incident_id"],
                "service": payload["service"],
                "approved": approved,
                "decision": final_decision.value,
                "policy_ids": policy_ids,
                "reasons": reasons,
                "proposed_action": action,
            },
        )