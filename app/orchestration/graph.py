import time



from app.config import settings

from app.agents.planner import PlannerAgent

from app.agents.investigator import InvestigatorAgent

from app.agents.ops import OpsAgent

from app.agents.verifier import VerifierAgent

from app.models.incident import Incident

from app.orchestration.state import WorkflowState

from app.orchestration.persistence import WorkflowStateStore

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

        self.state_store = WorkflowStateStore()



    def run(self, incident: Incident) -> WorkflowState:

        state: WorkflowState = {

            "incident": incident.model_dump(),

            "status": "PLANNING",

            "error": None,

        }



        # Persist initial workflow state.

        self.state_store.save(

            incident.incident_id,

            state,

        )



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



        self.state_store.save(

            incident.incident_id,

            state,

        )



        # =========================================================

        # 2. Investigator / RAG

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

                        "logs",

                        [],

                    )

                ),

                "metrics_available": (

                    investigation.payload["metrics"].get(

                        "success",

                        False,

                    )

                ),

                "evidence_count": len(

                    investigation.payload.get(

                        "evidence",

                        [],

                    )

                ),

                "dependency_count": len(

                    investigation.payload.get(

                        "dependencies",

                        [],

                    )

                ),

            },

            latency_ms=investigator_latency,

        )



        state["investigation"] = (

            investigation.model_dump()

        )

        state["status"] = "ACTION_PROPOSED"



        self.state_store.save(

            incident.incident_id,

            state,

        )



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



        state["action_proposal"] = (

            proposal.model_dump()

        )

        state["status"] = "VERIFYING"



        self.state_store.save(

            incident.incident_id,

            state,

        )



        # =========================================================

        # 4. Verifier / Safety

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

                "decision": verification.payload.get(

                    "decision",

                    "UNKNOWN",

                ),

                "approved": verification.payload[

                    "approved"

                ],

                "reasons": verification.payload[

                    "reasons"

                ],

                "policy_ids": verification.payload.get(

                    "policy_ids",

                    [],

                ),

                "rejected_alternatives": (

                    ["restart payment-db"]

                    if (

                        verification.payload["approved"]

                        and proposal.payload["service"]

                        == "payment-service"

                    )

                    else []

                ),

            },

            latency_ms=verifier_latency,

        )



        state["verification"] = (

            verification.model_dump()

        )



        # =========================================================

        # Verification Decision

        # =========================================================

        verification_decision = verification.payload.get(

            "decision",

            "BLOCK",

        )



        # ---------------------------------------------------------

        # Human approval required

        # ---------------------------------------------------------

        if verification_decision == "REQUIRE_APPROVAL":

            state["status"] = "WAITING_FOR_APPROVAL"

            state["error"] = None



            state["approval"] = {

                "required": True,

                "status": "PENDING",

                "reasons": verification.payload.get(

                    "reasons",

                    [],

                ),

                "policy_ids": verification.payload.get(

                    "policy_ids",

                    [],

                ),

            }



            self.tracer.record(

                "approval_required",

                "orchestrator",

                {

                    "incident_id": incident.incident_id,

                    "service": proposal.payload["service"],

                    "policy_ids": verification.payload.get(

                        "policy_ids",

                        [],

                    ),

                    "reasons": verification.payload.get(

                        "reasons",

                        [],

                    ),

                },

            )



            self.state_store.save(

                incident.incident_id,

                state,

            )



            return state



        # ---------------------------------------------------------

        # Policy/safety rejection

        # ---------------------------------------------------------

        if verification_decision == "BLOCK":

            state["status"] = "FAILED"

            state["error"] = "; ".join(

                verification.payload.get(

                    "reasons",

                    [],

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

                    "policy_ids": verification.payload.get(

                        "policy_ids",

                        [],

                    ),

                    "reasons": verification.payload.get(

                        "reasons",

                        [],

                    ),

                },

            )



            self.state_store.save(

                incident.incident_id,

                state,

            )



            return state



        # ---------------------------------------------------------

        # Verified and allowed

        # ---------------------------------------------------------

        state["approval"] = {

            "required": False,

            "status": "NOT_REQUIRED",

        }



        # =========================================================

        # Verification Approved

        # =========================================================

        state["status"] = "APPROVED"



        self.state_store.save(

            incident.incident_id,

            state,

        )



        return self._execute_approved_action(state)



    def approve(self, workflow_id: str) -> WorkflowState:

        """Approve a workflow that is waiting for human approval."""

        state: WorkflowState = self.state_store.load(workflow_id)



        if state.get("status") != "WAITING_FOR_APPROVAL":

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

        state["status"] = "APPROVED"

        state["error"] = None



        self.tracer.record(

            "approval_granted",

            "orchestrator",

            {

                "incident_id": workflow_id,

                "actor": "human",

                "decision": "APPROVED",

                "action": action,

                "policy_ids": approval.get(

                    "policy_ids",

                    [],

                ),

                "reasons": approval.get(

                    "reasons",

                    [],

                ),

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



        if state.get("status") != "WAITING_FOR_APPROVAL":

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

        state["status"] = "REJECTED"

        state["error"] = reason



        self.tracer.record(

            "approval_rejected",

            "orchestrator",

            {

                "incident_id": workflow_id,

                "actor": "human",

                "decision": "REJECTED",

                "action": action,

                "policy_ids": approval.get(

                    "policy_ids",

                    [],

                ),

                "reasons": approval.get(

                    "reasons",

                    [],

                ),

                "rejection_reason": reason,

            },

        )



        self.state_store.save(workflow_id, state)



        return state



    def _execute_approved_action(

        self,

        state: WorkflowState,

    ) -> WorkflowState:

        """Execute the already-verified action stored in workflow state."""

        incident_data = state.get("incident", {})

        verification = state.get("verification", {})

        payload = verification.get("payload", {})

        action = payload.get("proposed_action")



        if not action:

            state["status"] = "FAILED"

            state["error"] = "Verified action is missing from workflow state."

            self.state_store.save(

                incident_data.get("incident_id", "unknown"),

                state,

            )

            return state



        workflow_id = incident_data.get(

            "incident_id",

            "unknown",

        )



        # =========================================================

        # 5. Execute Approved Simulated Action

        # =========================================================

        if action["tool"] == "simulate_restart":

            action_start = self.tracer.start_timer()



            action_result = None

            last_error = None



            # Retry the tool according to configured policy.

            # max_retries = 2 means a maximum of 3 total attempts.

            for attempt in range(settings.max_retries + 1):

                try:

                    attempt_start = time.perf_counter()



                    action_result = simulate_restart(

                        SimulateRestartRequest(

                            service=action["service"],

                            environment=incident_data["environment"],

                        )

                    )



                    elapsed_seconds = (

                        time.perf_counter() - attempt_start

                    )



                    # Enforce configured timeout.

                    if (

                        elapsed_seconds

                        > settings.tool_timeout_seconds

                    ):

                        raise TimeoutError(

                            "Tool execution exceeded "

                            f"{settings.tool_timeout_seconds} "

                            "seconds."

                        )



                    self.tracer.record(

                        "tool_attempt",

                        "orchestrator",

                        {

                            "tool": action["tool"],

                            "attempt": attempt + 1,

                            "max_attempts": (

                                settings.max_retries + 1

                            ),

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

                            "tool": action["tool"],

                            "attempt": attempt + 1,

                            "max_attempts": (

                                settings.max_retries + 1

                            ),

                            "error": last_error,

                        },

                    )



                    # Clear the result so a failed attempt

                    # cannot accidentally be treated as success.

                    action_result = None



            action_latency = self.tracer.elapsed_ms(

                action_start

            )



            # All attempts failed.

            if action_result is None:

                state["status"] = "FAILED"

                state["error"] = (

                    "Tool execution failed after "

                    f"{settings.max_retries + 1} attempts: "

                    f"{last_error}"

                )



                self.tracer.record(

                    "tool_failed",

                    "orchestrator",

                    {

                        "tool": action["tool"],

                        "service": action["service"],

                        "attempts": settings.max_retries + 1,

                        "error": last_error,

                    },

                    latency_ms=action_latency,

                )



                self.state_store.save(

                    workflow_id,

                    state,

                )



                return state



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

                state["error"] = None

            else:

                state["status"] = "FAILED"

                state["error"] = (

                    action_result.error.message

                    if action_result.error

                    else "Action failed."

                )



        else:

            state["status"] = "FAILED"

            state["error"] = (

                f"Unsupported action tool: "

                f"{action['tool']}"

            )



        # Persist the final workflow state.

        self.state_store.save(

            workflow_id,

            state,

        )



        return state
