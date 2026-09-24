# Mini Agentic AI Platform



A production-oriented prototype for incident analysis and safe remediation using multiple cooperating agents, structured A2A messages, hybrid retrieval, infrastructure tools, deterministic safety verification, workflow orchestration, persistence, and audit tracing.



---



## 1. Problem



The platform receives an operational incident involving a service and analyzes:



\- Logs

\- Metrics

\- Runbooks

\- Infrastructure metadata

\- Service dependencies



It then:



1\. Plans an investigation.

2\. Retrieves operational evidence.

3\. Checks service dependencies and dependency health.

4\. Proposes a remediation action.

5\. Verifies safety and blast radius.

6\. Executes a simulated infrastructure action.

7\. Persists workflow state.

8\. Produces an auditable trace.

9\. Supports replay of the recorded workflow.



The prototype is designed around safety, correctness, auditability, and controlled agentic execution rather than a simple chatbot interaction.



---



## 2. Architecture



The platform contains four mandatory agents:



1\. Planner Agent

2\. Investigator / RAG Agent

3\. Infra / Ops Agent

4\. Verifier / Safety Agent



Agents communicate using structured A2A messages rather than free-form conversational text.



### High-Level Workflow



```text

Incident

&#x20;  |

&#x20;  v

Planner Agent

&#x20;  |

&#x20;  v

Investigator / RAG Agent

&#x20;  |

&#x20;  +--> Logs

&#x20;  +--> Metrics

&#x20;  +--> Runbooks

&#x20;  +--> Dependency Graph

&#x20;  |

&#x20;  v

Infra / Ops Agent

&#x20;  |

&#x20;  v

Verifier / Safety Agent

&#x20;  |

&#x20;  +--> Policy Checks

&#x20;  +--> Dependency Health

&#x20;  +--> Blast Radius

&#x20;  |

&#x20;  v

Simulated Infrastructure Action

&#x20;  |

&#x20;  v

Persisted Workflow State

&#x20;  |

&#x20;  v

Audit Trace / Replay







Architectural Principles



The architecture separates:



Agent reasoning

Infrastructure tools

Retrieval

Safety verification

Workflow orchestration

Persistence

Observability

Evaluation



Agents do not directly access infrastructure SDKs.



3\. Agents

Planner Agent



The Planner Agent receives the incident and creates a structured investigation plan.



The plan identifies the investigation activities required before remediation is proposed.



Current investigation steps include:



get\_logs

get\_metrics

retrieve\_runbook

check\_dependency\_graph



The Planner sends an investigation\_request A2A message to the Investigator.



Investigator / RAG Agent



The Investigator gathers evidence required to understand the incident.



It collects:



Service logs

Service metrics

Relevant runbooks

Service dependencies

Dependent services

Dependency health

Service owner information

Runbook citations



The Investigator uses hybrid retrieval combining lexical and semantic search.



Infra / Ops Agent



The Infra / Ops Agent receives the investigation result and proposes an infrastructure remediation action.



For the demonstration incident, it proposes:



simulate\_restart(payment-service)



The proposed action is still subject to verification.



The Ops Agent does not directly bypass the safety layer.



Verifier / Safety Agent



The Verifier is the final decision gate before an infrastructure action is executed.



It evaluates:



Environment policy

Allowed infrastructure tools

Restricted services

Dependency health

Blast radius

Action-specific safety rules



Only an approved action can proceed to simulated execution.



4\. A2A Messages



Agents communicate using the A2AMessage Pydantic model.



Each message contains:



message\_id

sender

receiver

message\_type

timestamp

payload



Example message flow:



Planner

&#x20;  |

&#x20;  | investigation\_request

&#x20;  v

Investigator

&#x20;  |

&#x20;  | investigation\_result

&#x20;  v

Ops

&#x20;  |

&#x20;  | action\_proposal

&#x20;  v

Verifier



The payload is structured data rather than free-form agent conversation.



This makes the workflow easier to validate, test, trace, and replay.



5\. Workflow Orchestration



The workflow is implemented as an explicit state machine.



The major workflow states are:



PLANNING

&#x20;   |

&#x20;   v

INVESTIGATING

&#x20;   |

&#x20;   v

ACTION\_PROPOSED

&#x20;   |

&#x20;   v

VERIFYING

&#x20;   |

&#x20;   v

APPROVED

&#x20;   |

&#x20;   v

COMPLETED



Unsafe or failed workflows transition to:



FAILED

Workflow Behavior



The orchestrator:



Creates the initial workflow state.

Runs the Planner.

Persists the planning state.

Runs the Investigator.

Persists the investigation state.

Runs the Ops Agent.

Persists the proposed action.

Runs the Verifier.

Persists the verification result.

Executes the approved simulated tool.

Persists the action result.

Records the final workflow state.



The orchestration layer also provides retry handling and tool execution timing.



6\. Persistence and Replay



Workflow state is persisted as JSON files under:



traces/



The persistence layer is implemented through:



WorkflowStateStore



It provides:



save(workflow\_id, state)

load(workflow\_id)

Why Persistence Is Used



Persistence allows the prototype to:



Survive the current process.

Inspect workflow state during development.

Support debugging.

Support replay.

Preserve state transitions for auditability.



The current implementation uses file-based persistence because this is a small prototype.



A distributed production system could use a durable workflow engine or database-backed state store.



7\. MCP-Style Infrastructure Tools



The platform exposes infrastructure operations through structured tool contracts.



Available tools:



get\_logs(service, timeframe)

get\_metrics(service)

simulate\_restart(service)

simulate\_scale(service, replicas)

get\_dependency\_graph(service)

Tool Design



Tools use:



Pydantic request schemas

Pydantic response schemas

Versioned contracts

Tenant identifiers

Environment identifiers

Structured errors

Explicit success/failure fields



Agents interact with the tool layer rather than accessing raw infrastructure SDKs.



Tenant and Environment Scoping



The default demonstration context is:



tenant\_id = demo-tenant

environment = production



The tool contracts require tenant and environment context.



This establishes the boundary needed for future multi-tenant isolation.



Tool Version



Current tool contract version:



1.0.0

Structured Errors



The tools return structured errors for expected failures, including cases such as:



UNSUPPORTED\_ENVIRONMENT

SERVICE\_NOT\_FOUND

SERVICE\_LOG\_NOT\_FOUND

SERVICE\_METRICS\_NOT\_FOUND

INFRASTRUCTURE\_DATA\_NOT\_FOUND

INVALID\_REPLICA\_COUNT

8\. Simulated Infrastructure



Infrastructure actions are simulated.



The prototype does not modify:



Kubernetes clusters

Cloud infrastructure

Production databases

Production services

Real replicas



Available simulated actions include:



simulate\_restart

simulate\_scale



For the demonstration incident, the approved action is:



simulate\_restart(payment-service)



The tool returns a structured simulated execution result.



This allows the complete agentic workflow to be demonstrated without introducing real infrastructure risk.



9\. Hybrid RAG



The Investigator uses a hybrid retrieval pipeline.



BM25 Retrieval



BM25 provides lexical retrieval based on matching terms.



It is useful when the incident description contains terminology that directly appears in operational documentation.



Semantic Retrieval



Semantic retrieval uses:



sentence-transformers

all-MiniLM-L6-v2



This allows conceptually similar evidence to be retrieved even when exact words differ.



Hybrid Retrieval



The final search combines:



BM25 score

\+

Semantic similarity score



The result includes runbook citation information.



Example:



runbook:payment-service-high-errors

Metadata Filtering



Retrieval can filter evidence using metadata such as:



service



This prevents unrelated runbooks from being selected for a service-specific investigation.



10\. Knowledge Graph



The prototype uses NetworkX for a lightweight service dependency graph.



The graph represents relationships such as:



checkout-service

&#x20;       |

&#x20;       | depends\_on

&#x20;       v

payment-service

&#x20;       |

&#x20;       +------> payment-db

&#x20;       |

&#x20;       +------> user-service



Runbook relationships are also represented:



payment-service

&#x20;       |

&#x20;       | has\_runbook

&#x20;       v

payment-service-high-errors

Supported Graph Operations



The knowledge graph supports:



get\_dependencies(service)

get\_dependents(service)

get\_owner(service)

get\_runbooks(service)



The graph is used by the Investigator and Verifier.



It helps determine dependency health and potential blast radius.



11\. Safety and Blast Radius



Safety verification is deterministic wherever practical.



Policy Checks



The policy layer checks:



Environment

Allowed tools

Restricted services

Manual approval requirements



Allowed simulated tools are:



simulate\_restart

simulate\_scale

Restricted Service Example



Direct restart of:



payment-db



is rejected because the runbook requires manual approval.



Dependency Health



Before restarting payment-service, the Verifier checks the health of its dependency:



payment-db



The simulated payment database is healthy.



Blast Radius



The blast-radius calculator considers:



Target service

Dependent services

Configured maximum blast radius



Current maximum:



max\_blast\_radius = 2



For payment-service, the affected services are within the configured boundary.



12\. Observability and Audit Trace



The platform contains a tracing layer that records the workflow execution.



Trace events include:



workflow\_started

cost\_estimate

agent\_completed

decision\_made

tool\_attempt

tool\_retry

tool\_failed

tool\_executed



Each trace event can contain:



Timestamp

Event type

Component

Details

Latency

Sensitive Data Redaction



Sensitive fields such as:



password

token

api\_key

authorization

secret

credential



are redacted before trace storage.



Trace Example

workflow\_started | orchestrator

cost\_estimate    | orchestrator

agent\_completed  | planner

agent\_completed  | investigator

agent\_completed  | ops

decision\_made    | verifier

tool\_attempt     | orchestrator

tool\_executed    | orchestrator

13\. Cost Tracking



The tracing layer supports cost estimation.



The cost estimator accepts:



input\_tokens

output\_tokens

input\_cost\_per\_1k

output\_cost\_per\_1k



The current prototype uses local Ollama inference, so the demonstration does not incur an external API charge.



The trace records a cost-estimate event so that a production implementation could later connect actual model usage and pricing information.



14\. Retry and Timeout Handling



The orchestration layer supports configurable retry behavior.



Current configuration:



max\_retries = 2

tool\_timeout\_seconds = 10



The orchestrator records:



tool\_attempt

tool\_retry

tool\_failed

tool\_executed

Retry Behavior



A failed tool execution can be retried up to the configured retry limit.



Timeout Behavior



The current prototype measures tool execution duration against the configured timeout threshold.



If execution exceeds the configured threshold, the workflow records the failure.



A production implementation could replace this with hard cancellation or asynchronous timeout enforcement.



15\. Versioning



Version information is maintained in:



app/version.py



The prototype tracks:



Application version

Agent versions

Tool versions

Prompt versions



Current baseline:



Application: 1.0.0



Agents:

&#x20; planner       1.0.0

&#x20; investigator  1.0.0

&#x20; ops           1.0.0

&#x20; verifier      1.0.0



Tools:

&#x20; get\_logs               1.0.0

&#x20; get\_metrics            1.0.0

&#x20; simulate\_restart       1.0.0

&#x20; simulate\_scale         1.0.0

&#x20; get\_dependency\_graph   1.0.0



Prompts:

&#x20; planner       1.0.0

&#x20; investigator  1.0.0

&#x20; ops           1.0.0

&#x20; verifier      1.0.0



Version tracking supports reproducibility and rollback.



16\. Evaluation



Safety evaluations are maintained under:



evaluations/



The current evaluation suite contains three safety invariant tests.



Evaluation 1 — Environment Safety



An action targeting a non-production environment is rejected.



Evaluation 2 — Restricted Infrastructure



Direct restart of payment-db is rejected because it requires manual approval.



Evaluation 3 — Blast Radius Boundary



Restarting payment-service is allowed when its dependency health and blast-radius conditions are satisfied.



Run:



pytest -q evaluations



Expected result:



3 passed



These evaluations provide an offline safety gate for the workflow.



17\. Testing



Automated tests are maintained under:



tests/



The test suite covers:



Infrastructure tool contracts

Tenant scoping

Environment scoping

Structured responses

Tool versioning

Knowledge graph behavior

Workflow persistence

Safety-related platform behavior



Run the complete test suite:



pytest -q



Expected current result:



10 passed



The test suite is intended to prevent regressions while the platform evolves.



18\. CI/CD



GitHub Actions is configured under:



.github/workflows/tests.yml



The workflow runs on:



push

pull\_request

CI Pipeline



The pipeline:



Checks out the repository.

Sets up Python 3.11.

Installs project dependencies.

Runs unit and contract tests.

Runs safety evaluations.



Commands executed by CI:



pytest -q tests

pytest -q evaluations



This provides an automated quality gate for changes.



19\. Rollback



Rollback guidance is documented in:



docs/ROLLBACK.md

Rollback Process

Identify the failing workflow or evaluation.

Review the workflow trace.

Identify application, agent, tool, and prompt versions.

Restore the last known-good version.

Run unit tests.

Run tool contract tests.

Run safety evaluations.

Validate the affected workflow.

Promote the restored version only after validation passes.

Rollback Principle



If a new version fails validation or introduces unsafe behavior, return to the last validated version.



20\. Architecture Trade-offs



The project intentionally uses simple components appropriate for a short prototype.



Local Ollama vs External LLM API



Choice: Local Ollama configuration.



Advantages:



No external API dependency during the prototype.

Local execution.

Easy experimentation.



Trade-off:



Hardware dependent.

Less suitable for distributed production serving.



Future Improvement:



Use a production model-serving platform when deploying at scale.



NetworkX vs Dedicated Graph Database



Choice: NetworkX.



Advantages:



Simple.

Lightweight.

Easy to inspect.

No additional infrastructure.



Trade-off:



Not designed for large distributed production graphs.



Future Improvement:



Use a graph database for large-scale dependency relationships.



Simulated Infrastructure vs Real Infrastructure



Choice: Simulated infrastructure tools.



Advantages:



Safe for demonstration.

No production risk.

Deterministic testing.



Trade-off:



Does not validate real cloud or Kubernetes behavior.



Future Improvement:



Introduce controlled infrastructure adapters behind the same tool contracts.



Deterministic Safety vs LLM-Based Safety



Choice: Deterministic safety checks.



Advantages:



Predictable.

Testable.

Auditable.

Easier to enforce invariants.



Trade-off:



Less flexible than fully model-driven reasoning.



Future Improvement:



Use LLM reasoning for suggestions while keeping deterministic policy enforcement as the final gate.



File-Based Workflow State vs Distributed Workflow State



Choice:



The prototype persists workflow state as JSON files under the traces/ directory.



Advantages:



Simple prototype architecture.

State survives the current process.

Easy to inspect during development.

Supports workflow replay and debugging.

No additional database infrastructure is required.



Trade-off:



File-based persistence is not suitable for concurrent distributed production workloads.



Future Improvement:



A production deployment could use a durable workflow engine or distributed database-backed state store.



21\. Project Structure

mini-agentic-ai/

│

├── app/

│   ├── \_\_init\_\_.py

│   ├── config.py

│   ├── version.py

│   │

│   ├── agents/

│   │   ├── \_\_init\_\_.py

│   │   ├── planner.py

│   │   ├── investigator.py

│   │   ├── ops.py

│   │   └── verifier.py

│   │

│   ├── models/

│   │   ├── \_\_init\_\_.py

│   │   ├── incident.py

│   │   └── messages.py

│   │

│   ├── orchestration/

│   │   ├── \_\_init\_\_.py

│   │   ├── state.py

│   │   ├── graph.py

│   │   └── persistence.py

│   │

│   ├── rag/

│   │   ├── \_\_init\_\_.py

│   │   ├── documents.py

│   │   ├── bm25\_search.py

│   │   ├── semantic\_search.py

│   │   ├── hybrid\_search.py

│   │   └── knowledge\_graph.py

│   │

│   ├── safety/

│   │   ├── \_\_init\_\_.py

│   │   ├── policies.py

│   │   └── blast\_radius.py

│   │

│   ├── tools/

│   │   ├── \_\_init\_\_.py

│   │   ├── schemas.py

│   │   ├── server.py

│   │   ├── logs.py

│   │   ├── metrics.py

│   │   ├── restart.py

│   │   ├── scale.py

│   │   └── dependencies.py

│   │

│   └── tracing/

│       ├── \_\_init\_\_.py

│       └── tracer.py

│

├── data/

│   ├── logs/

│   ├── metrics/

│   ├── runbooks/

│   └── infrastructure/

│

├── docs/

│   ├── ROLLBACK.md

│   └── TRADEOFFS.md

│

├── evaluations/

│

├── tests/

│

├── .github/

│   └── workflows/

│       └── tests.yml

│

├── demo.py

├── main.py

├── requirements.txt

├── .env.example

├── .gitignore

└── README.md

22\. Configuration



Configuration is managed through environment variables.



Example .env:



APP\_ENV=local

LLM\_PROVIDER=ollama

LLM\_MODEL=llama3.2:3b

OLLAMA\_URL=http://localhost:11434



The application configuration also includes:



max\_blast\_radius = 2

max\_retries = 2

tool\_timeout\_seconds = 10



Secrets and local environment configuration are excluded from Git through .gitignore.



23\. Running the Project

1\. Activate the Virtual Environment

.venv\\Scripts\\Activate.ps1

2\. Install Dependencies

pip install -r requirements.txt

3\. Verify the Application Configuration

python main.py



Expected output includes:



Mini Agentic AI Platform

Environment: local

LLM Provider: ollama

LLM Model: llama3.2:3b

Ollama URL: http://localhost:11434

4\. Run Tests

pytest -q

5\. Run Safety Evaluations

pytest -q evaluations

6\. Run the End-to-End Demo

python demo.py



The demo runs the incident workflow and displays:



Workflow status

Safety decision

Proposed action

Simulated action result

Audit trace

Replay verification



Expected final state:



Status: COMPLETED

Approved: True

24\. Current Prototype Scope



This project is a production-oriented prototype rather than a complete production deployment.



Implemented

Four-agent architecture

Structured A2A messages

Explicit workflow states

Persistent workflow state

Workflow replay

Five infrastructure tools

Versioned tool contracts

Tenant/environment tool context

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

Current Limitations

Infrastructure actions are simulated.

Workflow state uses local JSON files.

NetworkX is used instead of a distributed graph database.

Ollama is configured for local model serving.

Cost tracking is an estimation mechanism rather than a production billing integration.

Tenant scoping is represented in tool contracts rather than distributed tenant-isolated infrastructure.

The current prototype is intended for controlled demonstration and evaluation rather than direct production deployment.

25\. Design Principles



The implementation prioritizes:



Safety



Potential infrastructure actions must pass deterministic safety checks before execution.



Auditability



Important decisions, tool calls, workflow transitions, and execution results are recorded.



Determinism



Where safety decisions can be deterministic, the platform avoids relying solely on model output.



Testability



Tools, workflow persistence, graph behavior, and safety invariants are covered by automated tests.



Structured Communication



Agents exchange structured messages rather than uncontrolled conversational text.



Evidence-Based Investigation



The Investigator uses logs, metrics, runbooks, dependency data, and retrieval results before remediation is proposed.



Explicit Orchestration



Workflow states and transitions are explicit rather than hidden inside agent prompts.



Replayability



Persisted state and audit traces allow the workflow to be inspected and replayed.



Versioning



Agents, tools, prompts, and application versions are tracked to support reproducibility and rollback.



Controlled Execution



Infrastructure actions are exposed through explicit, versioned tool contracts and are simulated in the prototype.



Demo Scenario



The included demonstration uses a simulated payment-service incident.



The incident contains:



Database connection timeouts

Payment request failures

Elevated error rate

Increased latency



The Investigator checks:



payment-service logs

payment-service metrics

payment-db metrics

payment-service runbook

service dependency graph



The runbook indicates that when payment-db is healthy, restarting payment-service is an allowed remediation.



The Verifier then checks:



Environment

Policy

Dependency health

Blast radius



The action:



simulate\_restart(payment-service)



is approved and executed as a simulation.



The workflow ends with:



Status: COMPLETED

Approved: True



The trace can then be inspected and replayed.



Conclusion



This prototype demonstrates an agentic incident-response platform in which multiple specialized agents cooperate through structured messages and an explicit workflow.



The platform combines:



Agents

\+

A2A Communication

\+

Workflow Orchestration

\+

Hybrid RAG

\+

Knowledge Graph

\+

MCP-Style Tools

\+

Safety Verification

\+

Blast-Radius Analysis

\+

Persistence

\+

Observability

\+

Evaluation

\+

CI/CD



The design keeps infrastructure access controlled, makes safety decisions explicit, and provides an auditable execution path from incident intake to simulated remediation.


