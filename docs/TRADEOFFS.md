# Architecture Trade-offs

This project is a production-oriented prototype built within a limited implementation timebox. The following trade-offs were made to keep the system understandable, testable, and safe.

## 1. Local Ollama vs External LLM APIs

### Choice

The prototype uses Ollama for local LLM inference.

### Advantages

- No external API dependency for the prototype.
- Easier local development and testing.
- Data remains within the local development environment.
- No API usage cost during development.

### Trade-off

Local inference can have higher latency and requires suitable local hardware.

### Future Improvement

A production deployment could use a managed or self-hosted inference service depending on latency, cost, privacy, and scalability requirements.

---

## 2. Hybrid Retrieval vs Single Retrieval Method

### Choice

The RAG layer combines BM25 and semantic search.

### Advantages

- BM25 handles exact terminology and operational keywords well.
- Semantic search handles conceptually similar wording.
- Combining both improves retrieval robustness.

### Trade-off

Hybrid retrieval is more complex than using a single search method and requires maintaining both retrieval approaches.

### Future Improvement

Retrieval weights and evaluation datasets could be tuned using measured retrieval quality.

---

## 3. Simulated Infrastructure Actions vs Real Infrastructure

### Choice

Restart and scale operations are simulated.

### Advantages

- No risk to real infrastructure.
- Safe for demonstrations and development.
- Allows the complete agent workflow to be tested.

### Trade-off

The prototype does not validate behavior against real cloud or Kubernetes infrastructure.

### Future Improvement

Production integrations could be added behind the existing schema-first tool interface.

---

## 4. Deterministic Safety Checks vs LLM-Based Safety Decisions

### Choice

Important safety decisions are implemented using deterministic policy and blast-radius checks.

### Advantages

- More predictable behavior.
- Easier to test.
- Easier to audit.
- Reduces dependence on LLM interpretation for critical safety decisions.

### Trade-off

Deterministic rules may not cover every complex operational scenario.

### Future Improvement

LLM reasoning can assist with recommendations while deterministic policies remain the final safety gate.

---

## 5. NetworkX Knowledge Graph vs Dedicated Graph Database

### Choice

The prototype uses NetworkX for service dependency relationships.

### Advantages

- Lightweight.
- Easy to run locally.
- Simple to understand and test.
- No additional database infrastructure required.

### Trade-off

It is not designed for very large or distributed production graphs.

### Future Improvement

A production system could use a dedicated graph database or graph service.

---

## 6. File-Based Workflow State vs Distributed Workflow State

### Choice

The prototype persists workflow state as JSON files under the `traces/` directory.

### Advantages

- Simple prototype architecture.
- State survives the current process.
- Easy to inspect during development.
- Supports workflow replay and debugging.
- No additional database infrastructure is required.

### Trade-off

File-based persistence is not suitable for concurrent distributed production workloads.

### Future Improvement

A production deployment could use a durable workflow engine or distributed database-backed state store.