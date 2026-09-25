# Mini Agentic AI Platform

A production-oriented prototype for AI-assisted production incident analysis and safe remediation.

The platform uses four specialized agents to investigate an incident, collect evidence, propose a remediation, and pass that proposal through deterministic safety checks before a simulated infrastructure action can run.

> **Core principle:** agents can propose actions, but deterministic safety controls decide whether an action is allowed to execute.

## Overview

Given an operational incident, the platform:

1. Creates an investigation plan.
2. Collects logs and metrics.
3. Retrieves relevant runbooks using hybrid lexical and semantic search.
4. Traverses service dependencies using a knowledge graph.
5. Proposes a remediation action.
6. Validates the proposal with deterministic safety policies.
7. Checks dependency health and blast radius.
8. Requests human approval when required.
9. Executes an approved simulated infrastructure action.
10. Persists workflow state.
11. Records an auditable trace and supports trace replay.
12. Exposes the workflow through a small FastAPI API.

The prototype is intentionally designed for controlled demonstration and evaluation. It does not modify real production infrastructure.

## Architecture

```text
                           Incident
                              |
                              v
                       +--------------+
                       |    Planner   |
                       +------+-------+
                              |
                    investigation_request
                              |
                              v
                 +---------------------------+
                 |   Investigator / RAG       |
                 +-------------+-------------+
                               |
                +--------------+--------------+
                |              |              |
                v              v              v
              Logs          Metrics       Hybrid RAG
                                             |
                                          Runbooks
                                             |
                                             v
                                      Knowledge Graph
                                             |
                                             v
                                      Dependency Health
                                             |
                                             v
                                      +--------------+
                                      |     Ops      |
                                      +------+-------+
                                             |
                                       action_proposal
                                             |
                                             v
                                  +-------------------+
                                  | Verifier / Safety |
                                  +---------+---------+
                                            |
                              +-------------+-------------+
                              |                           |
                           BLOCK                   REQUIRE_APPROVAL
                              |                           |
                              v                           v
                           FAILED                 Human approval
                                                          |
                                               +----------+----------+
                                               |                     |
                                            Reject                Approve
                                               |                     |
                                               v                     v
                                           REJECTED          Simulated Tool
                                                                     |
                                                                     v
                                                              Persisted State
                                                                     |
                                                                     v
                                                               Audit Trace
```

## Main Components

| Component | Responsibility |
|---|---|
| Planner Agent | Creates the investigation plan |
| Investigator / RAG Agent | Collects operational evidence |
| Infra / Ops Agent | Proposes remediation actions |
| Verifier / Safety Agent | Makes deterministic safety decisions |
| Orchestrator | Controls workflow states and transitions |
| RAG Layer | Retrieves operational documentation |
| Knowledge Graph | Represents service dependencies and ownership |
| Tool Layer | Provides structured infrastructure operations |
| Persistence | Stores workflow state as JSON |
| Tracing | Records execution, decisions, latency, and failures |
| Evaluations | Validates important safety invariants |
| FastAPI API | Provides health and workflow endpoints |

## Agent Workflow

The four agents communicate using structured `A2AMessage` objects rather than uncontrolled conversational text.

```text
Planner
   |
   | investigation_request
   v
Investigator
   |
   | investigation_result
   v
Ops
   |
   | action_proposal
   v
Verifier
   |
   +---- BLOCK ------------> workflow FAILED
   |
   +---- REQUIRE_APPROVAL -> human review
   |                              |
   |                    +---------+---------+
   |                    |                   |
   |                 Reject              Approve
   |                    |                   |
   |                    v                   v
   |                REJECTED        Simulated Tool
   |
   +---- ALLOW -------------------------> Simulated Tool
```

Each A2A message contains structured fields such as:

- `message_id`
- `sender`
- `receiver`
- `message_type`
- `timestamp`
- `payload`

This makes agent communication easier to validate, test, trace, and audit.

## Agents

### 1. Planner Agent

The Planner receives the incident and creates a structured investigation plan.

The plan can include:

- `get_logs`
- `get_metrics`
- runbook retrieval
- dependency graph checks

The Planner does not execute infrastructure actions.

### 2. Investigator / RAG Agent

The Investigator gathers the evidence needed to understand the incident.

It collects:

- service logs
- service metrics
- relevant runbooks
- dependencies
- dependent services
- dependency health
- service owner information
- runbook citations

It combines hybrid retrieval with knowledge-graph traversal.

### 3. Infra / Ops Agent

The Ops agent receives the investigation result and proposes a remediation.

For the included demonstration, the proposal is:

```text
simulate_restart(payment-service)
```

The proposal is not executed immediately. It must first pass the Verifier.

### 4. Verifier / Safety Agent

The Verifier is the final safety gate.

It checks:

- environment policy
- allowed tools
- service/action consistency
- restricted services
- dependency health
- blast radius
- action-specific safety rules
- approval requirements

If a safety condition fails, the workflow stops without executing the proposed action.

For example, a direct restart of `payment-db` requires manual approval in the prototype.

## Workflow State Machine

The orchestrator uses explicit workflow states:

```text
PLANNING
    |
    v
INVESTIGATING
    |
    v
ACTION_PROPOSED
    |
    v
VERIFYING
    |
    +----------> FAILED
    |
    +----------> WAITING_FOR_APPROVAL
                         |
                    +----+----+
                    |         |
                 REJECT     APPROVE
                    |         |
                    v         v
                REJECTED   APPROVED
                              |
                              v
                          COMPLETED

Any stoppable workflow
        |
        v
     STOPPED
```

The workflow state is persisted after important transitions so that control is not hidden entirely inside an agent response.

## Policy and Safety Model

The main design decision is the separation between reasoning and execution.

```text
Agent Proposal
      |
      v
Deterministic Verification
      |
      +-- Environment
      +-- Tool allowlist
      +-- Policy rules
      +-- Dependency health
      +-- Blast radius
      +-- Manual approval rules
      |
      +-- BLOCK -------------> FAILED
      |
      +-- REQUIRE_APPROVAL --> Human review
      |
      +-- ALLOW -------------> Simulated Tool
```

The policy engine uses explicit decisions:

- `ALLOW`
- `REQUIRE_APPROVAL`
- `BLOCK`

The verifier combines policy results with dependency and blast-radius checks.

## Human Approval

Certain sensitive actions can require human approval.

The approval workflow records:

- approval status
- approving actor
- policy IDs
- policy reasons
- proposed action
- rejection reason when applicable
- audit event

Supported approval outcomes include:

```text
WAITING_FOR_APPROVAL
        |
   +----+----+
   |         |
APPROVE    REJECT
   |         |
   v         v
APPROVED  REJECTED
```

## Workflow Stop / Kill Mechanism

The orchestrator supports stopping a workflow before approved action execution.

A stopped workflow:

- receives `STOPPED` status
- records the operator
- records the stop reason
- persists the state
- emits a `workflow_stopped` audit event

The action execution helper also contains a guard that prevents a stopped workflow from executing its action.

## Blast Radius

The current configuration uses:

```text
max_blast_radius = 2
```

The blast-radius calculator considers the target service and its direct dependent services.

Before approving the demonstration restart of `payment-service`, the Verifier checks the health of its dependency `payment-db`.

## Hybrid RAG

The Investigator uses two retrieval approaches.

### BM25

BM25 provides lexical retrieval and is useful for exact operational terms such as:

- service names
- error messages
- technical keywords

### Semantic Search

Semantic retrieval uses:

```text
sentence-transformers
all-MiniLM-L6-v2
```

This helps retrieve conceptually related evidence even when wording differs.

### Retrieval Flow

```text
Incident description
       |
       +-------------> BM25
       |
       +-------------> Semantic Search
                              |
                              v
                         Score Fusion
                              |
                              v
                          Top Results
                              |
                              v
                        Runbook Citations
```

Retrieval supports metadata filtering, including service-level filtering.

## Knowledge Graph

The prototype uses NetworkX for service dependency relationships.

Example:

```text
checkout-service
       |
       v
payment-service
       |
       +----> payment-db
       |
       +----> user-service
```

The graph supports:

- `get_dependencies(service)`
- `get_dependents(service)`
- `get_owner(service)`
- `get_runbooks(service)`

The Investigator uses the graph to understand incident context.

The Verifier uses dependency information for safety validation and blast-radius analysis.

## MCP-Style Tool Layer

The project implements a local MCP-style, schema-first tool layer.

It is not a full external MCP protocol server. The prototype focuses on the tool-contract concepts required by the exercise.

### Available Tools

| Tool | Purpose |
|---|---|
| `get_logs` | Retrieve service logs |
| `get_metrics` | Retrieve service metrics |
| `simulate_restart` | Simulate a service restart |
| `simulate_scale` | Simulate a replica change |
| `get_dependency_graph` | Retrieve service dependency information |

### Tool Contracts

Tools use:

- Pydantic request schemas
- Pydantic response schemas
- versioned contracts
- tenant identifiers
- environment identifiers
- explicit success/failure fields
- structured error codes

Current tool contract version:

```text
1.0.0
```

Example structured errors include:

```text
UNSUPPORTED_ENVIRONMENT
SERVICE_NOT_FOUND
SERVICE_LOG_NOT_FOUND
SERVICE_METRICS_NOT_FOUND
INFRASTRUCTURE_DATA_NOT_FOUND
INVALID_REPLICA_COUNT
```

### Tenant and Environment Context

The demonstration uses:

```text
tenant_id = demo-tenant
environment = production
```

Tenant and environment are carried through tool contracts.

The current prototype represents tenant scoping at the contract level rather than providing distributed infrastructure isolation.

## Simulated Infrastructure

Infrastructure operations are deliberately simulated.

The prototype does not modify:

- Kubernetes clusters
- cloud infrastructure
- production databases
- production services
- real replicas

Supported simulated operations include:

```text
simulate_restart
simulate_scale
```

This allows the complete agentic workflow to be demonstrated without introducing real infrastructure risk.

## Persistence and Replay

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

- state inspection
- debugging
- process-level durability
- auditability
- replay support

The prototype uses file-based persistence because it is simple and appropriate for a small local system.

The current replay mechanism replays recorded trace data for verification. It is not a full re-execution of every workflow step.

## Observability and Audit Trace

The tracing layer records important workflow events.

Example events include:

```text
workflow_started
cost_estimate
agent_completed
decision_made
approval_required
approval_granted
approval_rejected
workflow_stopped
action_execution_prevented
tool_attempt
tool_retry
tool_failed
tool_executed
```

Trace records can include:

- unique `audit_id`
- timestamp
- event type
- component
- details
- latency

### Sensitive-Data Redaction

Sensitive fields are redacted before trace storage, including:

```text
password
token
api_key
authorization
secret
credential
```

### Cost Estimation

The tracing layer supports cost estimation from:

- input tokens
- output tokens
- input cost per 1K tokens
- output cost per 1K tokens

The local Ollama setup does not incur an external API charge. The estimator is included so a production implementation can connect model usage to pricing later.

## Retry and Timeout Handling

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

## Versioning and Rollback

Version information is maintained in:

```text
app/version.py
```

The project tracks:

- application version
- agent versions
- tool versions
- prompt versions

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
  simulate_restart      1.0.0
  simulate_scale        1.0.0
  get_dependency_graph  1.0.0
```

Rollback guidance is documented in:

```text
docs/ROLLBACK.md
```

The intended rollback process is:

```text
Identify failure
      |
Review trace
      |
Identify validated version
      |
Restore version
      |
Run tests
      |
Run safety evaluations
      |
Validate workflow
      |
Promote restored version
```

## Evaluation and Testing

Automated tests are divided into:

```text
tests/
evaluations/
```

The local validation suite currently includes unit/integration tests and safety invariant evaluations.

The safety evaluations cover:

- cross-environment action rejection
- unsafe restricted infrastructure action rejection
- bounded remediation acceptance

Run project tests:

```powershell
python -m pytest -q tests
```

Run safety evaluations:

```powershell
python -m pytest -q evaluations
```

Run everything:

```powershell
python -m pytest -q
```

The current validated local run passes:

```text
16 passed
```

## CI/CD

GitHub Actions is configured in:

```text
.github/workflows/tests.yml
```

CI runs on push and pull request.

The pipeline:

1. Checks out the repository.
2. Sets up Python.
3. Installs dependencies.
4. Runs project tests.
5. Runs safety evaluations.

The repository also maintains version information and rollback guidance.

## FastAPI API

A lightweight FastAPI layer is provided in:

```text
app/api.py
```

### Health Check

Start the API:

```powershell
uvicorn app.api:app --reload
```

Then check:

```text
GET /health
```

Expected response:

```json
{
  "status": "ok",
  "service": "mini-agentic-ai"
}
```

### Workflow Endpoints

The API exposes endpoints for:

```text
POST /incidents
POST /incidents/{workflow_id}/approve
POST /incidents/{workflow_id}/reject
POST /incidents/{workflow_id}/stop
```

The API provides a simple service boundary around the existing workflow orchestration.

## Project Structure

```text
mini-agentic-ai/
|
+-- app/
|   +-- agents/
|   |   +-- planner.py
|   |   +-- investigator.py
|   |   +-- ops.py
|   |   +-- verifier.py
|   |
|   +-- models/
|   |   +-- incident.py
|   |   +-- messages.py
|   |
|   +-- orchestration/
|   |   +-- state.py
|   |   +-- graph.py
|   |   +-- persistence.py
|   |
|   +-- rag/
|   |   +-- documents.py
|   |   +-- bm25_search.py
|   |   +-- semantic_search.py
|   |   +-- hybrid_search.py
|   |   +-- knowledge_graph.py
|   |
|   +-- safety/
|   |   +-- policies.py
|   |   +-- blast_radius.py
|   |
|   +-- tools/
|   |   +-- schemas.py
|   |   +-- server.py
|   |   +-- logs.py
|   |   +-- metrics.py
|   |   +-- restart.py
|   |   +-- scale.py
|   |   +-- dependencies.py
|   |
|   +-- tracing/
|   |   +-- tracer.py
|   |
|   +-- api.py
|   +-- config.py
|   +-- version.py
|
+-- data/
|   +-- infrastructure/
|   +-- logs/
|   +-- metrics/
|   +-- runbooks/
|
+-- docs/
|   +-- ROLLBACK.md
|   +-- TRADEOFFS.md
|
+-- evaluations/
+-- tests/
+-- traces/
|
+-- .github/
|   +-- workflows/
|       +-- tests.yml
|
+-- demo.py
+-- main.py
+-- requirements.txt
+-- .env.example
+-- README.md
```

## Configuration

Configuration is managed through environment variables.

Example:

```text
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

## Getting Started

### 1. Clone the repository

```powershell
git clone https://github.com/sunanda2601/mini-agentic-ai.git
cd mini-agentic-ai
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Configure Ollama

Make sure Ollama is running locally and the configured model is available:

```text
llama3.2:3b
```

Default Ollama endpoint:

```text
http://localhost:11434
```

### 5. Verify configuration

```powershell
python main.py
```

### 6. Run tests

```powershell
python -m pytest -q
```

### 7. Run safety evaluations

```powershell
python -m pytest -q evaluations
```

### 8. Run the end-to-end demo

```powershell
python demo.py
```

The demo displays:

- workflow status
- safety decision
- proposed action
- simulated execution result
- audit trace
- replay verification

### 9. Run the API

```powershell
uvicorn app.api:app --reload
```

Open the FastAPI documentation at:

```text
http://127.0.0.1:8000/docs
```

## Demonstration Scenario

The included demonstration uses a simulated high-severity incident involving:

```text
Service:     payment-service
Environment: production
Severity:    high
```

The incident contains symptoms such as:

- database connection timeouts
- payment request failures
- elevated error rate
- increased latency

The Investigator examines:

- `payment-service` logs
- `payment-service` metrics
- `payment-db` metrics
- `payment-service` runbook
- service dependency graph

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

## Architecture Trade-offs

The prototype intentionally uses simple components suitable for a short hands-on exercise.

| Decision | Why it was chosen | Production alternative |
|---|---|---|
| Local Ollama | Local execution with no external API dependency | Managed/model-serving platform |
| Hybrid retrieval | Combines exact and semantic matching | Larger retrieval/reranking stack |
| NetworkX | Lightweight dependency graph | Distributed graph database/service |
| Simulated infrastructure | Safe demonstration and testing | Controlled cloud/Kubernetes adapters |
| Deterministic safety | Predictable and auditable decisions | Deterministic policy layer plus richer model reasoning |
| File-based state | Simple local persistence | Durable workflow engine/distributed state store |

More detail is available in:

```text
docs/TRADEOFFS.md
```

## Current Scope and Limitations

This is a production-oriented prototype, not a production deployment.

### Implemented

- Four-agent architecture
- Structured A2A messages
- Explicit workflow states
- Persistent workflow state
- Trace replay
- Structured infrastructure tools
- Versioned tool contracts
- Tenant/environment context
- Hybrid BM25 + semantic retrieval
- Runbook citations
- Service dependency graph
- Dependency health checks
- Deterministic safety policies
- Blast-radius checks
- Human approval/rejection
- Workflow stop mechanism
- Simulated remediation
- Retry handling
- Timeout measurement
- Redacted audit tracing
- Unique audit IDs
- Cost estimation support
- Agent/tool/prompt versioning
- Safety evaluations
- Automated tests
- GitHub Actions CI
- FastAPI API
- Rollback documentation
- Architecture trade-off documentation

### Current Limitations

- Infrastructure actions are simulated.
- Workflow state uses local JSON files.
- NetworkX is used instead of a distributed graph database.
- Ollama is configured for local model serving.
- Cost tracking is an estimation mechanism rather than production billing integration.
- Tenant scoping is represented in tool contracts rather than distributed tenant-isolated infrastructure.
- The tool layer is MCP-style rather than a full MCP protocol server.
- Timeout handling measures the threshold rather than forcibly cancelling a running operation.
- Trace replay verifies recorded trace data rather than re-executing the entire workflow.

These limitations are deliberate prototype trade-offs and provide clear paths for production hardening.

## Design Principles

The implementation prioritizes:

### Safety

Potential infrastructure actions must pass deterministic safety checks before execution.

### Auditability

Important decisions, tool calls, transitions, approvals, and execution results are recorded.

### Determinism

Safety-critical decisions are deterministic wherever practical.

### Testability

Tools, persistence, graph behavior, workflow behavior, and safety invariants are covered by automated tests.

### Structured Communication

Agents exchange structured messages rather than uncontrolled conversational text.

### Evidence-Based Investigation

Remediation is proposed only after collecting operational evidence.

### Explicit Orchestration

Workflow states and transitions are explicit.

### Controlled Execution

Infrastructure access is exposed through explicit tool contracts and remains simulated in this prototype.

## Why This Architecture?

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

Agents provide flexible reasoning and investigation, while deterministic orchestration and safety checks provide control over execution.

This separation makes the system easier to:

- test
- audit
- debug
- replay
- evaluate
- version
- extend toward production

## Future Production Evolution

A production deployment could evolve the prototype by:

- replacing simulated tools with controlled infrastructure adapters
- moving workflow state to a durable distributed workflow engine
- introducing distributed tenant isolation
- replacing NetworkX with a scalable graph service when graph size requires it
- using production-grade model serving instead of local Ollama
- adding stronger timeout/cancellation semantics
- expanding evaluation coverage and regression datasets
- introducing a centralized tool registry/protocol layer where required
- adding stronger authentication and authorization around the API

The safety boundary should remain:

```text
Agent proposal
      |
      v
Deterministic policy + validation
      |
      v
Approved tool execution
```

## Conclusion

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
Human Approval
        +
Workflow Stop Controls
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
        +
FastAPI API
```

The key architectural principle is simple:

> **Agents investigate and propose. The safety layer validates. The orchestrator controls execution.**

This provides a clear, auditable path from an incident to a controlled remediation decision without allowing an agent response to directly perform infrastructure operations.
