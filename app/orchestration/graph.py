from app.agents.planner import PlannerAgent
from app.agents.investigator import InvestigatorAgent
from app.agents.ops import OpsAgent
from app.agents.verifier import VerifierAgent
from app.models.incident import Incident
from app.orchestration.state import WorkflowState
from app.tools.restart import simulate_restart
from app.tools.schemas import SimulateRestartRequest
from app.tracing.tracer import Tracer
from app.version import (
    APP_VERSION,
    AGENT_VERSIONS,
    TOOL_VERSIONS,
)


class IncidentWorkflow:
    def __init__(self):
        self.planner = PlannerAgent()
        self.investigator = InvestigatorAgent()
        self.ops = OpsAgent()
        self.verifier = VerifierAgent()
        self.tracer = Tracer()

    def run(self, incident: Incident) -> WorkflowState:
        state: WorkflowState = {
            "incident": incident.model_dump(),
            "status": "PLANNING",
            "error": None,
        }

        # =========================================================
        # Workflow Started
        # =========================================================
        self.tracer.record(
    "workflow_started",
    "orchestrator",
    {
        "incident_id": incident.incident_id,
        "app_version": APP_VERSION,
        "agent_versions": AGENT_VERSIONS,
        "tool_versions": TOOL_VERSIONS,
    },
)


        estimated_cost = self.tracer.estimate_cost(
            input_tokens=0,
            output_tokens=0,
            input_cost_per_1k=0.0,
            output_cost_per_1k=0.0,
        )

        self.tracer.record(
            "cost_estimate",
            "orchestrator",
            {
                "provider": "ollama",
                "model": "llama3.2:3b",
                "estimated_cost_usd": estimated_cost,
                "pricing_basis": "local_inference",
            },
        )

        # =========================================================
        # 1. Planner
        # =========================================================
        planner_start = self.tracer.start_timer()

        plan = self.planner.create_plan(incident)

        planner_latency = self.tracer.elapsed_ms(
            planner_start
        )

        self.tracer.record(
            "agent_completed",
            "planner",
            {
                "message_type": plan.message_type,
            },
            latency_ms=planner_latency,
        )

        state["plan"] = plan.model_dump()
        state["status"] = "INVESTIGATING"

        # =========================================================
        # 2. Investigator
        # =========================================================
        investigator_start = self.tracer.start_timer()

        investigation = self.investigator.investigate(
            incident
        )

        investigator_latency = self.tracer.elapsed_ms(
            investigator_start
        )

        self.tracer.record(
    "agent_completed",
    "investigator",
    {
        "message_type": investigation.message_type,
        "service": incident.service,
        "logs_retrieved": len(
            investigation.payload["logs"].get(
                "logs", []
            )
        ),
        "metrics_available": investigation.payload[
            "metrics"
        ].get("success", False),
        "evidence_count": len(
            investigation.payload.get(
                "evidence", []
            )
        ),
        "dependency_count": len(
            investigation.payload.get(
                "dependencies", []
            )
        ),
    },
    latency_ms=investigator_latency,
)

        state["investigation"] = investigation.model_dump()
        state["status"] = "ACTION_PROPOSED"

        # =========================================================
        # 3. Ops
        # =========================================================
        ops_start = self.tracer.start_timer()

        proposal = self.ops.propose_action(
            investigation
        )

        ops_latency = self.tracer.elapsed_ms(
            ops_start
        )

        self.tracer.record(
            "agent_completed",
            "ops",
            {
                "message_type": proposal.message_type,
                "tool": proposal.payload[
                    "proposed_action"
                ]["tool"],
                "service": proposal.payload[
                    "proposed_action"
                ]["service"],
            },
            latency_ms=ops_latency,
        )

        state["action_proposal"] = proposal.model_dump()
        state["status"] = "VERIFYING"

        # =========================================================
        # 4. Verifier
        # =========================================================
        verifier_start = self.tracer.start_timer()

        verification = self.verifier.verify(
            proposal
        )

        verifier_latency = self.tracer.elapsed_ms(
            verifier_start
        )

        self.tracer.record(
    "decision_made",
    "verifier",
    {
        "decision": (
            "approved"
            if verification.payload["approved"]
            else "rejected"
        ),
        "approved": verification.payload["approved"],
        "reasons": verification.payload["reasons"],
        "rejected_alternatives": (
            ["restart payment-db"]
            if verification.payload["approved"]
            and proposal.payload["service"] == "payment-service"
            else []
        ),
    },
    latency_ms=verifier_latency,
)

        state["verification"] = verification.model_dump()

        # =========================================================
        # Verification Failed
        # =========================================================
        if not verification.payload["approved"]:
            state["status"] = "FAILED"
            state["error"] = "; ".join(
                verification.payload["reasons"]
            )

            return state

        state["status"] = "APPROVED"

        # =========================================================
        # 5. Execute Approved Simulated Action
        # =========================================================
        action = verification.payload[
            "proposed_action"
        ]

        if action["tool"] == "simulate_restart":

            action_start = self.tracer.start_timer()

            action_result = simulate_restart(
                SimulateRestartRequest(
                    service=action["service"],
                    environment=incident.environment,
                )
            )

            action_latency = self.tracer.elapsed_ms(
                action_start
            )

            self.tracer.record(
                "tool_executed",
                "orchestrator",
                {
                    "tool": action["tool"],
                    "service": action["service"],
                    "success": action_result.success,
                    "simulated": action_result.simulated,
                },
                latency_ms=action_latency,
            )

            state["action_result"] = (
                action_result.model_dump()
            )

            if action_result.success:
                state["status"] = "COMPLETED"

            else:
                state["status"] = "FAILED"

                state["error"] = (
                    action_result.error.message
                    if action_result.error
                    else "Action failed."
                )

        return state