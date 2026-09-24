from app.models.messages import A2AMessage
from app.safety.blast_radius import BlastRadiusCalculator
from app.safety.policies import check_action_policy


class VerifierAgent:
    name = "verifier"

    def verify(self, proposal: A2AMessage) -> A2AMessage:
        payload = proposal.payload
        action = payload["proposed_action"]

        approved = False
        reasons = []

                # Check action policy
        policy_result = check_action_policy(
            tool=action["tool"],
            service=action["service"],
            environment=payload["environment"],
        )

        if not policy_result.allowed:
            reasons.extend(policy_result.reasons)

        # Check blast radius
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

        if payload["environment"] != "production":
            reasons.append("Unsupported environment.")

        if action["tool"] != "simulate_restart":
            reasons.append("Action is not on the allowed tool list.")

        if action["service"] != payload["service"]:
            reasons.append("Action service does not match incident service.")

        # Database restart requires manual approval
        if action["service"] == "payment-db":
            reasons.append("Database restart requires manual approval.")

        # Check payment-db health before allowing payment-service restart
        if (
            action["service"] == "payment-service"
            and action["tool"] == "simulate_restart"
        ):
            dependency_metrics = payload.get("dependency_metrics", {})
            payment_db = dependency_metrics.get("payment-db")

            if not payment_db:
                reasons.append(
                    "Payment-db health information is missing."
                )
            elif not payment_db.get("success"):
                reasons.append(
                    "Payment-db health check failed."
                )
            elif not payment_db.get("metrics", {}).get("healthy", False):
                reasons.append(
                    "Payment-db is unhealthy. "
                    "Restart cannot be approved."
                )

        if not reasons:
            approved = True

        return A2AMessage(
            message_id=f"{payload['incident_id']}-VERIFICATION",
            sender=self.name,
            receiver="orchestrator",
            message_type="verification_result",
            payload={
                "incident_id": payload["incident_id"],
                "service": payload["service"],
                "approved": approved,
                "reasons": reasons,
                "proposed_action": action,
            },
        )