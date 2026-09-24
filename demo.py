from app.models.incident import Incident
from app.orchestration.graph import IncidentWorkflow


def main():
    print("=" * 60)
    print("MINI AGENTIC AI PLATFORM - INCIDENT DEMO")
    print("=" * 60)

    incident = Incident(
        incident_id="DEMO-001",
        service="payment-service",
        environment="production",
        description="Payment service has database connection timeouts and elevated errors.",
        severity="high",
    )

    print("\n[INCIDENT]")
    print(f"ID: {incident.incident_id}")
    print(f"Service: {incident.service}")
    print(f"Environment: {incident.environment}")
    print(f"Severity: {incident.severity}")

    workflow = IncidentWorkflow()

    print("\n[1] Planner")
    print("Creating investigation plan...")

    print("\n[2] Investigator / RAG")
    print("Collecting logs, metrics, runbook evidence, and dependencies...")

    print("\n[3] Ops")
    print("Proposing remediation action...")

    print("\n[4] Verifier / Safety")
    print("Checking policy, dependency health, and blast radius...")

    result = workflow.run(incident)

    print("\n[WORKFLOW RESULT]")
    print(f"Status: {result['status']}")

    if result.get("verification"):
        verification = result["verification"]["payload"]

        print(f"Approved: {verification['approved']}")
        print(f"Reasons: {verification['reasons']}")

        if verification.get("proposed_action"):
            print(
                f"Proposed action: "
                f"{verification['proposed_action']}"
            )

    if result.get("action_result"):
        print("\n[ACTION]")
        print(result["action_result"])

    print("\n[TRACE]")
    for event in workflow.tracer.get_events():
        print(
            f"{event['event_type']} | "
            f"{event['component']} | "
            f"{event['latency_ms']} ms"
        )

    print("\n[REPLAY]")
    replay = workflow.tracer.replay()
    print(f"Trace events: {len(replay)}")
    print(
        f"Replay matches trace: "
        f"{replay == workflow.tracer.get_events()}"
    )

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
    