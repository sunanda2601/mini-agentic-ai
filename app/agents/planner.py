from app.models.incident import Incident
from app.models.messages import A2AMessage


class PlannerAgent:
    name = "planner"

    def create_plan(self, incident: Incident) -> A2AMessage:
        return A2AMessage(
            message_id=f"{incident.incident_id}-PLAN",
            sender=self.name,
            receiver="investigator",
            message_type="investigation_request",
            payload={
                "incident_id": incident.incident_id,
                "service": incident.service,
                "environment": incident.environment,
                "severity": incident.severity,
                "investigation_steps": [
                    "get_logs",
                    "get_metrics",
                    "retrieve_runbook",
                    "check_dependency_graph",
                ],
                "reason": (
                    "Investigate the incident using operational data, "
                    "runbooks, and service dependencies before proposing remediation."
                ),
            },
        )