from app.agents.verifier import VerifierAgent
from app.models.messages import A2AMessage


def test_no_cross_environment_action():
    """Verify that actions attempting to mutate across environments are blocked."""
    verifier = VerifierAgent()

    # Incident is in staging, but proposed action targets production
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
                "environment": "production",
                "reason": "cross environment test",
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
    assert result.payload["decision"] == "BLOCK"
    assert any(
        "cross-environment" in reason.lower()
        for reason in result.payload["reasons"]
    )
    assert "ENV-CROSS" in result.payload["policy_ids"]


def test_no_unsafe_database_restart():
    """Verify that restarting a database service requires human approval."""
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
    assert result.payload["decision"] == "REQUIRE_APPROVAL"
    assert any(
        "manual approval" in reason.lower()
        for reason in result.payload["reasons"]
    )


def test_staging_autonomous_within_blast_radius():
    """Verify staging remediation executes autonomously when blast radius and health checks pass."""
    verifier = VerifierAgent()

    proposal = A2AMessage(
        message_id="TEST-BLAST-RADIUS-STAGING",
        sender="ops",
        receiver="verifier",
        message_type="action_proposal",
        payload={
            "incident_id": "TEST-003",
            "service": "payment-service",
            "environment": "staging",
            "proposed_action": {
                "tool": "simulate_restart",
                "service": "payment-service",
                "reason": "test blast radius staging",
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
    assert result.payload["decision"] == "ALLOW"


def test_every_production_mutation_requires_human_approval():
    """Verify that every production mutation requires explicit human approval."""
    verifier = VerifierAgent()

    proposal = A2AMessage(
        message_id="TEST-PROD-APPROVAL-REQ",
        sender="ops",
        receiver="verifier",
        message_type="action_proposal",
        payload={
            "incident_id": "TEST-004",
            "service": "payment-service",
            "environment": "production",
            "proposed_action": {
                "tool": "simulate_restart",
                "service": "payment-service",
                "reason": "production restart attempt",
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

    assert result.payload["approved"] is False
    assert result.payload["decision"] == "REQUIRE_APPROVAL"
    assert any(
        "human approval" in reason.lower()
        for reason in result.payload["reasons"]
    )
    assert "APPROVAL-PROD" in result.payload["policy_ids"]


def test_unknown_environment_fails_closed():
    """Verify that unknown environments are blocked."""
    verifier = VerifierAgent()

    proposal = A2AMessage(
        message_id="TEST-UNKNOWN-ENV",
        sender="ops",
        receiver="verifier",
        message_type="action_proposal",
        payload={
            "incident_id": "TEST-005",
            "service": "payment-service",
            "environment": "sandbox",
            "proposed_action": {
                "tool": "simulate_restart",
                "service": "payment-service",
                "reason": "sandbox test",
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
    assert result.payload["decision"] == "BLOCK"
    assert "ENV-001" in result.payload["policy_ids"]