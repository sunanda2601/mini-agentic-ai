Mini Agentic AI Platform
A production-oriented prototype for AI-assisted production incident analysis and safe remediation.
The platform uses four specialized agents to investigate an incident, collect evidence, propose a remediation, and pass that proposal through deterministic safety checks before a simulated infrastructure action can run.
> **Core principle:** the LLM can propose an action, but deterministic safety controls decide whether the action is allowed to execute.
---
Overview
Given an operational incident, the platform:
Creates an investigation plan.
Collects logs and metrics.
Retrieves relevant runbooks using hybrid lexical + semantic search.
Traverses service dependencies using a knowledge graph.
Proposes a remediation action.
Validates the proposal with deterministic safety policies.
Checks dependency health and blast radius.
Executes an approved simulated infrastructure action.
Persists workflow state.
Records an auditable trace and supports trace replay.
The prototype is intentionally designed for controlled demonstration and evaluation. It does not modify real production infrastructure.
---
Architecture
```text
                         Incident
                            │
                            ▼
                    ┌──────────────┐
                    │    Planner   │
                    └──────┬───────┘
                           │
                    investigation_request
                           │
                           ▼
              ┌─────────────────────────┐
              │ Investigator / RAG Agent│
              └────────────┬────────────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
           Logs         Metrics      Hybrid RAG
                                           │
                                      Runbooks
                                           │
                           ┌───────────────┘
                           ▼
                    Knowledge Graph
                           │
                           ▼
                    Dependency Health
                           │
                           ▼
                    ┌──────────────┐
                    │     Ops      │
                    └──────┬───────┘
                           │
                     action_proposal
                           │
                           ▼
                  ┌─────────────────┐
                  │ Verifier/Safety │
                  └────────┬────────┘
                           │
                    ┌──────┴──────┐
                    │             │
                  Reject        Approve
                    │             │
                   STOP           ▼
                         Simulated Tool
                               │
                               ▼
                      Persisted State
                               │
                               ▼
                         Audit Trace
```
Main components
Component	Responsibility
Planner	Creates the investigation plan
Investigator / RAG	Collects operational evidence
Ops	Proposes a remediation
Verifier / Safety	Makes the final deterministic safety decision
Orchestrator	Controls workflow states and transitions
RAG	Retrieves relevant operational documentation
Knowledge Graph	Represents service dependencies and ownership
Tool Layer	Provides structured infrastructure operations
Persistence	Stores workflow state as JSON
Tracing	Records execution, decisions, latency and failures
Evaluations	Validates important safety invariants
---
Agent Workflow
The four agents communicate using structured `A2AMessage` objects rather than uncontrolled conversational text.
```text
Planner
   │
   │ investigation_request
   ▼
Investigator
   │
   │ investigation_result
   ▼
Ops
   │
   │ action_proposal
   ▼
Verifier
   │
   ├── rejected ───────────────► workflow FAILED
   │
   └── approved
          │
          ▼
   Simulated Infrastructure Tool
```
Each A2A message contains structured fields such as:
`message_id`
`sender`
`receiver`
`message_type`
`timestamp`
`payload`
This makes agent communication easier to validate, test, trace and audit.
---
Agents
1. Planner Agent
The Planner receives the incident and creates a structured investigation plan.
The plan can include:
`get_logs`
`get_metrics`
runbook retrieval
dependency graph checks
The Planner does not execute infrastructure actions.
---
2. Investigator / RAG Agent
The Investigator gathers the evidence needed to understand the incident.
It collects:
service logs
service metrics
relevant runbooks
dependencies
dependent services
dependency health
service owner information
runbook citations
It combines hybrid retrieval with knowledge-graph traversal.
---
3. Infra / Ops Agent
The Ops agent receives the investigation result and proposes a remediation.
For the included demonstration, the proposal is:
```text
simulate_restart(payment-service)
```
The proposal is not executed immediately.
It must first pass the Verifier.
---
4. Verifier / Safety Agent
The Verifier is the final safety gate.
It checks:
environment policy
allowed tools
service/action consistency
restricted services
dependency health
blast radius
action-specific safety rules
If any safety condition fails, the workflow stops without executing the proposed action.
For example:
```text
payment-db
```
cannot be directly restarted because the prototype requires manual approval for that operation.
---
Workflow State Machine
The orchestrator uses explicit workflow states:
```text
PLANNING
   │
   ▼
INVESTIGATING
   │
   ▼
ACTION_PROPOSED
   │
   ▼
VERIFYING
   │
   ├──────────────► FAILED
   │
   ▼
APPROVED
   │
   ▼
COMPLETED
```
The orchestrator persists state after important transitions.
This prevents workflow control from being hidden entirely inside an LLM response.
---
Safety Model
The most important design decision is the separation between reasoning and execution.
```text
LLM / Agent Proposal
        │
        ▼
Deterministic Verification
        │
        ├── Policy
        ├── Environment
        ├── Tool allowlist
        ├── Dependency health
        ├── Blast radius
        └── Manual approval rules
        │
        ├── Reject → STOP
        │
        └── Approve
               │
               ▼
        Simulated Tool
```
Blast radius
The current configuration is:
```text
max_blast_radius = 2
```
The blast-radius calculator considers the target service and its direct dependent services.
Dependency health
Before approving the demonstration restart of `payment-service`, the Verifier checks the health of `payment-db`.
Environment safety
The tool layer and Verifier validate the environment. Unsupported environments are rejected.
---
Hybrid RAG
The Investigator uses two retrieval approaches:
BM25
BM25 provides lexical retrieval and is useful for exact operational terms such as:
service names
error messages
technical keywords
Semantic retrieval
Semantic retrieval uses:
```text
sentence-transformers
all-MiniLM-L6-v2
```
This helps retrieve conceptually related evidence even when wording differs.
Hybrid retrieval flow
```text
Incident description
        │
        ├──────────────► BM25
        │
        └──────────────► Semantic Search
                              │
                              ▼
                       Score Fusion
                              │
                              ▼
                       Top Results
                              │
                              ▼
                     Runbook Citations
```
Retrieval supports metadata filtering, including service-level filtering.
---
Knowledge Graph
The prototype uses NetworkX for service dependency relationships.
Example:
```text
checkout-service
       │
       ▼
payment-service
       │
       ├────► payment-db
       │
       └────► user-service
```
The graph supports:
`get_dependencies(service)`
`get_dependents(service)`
`get_owner(service)`
`get_runbooks(service)`
The Investigator uses the graph to understand the incident context.
The Verifier uses dependency information as part of safety validation and blast-radius analysis.
---
MCP-Style Tool Layer
The project implements a local MCP-style, schema-first tool layer.
It is not a full external MCP protocol server; instead, the prototype focuses on the important tool-contract concepts required by the exercise.
Available tools:
Tool	Purpose
`get_logs`	Retrieve service logs
`get_metrics`	Retrieve service metrics
`simulate_restart`	Simulate a service restart
`simulate_scale`	Simulate a replica change
`get_dependency_graph`	Retrieve service dependency information
Tool contracts
Tools use:
Pydantic request schemas
Pydantic response schemas
versioned contracts
tenant identifiers
environment identifiers
explicit success/failure fields
structured error codes
Current tool contract version:
```text
1.0.0
```
Examples of structured errors include:
```text
UNSUPPORTED_ENVIRONMENT
SERVICE_NOT_FOUND
SERVICE_LOG_NOT_FOUND
SERVICE_METRICS_NOT_FOUND
INFRASTRUCTURE_DATA_NOT_FOUND
INVALID_REPLICA_COUNT
```
Tenant and environment context
The demonstration uses:
```text
tenant_id = demo-tenant
environment = production
```
Tenant and environment are carried through tool contracts. The current prototype represents tenant scoping at the contract level rather than providing distributed infrastructure isolation.
---
Simulated Infrastructure
Infrastructure operations are deliberately simulated.
The prototype does not modify:
Kubernetes clusters
cloud infrastructure
production databases
production services
real replicas
Supported simulated operations include:
```text
simulate_restart
simulate_scale
```
This allows the complete agentic workflow to be demonstrated without introducing real infrastructure risk.
---
Persistence and Replay
Workflow state is persisted as JSON under:
```text
traces/
```
The persistence layer is implemented by:
```text
WorkflowStateStore
```
It supports:
```text
save(workflow_id, state)
load(workflow_id)
```
Persistence provides:
state inspection
debugging
process-level durability
auditability
replay support
The prototype uses file-based persistence because it is simple and appropriate for a small local system.
For a distributed production deployment, this could be replaced with a durable workflow engine or database-backed state store.
Replay
The current replay mechanism replays the recorded trace data for verification. It is not a full re-execution of every workflow step.
---
Observability and Audit Trace
The tracing layer records important workflow events.
Example trace:
```text
workflow_started
cost_estimate
agent_completed        planner
agent_completed        investigator
agent_completed        ops
decision_made          verifier
tool_attempt            orchestrator
tool_executed           orchestrator
```
Trace records can include:
timestamp
event type
component
details
latency
Sensitive-data redaction
Sensitive fields are redacted before trace storage, including fields such as:
```text
password
token
api_key
authorization
secret
credential
```
Cost estimation
The tracing layer supports cost estimation from:
input tokens
output tokens
input cost per 1K tokens
output cost per 1K tokens
The current local Ollama setup does not incur an external API charge; the estimator is included so a production implementation can connect model usage to pricing later.
---
Retry and Timeout Handling
The orchestrator supports configurable retries.
Current configuration:
```text
max_retries = 2
tool_timeout_seconds = 10
```
Tool execution can produce trace events such as:
```text
tool_attempt
tool_retry
tool_failed
tool_executed
```
The current timeout implementation measures execution duration against the configured threshold. A production implementation could add hard cancellation or asynchronous timeout enforcement.
---
Versioning and Rollback
Version information is maintained in:
```text
app/version.py
```
The project tracks:
application version
agent versions
tool versions
prompt versions
Current baseline:
```text
Application: 1.0.0

Agents:
  planner       1.0.0
  investigator  1.0.0
  ops           1.0.0
  verifier      1.0.0

Tools:
  get_logs               1.0.0
  get_metrics            1.0.0
  simulate_restart       1.0.0
  simulate_scale         1.0.0
  get_dependency_graph   1.0.0
```
Rollback guidance is documented in:
```text
docs/ROLLBACK.md
```
The intended rollback process is:
```text
Identify failure
      ↓
Review trace
      ↓
Identify validated version
      ↓
Restore version
      ↓
Run tests
      ↓
Run safety evaluations
      ↓
Validate workflow
      ↓
Promote restored version
```
---
Evaluation and Testing
Automated tests are divided into:
```text
tests/
evaluations/
```
The project currently has:
7 automated project tests
3 safety evaluations
10 passing checks in the validated local run
Safety evaluations cover:
Environment safety
An action targeting an unsupported/non-production environment is rejected.
Restricted infrastructure
A direct restart of `payment-db` is rejected because manual approval is required.
Bounded remediation
`payment-service` restart is allowed when dependency health and blast-radius conditions are satisfied.
Run:
```powershell
python -m pytest -q tests
python -m pytest -q evaluations
```
Or run everything together:
```powershell
python -m pytest -q tests evaluations
```
---
CI
GitHub Actions is configured in:
```text
.github/workflows/tests.yml
```
CI runs on:
push
pull request
The pipeline:
Checks out the repository.
Sets up Python 3.11.
Installs dependencies.
Runs project tests.
Runs safety evaluations.
Commands used by CI:
```text
pytest -q tests
pytest -q evaluations
```
---
Project Structure
```text
mini-agentic-ai/
│
├── app/
│   ├── agents/
│   │   ├── planner.py
│   │   ├── investigator.py
│   │   ├── ops.py
│   │   └── verifier.py
│   │
│   ├── models/
│   │   ├── incident.py
│   │   └── messages.py
│   │
│   ├── orchestration/
│   │   ├── state.py
│   │   ├── graph.py
│   │   └── persistence.py
│   │
│   ├── rag/
│   │   ├── documents.py
│   │   ├── bm25_search.py
│   │   ├── semantic_search.py
│   │   ├── hybrid_search.py
│   │   └── knowledge_graph.py
│   │
│   ├── safety/
│   │   ├── policies.py
│   │   └── blast_radius.py
│   │
│   ├── tools/
│   │   ├── schemas.py
│   │   ├── server.py
│   │   ├── logs.py
│   │   ├── metrics.py
│   │   ├── restart.py
│   │   ├── scale.py
│   │   └── dependencies.py
│   │
│   ├── tracing/
│   │   └── tracer.py
│   │
│   ├── config.py
│   └── version.py
│
├── data/
│   ├── infrastructure/
│   ├── logs/
│   ├── metrics/
│   └── runbooks/
│
├── docs/
│   ├── ROLLBACK.md
│   └── TRADEOFFS.md
│
├── evaluations/
├── tests/
├── traces/
│
├── .github/workflows/tests.yml
├── demo.py
├── main.py
├── requirements.txt
├── .env.example
└── README.md
```
---
Configuration
Configuration is managed through environment variables.
Example:
```env
APP_ENV=local
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2:3b
OLLAMA_URL=http://localhost:11434
```
Safety/runtime configuration:
```text
max_blast_radius = 2
max_retries = 2
tool_timeout_seconds = 10
```
Local secrets and environment-specific configuration are excluded from Git through `.gitignore`.
---
Getting Started
1. Clone the repository
```powershell
git clone https://github.com/sunanda2601/mini-agentic-ai.git
cd mini-agentic-ai
```
2. Create a virtual environment
```powershell
python -m venv .venv
```
Activate it on Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
```
3. Install dependencies
```powershell
pip install -r requirements.txt
```
4. Configure Ollama
Make sure Ollama is running locally and the configured model is available:
```text
llama3.2:3b
```
The default Ollama endpoint is:
```text
http://localhost:11434
```
5. Verify configuration
```powershell
python main.py
```
6. Run tests
```powershell
python -m pytest -q tests
```
7. Run safety evaluations
```powershell
python -m pytest -q evaluations
```
8. Run the end-to-end demo
```powershell
python demo.py
```
The demo displays:
workflow status
safety decision
proposed action
simulated execution result
audit trace
replay verification
---
Demonstration Scenario
The included demonstration uses a simulated high-severity incident involving:
```text
Service:     payment-service
Environment: production
Severity:    high
```
The incident contains symptoms such as:
database connection timeouts
payment request failures
elevated error rate
increased latency
The Investigator examines:
```text
payment-service logs
payment-service metrics
payment-db metrics
payment-service runbook
service dependency graph
```
The Ops agent proposes:
```text
simulate_restart(payment-service)
```
The Verifier checks:
```text
Environment
Policy
Dependency health
Blast radius
```
If the safety conditions are satisfied, the simulated restart is approved.
Expected final state:
```text
Status:   COMPLETED
Approved: True
```
The resulting trace can then be inspected and replayed.
---
Architecture Trade-offs
The prototype intentionally uses simple components suitable for a short hands-on exercise.
Decision	Why it was chosen	Production alternative
Local Ollama	Local execution and no external API dependency	Managed/model-serving platform
Hybrid retrieval	Combines exact and semantic matching	Larger retrieval/reranking stack
NetworkX	Lightweight dependency graph	Distributed graph database/service
Simulated infrastructure	Safe demonstration and testing	Controlled cloud/Kubernetes adapters
Deterministic safety	Predictable and auditable decisions	LLM reasoning can assist, but policy remains the final gate
File-based state	Simple local persistence	Durable workflow engine/distributed state store
More detail is available in:
```text
docs/TRADEOFFS.md
```
---
Current Scope and Limitations
This is a production-oriented prototype, not a production deployment.
Implemented
Four-agent architecture
Structured A2A messages
Explicit workflow states
Persistent workflow state
Trace replay
Structured infrastructure tools
Versioned tool contracts
Tenant/environment context
Hybrid BM25 + semantic retrieval
Runbook citations
Service dependency graph
Dependency health checks
Deterministic safety policies
Blast-radius checks
Simulated remediation
Retry handling
Timeout measurement
Redacted audit tracing
Cost estimation support
Agent/tool/prompt versioning
Safety evaluations
Automated tests
GitHub Actions CI
Rollback documentation
Architecture trade-off documentation
Current limitations
Infrastructure actions are simulated.
Workflow state uses local JSON files.
NetworkX is used instead of a distributed graph database.
Ollama is configured for local model serving.
Cost tracking is an estimation mechanism rather than production billing integration.
Tenant scoping is represented in tool contracts rather than distributed tenant-isolated infrastructure.
The tool layer is MCP-style rather than a full MCP protocol server.
Timeout handling measures the threshold rather than forcibly cancelling a running operation.
Trace replay verifies recorded trace data rather than re-executing the entire workflow.
These limitations are deliberate prototype trade-offs and provide clear paths for production hardening.
---
Design Principles
The implementation prioritizes:
Safety
Potential infrastructure actions must pass deterministic safety checks before execution.
Auditability
Important decisions, tool calls, transitions and execution results are recorded.
Determinism
Safety-critical decisions are deterministic wherever practical.
Testability
Tools, persistence, graph behavior and safety invariants are covered by automated tests.
Structured Communication
Agents exchange structured messages rather than uncontrolled conversational text.
Evidence-Based Investigation
Remediation is proposed only after collecting operational evidence.
Explicit Orchestration
Workflow states and transitions are explicit.
Controlled Execution
Infrastructure access is exposed through explicit tool contracts and remains simulated in this prototype.
---
Why This Architecture?
The architecture separates four concerns that should not be controlled by one LLM response:
```text
Reasoning
   +
Evidence Retrieval
   +
Safety Policy
   +
Execution
```
The agents provide flexible reasoning and investigation, while deterministic orchestration and safety checks provide control over execution.
This separation makes the system easier to:
test
audit
debug
replay
evaluate
version
extend toward production
---
Future Production Evolution
A production deployment could evolve the prototype by:
Replacing simulated tools with controlled infrastructure adapters.
Moving workflow state to a durable distributed workflow engine.
Introducing distributed tenant isolation.
Replacing NetworkX with a scalable graph service when graph size requires it.
Using production-grade model serving instead of local Ollama.
Adding stronger timeout/cancellation semantics.
Expanding evaluation coverage and regression datasets.
Introducing a centralized tool registry/protocol layer where required.
The safety boundary should remain:
```text
Agent proposal
      ↓
Deterministic policy + validation
      ↓
Approved tool execution
```
---
Conclusion
The Mini Agentic AI Platform demonstrates a controlled agentic workflow for incident analysis and remediation.
It combines:
```text
Specialized Agents
        +
Structured A2A Communication
        +
Explicit Orchestration
        +
Hybrid RAG
        +
Knowledge Graph
        +
MCP-Style Tool Contracts
        +
Deterministic Safety Verification
        +
Blast-Radius Analysis
        +
Persistence
        +
Observability
        +
Evaluation
        +
CI/CD
```
The key architectural principle is simple:
> **Agents investigate and propose. The safety layer validates. The orchestrator controls execution.**
This provides a clear, auditable path from an incident to a controlled remediation decision without allowing an LLM response to directly perform infrastructure operations.
