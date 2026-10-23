
import time

from app.config import settings
from app.agents.planner import PlannerAgent
from app.agents.investigator import InvestigatorAgent
from app.agents.ops import OpsAgent
from app.agents.verifier import VerifierAgent
from app.models.incident import Incident
from app.orchestration.state import (
    State,
    WorkflowState,
    validate_transition,
    IllegalStateTransitionError,
)
from app.orchestration.persistence import WorkflowStateStore
from app.safety.policies import (
    PolicyDecision,
    check_action_policy,
    is_database_service,
)
from app.tools.restart import simulate_restart
from app.tools.scale import simulate_scale
from app.tools.schemas import (
    SimulateRestartRequest,
    SimulateScaleRequest,
)
from app.tracing.tracer import Tracer
from app.version import APP_VERSION, AGENT_VERSIONS, TOOL_VERSIONS


class IncidentWorkflow:
    def __init__(self):
        self.planner = PlannerAgent()
        self.investigator = InvestigatorAgent()
        self.ops = OpsAgent()
        self.verifier = VerifierAgent()
        self.tracer = Tracer()
        self.state_store = WorkflowStateStore()

    def _transition_to(
        self,
        state: WorkflowState,
        target: State | str,
    ) -> None:
        """Validate and apply a legal workflow state transition."""
        current = state.get("status")
        target_state = validate_transition(current, target)
        state["status"] = target_state.value

    def run(self, incident: Incident) -> WorkflowState:
        state: WorkflowState = {
            "incident": incident.model_dump(),
            "status": None,
            "error": None,
        }

        self._transition_to(state, State.PLANNING)
        self.state_store.save(incident.incident_id, state)

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

        # 1. Planner
        planner_start = self.tracer.start_timer()
        plan = self.planner.create_plan(incident)
        planner_latency = self.tracer.elapsed_ms(planner_start)

        self.tracer.record(
            "agent_completed",
            "planner",
            {"message_type": plan.message_type},
            latency_ms=planner_latency,
        )

        state["plan"] = plan.model_dump()
        self._transition_to(state, State.INVESTIGATING)
        self.state_store.save(incident.incident_id, state)

        # 2. Investigator
        investigator_start = self.tracer.start_timer()
        investigation = self.investigator.investigate(incident)
        investigator_latency = self.tracer.elapsed_ms(investigator_start)

        self.tracer.record(
            "agent_completed",
            "investigator",
            {
                "message_type": investigation.message_type,
                "service": incident.service,
                "logs_retrieved": len(
                    investigation.payload.get("logs", {}).get("logs", [])
                ),
                "metrics_available": investigation.payload.get(
                    "metrics", {}
                ).get("success", False),
                "evidence_count": len(
                    investigation.payload.get("evidence", [])
                ),
                "dependency_count": len(
                    investigation.payload.get("dependencies", [])
                ),
            },
            latency_ms=investigator_latency,
        )

        state["investigation"] = investigation.model_dump()
        self._transition_to(state, State.ACTION_PROPOSED)
        self.state_store.save(incident.incident_id, state)

        # 3. Ops
        ops_start = self.tracer.start_timer()
        proposal = self.ops.propose_action(investigation)
        ops_latency = self.tracer.elapsed_ms(ops_start)
        proposed_action = proposal.payload["proposed_action"]

        self.tracer.record(
            "agent_completed",
            "ops",
            {
                "message_type": proposal.message_type,
                "tool": proposed_action["tool"],
                "service": proposed_action["service"],
            },
            latency_ms=ops_latency,
        )

        state["action_proposal"] = proposal.model_dump()
        self._transition_to(state, State.VERIFYING)
        self.state_store.save(incident.incident_id, state)

        # 4. Verifier / safety
        verifier_start = self.tracer.start_timer()
        verification = self.verifier.verify(proposal)
        verifier_latency = self.tracer.elapsed_ms(verifier_start)

        self.tracer.record(
            "decision_made",
            "verifier",
            {
                "decision": verification.payload.get("decision", "UNKNOWN"),
                "approved": verification.payload.get("approved", False),
                "reasons": verification.payload.get("reasons", []),
                "policy_ids": verification.payload.get("policy_ids", []),
                "rejected_alternatives": (
                    ["restart payment-db"]
                    if (
                        verification.payload.get("approved")
                        and proposed_action.get("service") == "payment-service"
                    )
                    else []
                ),
            },
            latency_ms=verifier_latency,
        )

        state["verification"] = verification.model_dump()
        verification_decision = verification.payload.get(
            "decision",
            PolicyDecision.BLOCK.value,
        )

        # Case A: Human approval is required.
        if verification_decision == PolicyDecision.REQUIRE_APPROVAL.value:
            self._transition_to(state, State.WAITING_FOR_APPROVAL)
            state["error"] = None
            state["approval"] = {
                "required": True,
                "status": "PENDING",
                "reasons": verification.payload.get("reasons", []),
                "policy_ids": verification.payload.get("policy_ids", []),
            }

            self.tracer.record(
                "approval_required",
                "orchestrator",
                {
                    "incident_id": incident.incident_id,
                    "service": proposed_action["service"],
                    "policy_ids": verification.payload.get("policy_ids", []),
                    "reasons": verification.payload.get("reasons", []),
                },
            )

            self.state_store.save(incident.incident_id, state)
            return state

        # Case B: The action is blocked by safety policy.
        if verification_decision == PolicyDecision.BLOCK.value:
            self._transition_to(state, State.FAILED)
            state["error"] = "; ".join(
                verification.payload.get(
                    "reasons",
                    ["Action blocked by safety policy."],
                )
            )
            state["approval"] = {
                "required": False,
                "status": "NOT_REQUIRED",
            }

            self.tracer.record(
                "action_blocked",
                "orchestrator",
                {
                    "incident_id": incident.incident_id,
                    "policy_ids": verification.payload.get("policy_ids", []),
                    "reasons": verification.payload.get("reasons", []),
                },
            )

            self.state_store.save(incident.incident_id, state)
            return state

        # Case C: The action is allowed without human approval.
        state["approval"] = {
            "required": False,
            "status": "NOT_REQUIRED",
        }

        self._transition_to(state, State.APPROVED)
        self.state_store.save(incident.incident_id, state)

        return self._execute_approved_action(state)


    def stop(
        self,
        workflow_id: str,
        reason: str = "Workflow stopped by operator.",
    ) -> WorkflowState:
        """Stop a workflow before its action is executed."""
        state: WorkflowState = self.state_store.load(workflow_id)
        previous_status = state.get("status")

        try:
            self._transition_to(state, State.STOPPED)
        except IllegalStateTransitionError as exc:
            raise ValueError(
                f"Workflow '{workflow_id}' cannot be stopped "
                f"from status '{previous_status}'."
            ) from exc

        state["error"] = reason

        approval = state.get("approval")
        if approval:
            state["approval"] = {
                **approval,
                "status": "STOPPED",
                "stopped_by": "operator",
                "stop_reason": reason,
            }

        self.tracer.record(
            "workflow_stopped",
            "orchestrator",
            {
                "incident_id": workflow_id,
                "previous_status": previous_status,
                "stopped_by": "operator",
                "reason": reason,
            },
        )

        self.state_store.save(workflow_id, state)
        return state


    def approve(self, workflow_id: str) -> WorkflowState:
        """Approve a workflow that is waiting for human approval."""
        state: WorkflowState = self.state_store.load(workflow_id)

        if state.get("status") != State.WAITING_FOR_APPROVAL.value:
            raise ValueError(
                f"Workflow '{workflow_id}' is not waiting for approval."
            )

        approval = state.get("approval", {})
        if approval.get("status") != "PENDING":
            raise ValueError(
                f"Workflow '{workflow_id}' has no pending approval."
            )

        verification = state.get("verification", {})
        payload = verification.get("payload", {})
        action = payload.get("proposed_action", {})

        state["approval"] = {
            **approval,
            "status": "APPROVED",
            "approved_by": "human",
        }

        self._transition_to(state, State.APPROVED)
        state["error"] = None

        self.tracer.record(
            "approval_granted",
            "orchestrator",
            {
                "incident_id": workflow_id,
                "actor": "human",
                "decision": "APPROVED",
                "action": action,
                "policy_ids": approval.get("policy_ids", []),
                "reasons": approval.get("reasons", []),
            },
        )

        self.state_store.save(workflow_id, state)
        return self._execute_approved_action(state)

    def reject(
        self,
        workflow_id: str,
        reason: str = "Rejected by human reviewer.",
    ) -> WorkflowState:
        """Reject a workflow that is waiting for human approval."""
        state: WorkflowState = self.state_store.load(workflow_id)

        if state.get("status") != State.WAITING_FOR_APPROVAL.value:
            raise ValueError(
                f"Workflow '{workflow_id}' is not waiting for approval."
            )

        approval = state.get("approval", {})
        if approval.get("status") != "PENDING":
            raise ValueError(
                f"Workflow '{workflow_id}' has no pending approval."
            )

        verification = state.get("verification", {})
        payload = verification.get("payload", {})
        action = payload.get("proposed_action", {})

        state["approval"] = {
            **approval,
            "status": "REJECTED",
            "rejected_by": "human",
            "rejection_reason": reason,
        }

        self._transition_to(state, State.REJECTED)
        state["error"] = reason

        self.tracer.record(
            "approval_rejected",
            "orchestrator",
            {
                "incident_id": workflow_id,
                "actor": "human",
                "decision": "REJECTED",
                "action": action,
                "policy_ids": approval.get("policy_ids", []),
                "reasons": approval.get("reasons", []),
                "rejection_reason": reason,
            },
        )

        self.state_store.save(workflow_id, state)
        return state

    def _execute_approved_action(
        self,
        state: WorkflowState,
    ) -> WorkflowState:
        """
        Execute a verified and approved action.

        Revalidates safety invariants, scope boundaries, and approval
        independently before invoking a tool.
        """
        workflow_id = state.get("incident", {}).get(
            "incident_id",
            "unknown",
        )

        # Record the stop event before returning.
        if state.get("status") == State.STOPPED.value:
            state["error"] = state.get(
                "error",
                "Workflow was stopped before action execution.",
            )

            self.tracer.record(
                "action_execution_prevented",
                "orchestrator",
                {
                    "incident_id": workflow_id,
                    "reason": state["error"],
                },
            )

            self.state_store.save(workflow_id, state)
            return state

        # Execution requires APPROVED state.
        if state.get("status") != State.APPROVED.value:
            raise IllegalStateTransitionError(
                "Execution boundary rejected: Cannot execute action "
                f"from status '{state.get('status')}'. "
                f"Workflow must be in '{State.APPROVED.value}' state."
            )

        incident_data = state.get("incident", {})
        verification = state.get("verification", {})
        payload = verification.get("payload", {})
        action = payload.get("proposed_action")

        if not action:
            self._transition_to(state, State.FAILED)
            state["error"] = (
                "Execution boundary rejected: "
                "Action is missing from workflow state."
            )
            self.state_store.save(workflow_id, state)
            return state

        target_service = action.get("service")
        target_tool = action.get("tool")
        target_env = incident_data.get("environment")

        # Check 1: Action service must match incident service.
        if not target_service or target_service != incident_data.get("service"):
            self._transition_to(state, State.FAILED)
            state["error"] = (
                f"Execution boundary rejected: Action service "
                f"'{target_service}' does not match incident service "
                f"'{incident_data.get('service')}'."
            )
            self.state_store.save(workflow_id, state)
            return state

        # Check 2: Prevent cross-environment actions.
        if (
            action.get("environment")
            and action["environment"] != target_env
        ):
            self._transition_to(state, State.FAILED)
            state["error"] = (
                "Execution boundary rejected: Cross-environment action "
                f"detected. Action environment '{action.get('environment')}' "
                f"!= incident '{target_env}'."
            )
            self.state_store.save(workflow_id, state)
            return state

        # Check 3: Re-evaluate central policy at execution time.
        boundary_policy = check_action_policy(
            tool=target_tool,
            service=target_service,
            environment=target_env,
            action_environment=action.get("environment"),
        )

        if boundary_policy.decision == PolicyDecision.BLOCK:
            self._transition_to(state, State.FAILED)
            state["error"] = (
                "Execution boundary blocked: "
                f"{'; '.join(boundary_policy.reasons)}"
            )
            self.state_store.save(workflow_id, state)
            return state

        # Check 4: Production actions require human approval.
        if target_env == "production":
            approval = state.get("approval", {})
            if (
                approval.get("status") != "APPROVED"
                or approval.get("approved_by") != "human"
            ):
                self._transition_to(state, State.FAILED)
                state["error"] = (
                    "Execution boundary rejected: Production action "
                    "lacks required human approval."
                )
                self.state_store.save(workflow_id, state)
                return state

        # Check 5: Database actions require approval.
        if is_database_service(target_service):
            approval = state.get("approval", {})
            if (
                approval.get("status") != "APPROVED"
                or not approval.get("approved_by")
            ):
                self._transition_to(state, State.FAILED)
                state["error"] = (
                    "Execution boundary rejected: Database restart for "
                    f"'{target_service}' lacks required approval."
                )
                self.state_store.save(workflow_id, state)
                return state

        # Check 6: Scale replicas must be a positive integer.
        if target_tool == "simulate_scale":
            replicas = action.get("replicas")

            if (
                isinstance(replicas, bool)
                or not isinstance(replicas, int)
                or replicas < 1
            ):
                self._transition_to(state, State.FAILED)
                state["error"] = (
                    "Invalid scale action: replicas must be "
                    "a positive integer."
                )
                self.state_store.save(workflow_id, state)
                return state

        # 5. Execute the approved simulated action.
        if target_tool in {"simulate_restart", "simulate_scale"}:
            action_start = self.tracer.start_timer()
            action_result = None
            last_error = None

            # max_retries=2 allows at most 3 attempts.
            for attempt in range(settings.max_retries + 1):
                try:
                    attempt_start = time.perf_counter()

                    if target_tool == "simulate_restart":
                        action_result = simulate_restart(
                            SimulateRestartRequest(
                                service=target_service,
                                environment=target_env,
                            )
                        )
                    else:
                        action_result = simulate_scale(
                            SimulateScaleRequest(
                                service=target_service,
                                replicas=action["replicas"],
                                environment=target_env,
                            )
                        )

                    elapsed_seconds = time.perf_counter() - attempt_start

                    if elapsed_seconds > settings.tool_timeout_seconds:
                        raise TimeoutError(
                            "Tool execution exceeded "
                            f"{settings.tool_timeout_seconds} seconds."
                        )

                    self.tracer.record(
                        "tool_attempt",
                        "orchestrator",
                        {
                            "tool": target_tool,
                            "attempt": attempt + 1,
                            "max_attempts": settings.max_retries + 1,
                            "success": action_result.success,
                        },
                    )
                    break

                except Exception as exc:
                    last_error = str(exc)

                    self.tracer.record(
                        "tool_retry",
                        "orchestrator",
                        {
                            "tool": target_tool,
                            "attempt": attempt + 1,
                            "max_attempts": settings.max_retries + 1,
                            "error": last_error,
                        },
                    )

                    action_result = None

            action_latency = self.tracer.elapsed_ms(action_start)

            # All attempts failed.
            if action_result is None:
                self._transition_to(state, State.FAILED)
                state["error"] = (
                    f"Tool execution failed after "
                    f"{settings.max_retries + 1} attempts: {last_error}"
                )

                self.tracer.record(
                    "tool_failed",
                    "orchestrator",
                    {
                        "tool": target_tool,
                        "service": target_service,
                        "attempts": settings.max_retries + 1,
                        "error": last_error,
                    },
                    latency_ms=action_latency,
                )

                self.state_store.save(workflow_id, state)
                return state

            self.tracer.record(
                "tool_executed",
                "orchestrator",
                {
                    "tool": target_tool,
                    "service": target_service,
                    "success": action_result.success,
                    "simulated": action_result.simulated,
                },
                latency_ms=action_latency,
            )

            state["action_result"] = action_result.model_dump()

            if action_result.success:
                self._transition_to(state, State.COMPLETED)
                state["error"] = None
            else:
                self._transition_to(state, State.FAILED)
                state["error"] = (
                    action_result.error.message
                    if action_result.error
                    else "Action execution returned unsuccessful."
                )

        else:
            self._transition_to(state, State.FAILED)
            state["error"] = f"Unsupported action tool: '{target_tool}'."

        self.state_store.save(workflow_id, state)
        return state
