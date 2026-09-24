from app.models.messages import A2AMessage


class OpsAgent:
    name = "ops"

    def propose_action(
        self,
        investigation: A2AMessage,
    ) -> A2AMessage:

        payload = investigation.payload

        service = payload["service"]
        environment = payload["environment"]

        return A2AMessage(
            message_id=f"{payload['incident_id']}-ACTION",
            sender=self.name,
            receiver="verifier",
            message_type="action_proposal",
            payload={
                "incident_id": payload["incident_id"],
                "service": service,
                "environment": environment,
                "proposed_action": {
                    "tool": "simulate_restart",
                    "service": service,
                    "reason": (
                        "Payment service has database connection "
                        "timeouts and elevated errors."
                    ),
                },
                "dependencies": payload["dependencies"],
                "dependency_metrics": payload["dependency_metrics"],
                "dependents": payload["dependents"],
                "owner": payload["owner"],
                "evidence": payload["evidence"],
            },
        )