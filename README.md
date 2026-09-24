# Mini Agentic AI Platform

A production-oriented prototype for incident analysis and safe remediation using multiple cooperating agents, structured A2A messages, retrieval, infrastructure tools, safety verification, orchestration, and audit tracing.

## 1. Problem

The platform receives an incident involving a service and analyzes operational evidence such as:

- Logs
- Metrics
- Runbooks
- Infrastructure metadata
- Service dependencies

It then plans an investigation, retrieves evidence, proposes a remediation action, verifies safety and blast radius, executes a simulated action, and records an auditable trace.

## 2. Architecture

The platform contains four mandatory agents:

1. Planner Agent
2. Investigator / RAG Agent
3. Infra / Ops Agent
4. Verifier / Safety Agent

Agents communicate using structured A2A messages rather than free-form conversational text.

### Workflow

`	ext
Incident
   |
   v
Planner
   |
   v
Investigator / RAG
   |
   +--> Logs
   +--> Metrics
   +--> Runbooks
   +--> Dependency Graph
   |
   v
Ops Agent
   |
   v
Verifier / Safety
   |
   +--> Policy Checks
   +--> Dependency Health
   +--> Blast Radius
   |
   v
Simulated Action
   |
   v
Audit Trace / Replay
