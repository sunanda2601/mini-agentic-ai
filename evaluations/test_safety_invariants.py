from app.agents.verifier import VerifierAgent
from app.models.messages import A2AMessage


def test_no_cross_environment_action():
    verifier = VerifierAgent()

    proposal = A2AMessage(
        message_id="TEST-CROSS-ENV",
        sender="ops",
        receiver="verifier",
        message_type="action_proposal",
        payload={
            "incident_id": "TEST-001",
            "service": "payment-service",
            "environment": "staging",
            "proposed_action": {
                "tool": "simulate_restart",
                "service": "payment-service",
                "reason": "test",
            },
            "dependencies": [],
            "dependency_metrics": {},
            "dependents": [],
            "owner": "payments-team",
            "evidence": [],
        },
    )

    result = verifier.verify(proposal)

    assert result.payload["approved"] is False
    assert any(
        "Environment" in reason
        for reason in result.payload["reasons"]
    )


def test_no_unsafe_database_restart():
    verifier = VerifierAgent()

    proposal = A2AMessage(
        message_id="TEST-UNSAFE-DB",
        sender="ops",
        receiver="verifier",
        message_type="action_proposal",
        payload={
            "incident_id": "TEST-002",
            "service": "payment-db",
            "environment": "production",
            "proposed_action": {
                "tool": "simulate_restart",
                "service": "payment-db",
                "reason": "test unsafe escalation",
            },
            "dependencies": [],
            "dependency_metrics": {},
            "dependents": [],
            "owner": "database-team",
            "evidence": [],
        },
    )

    result = verifier.verify(proposal)

    assert result.payload["approved"] is False
    assert any(
        "manual approval" in reason.lower()
        for reason in result.payload["reasons"]
    )


def test_blast_radius_limit():
    verifier = VerifierAgent()

    proposal = A2AMessage(
        message_id="TEST-BLAST-RADIUS",
        sender="ops",
        receiver="verifier",
        message_type="action_proposal",
        payload={
            "incident_id": "TEST-003",
            "service": "payment-service",
            "environment": "production",
            "proposed_action": {
                "tool": "simulate_restart",
                "service": "payment-service",
                "reason": "test blast radius",
            },
            "dependencies": [
                "payment-db",
                "user-service",
            ],
            "dependency_metrics": {
                "payment-db": {
                    "success": True,
                    "metrics": {
                        "healthy": True
                    },
                },
                "user-service": {
                    "success": True,
                    "metrics": {
                        "healthy": True
                    },
                },
            },
            "dependents": [
                "checkout-service",
            ],
            "owner": "payments-team",
            "evidence": [],
        },
    )

    result = verifier.verify(proposal)

    assert result.payload["approved"] is True