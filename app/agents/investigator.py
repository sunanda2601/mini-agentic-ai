from app.models.incident import Incident
from app.models.messages import A2AMessage
from app.tools.logs import get_logs
from app.tools.metrics import get_metrics
from app.tools.schemas import (
    GetLogsRequest,
    GetMetricsRequest,
)
from app.rag.hybrid_search import HybridSearcher
from app.rag.knowledge_graph import KnowledgeGraph


class InvestigatorAgent:
    name = "investigator"

    def __init__(self):
        self.searcher = HybridSearcher()
        self.graph = KnowledgeGraph()

    def investigate(self, incident: Incident) -> A2AMessage:

        # =========================================================
        # 1. Collect logs
        # =========================================================
        logs = get_logs(
            GetLogsRequest(
                service=incident.service,
                timeframe="last_30_minutes",
                environment=incident.environment,
            )
        )

        # =========================================================
        # 2. Collect service metrics
        # =========================================================
        metrics = get_metrics(
            GetMetricsRequest(
                service=incident.service,
                environment=incident.environment,
            )
        )

        # =========================================================
        # 3. Retrieve runbook evidence
        #    Hybrid retrieval = BM25 + semantic search
        # =========================================================
        evidence = self.searcher.search(
            query=incident.description,
            top_k=3,
            metadata_filter={
                "service": incident.service
            },
        )

        # =========================================================
        # 4. Traverse knowledge graph
        # =========================================================
        dependencies = self.graph.get_dependencies(
            incident.service
        )

        dependents = self.graph.get_dependents(
            incident.service
        )

        owner = self.graph.get_owner(
            incident.service
        )

        runbooks = self.graph.get_runbooks(
            incident.service
        )

        # =========================================================
        # 5. Check health/metrics of dependencies
        # =========================================================
        dependency_metrics = {}

        for dependency in dependencies:
            dependency_result = get_metrics(
                GetMetricsRequest(
                    service=dependency,
                    environment=incident.environment,
                )
            )

            dependency_metrics[dependency] = (
                dependency_result.model_dump()
            )

        # =========================================================
        # 6. Return structured A2A investigation result
        # =========================================================
        return A2AMessage(
            message_id=f"{incident.incident_id}-INVESTIGATION",
            sender=self.name,
            receiver="ops",
            message_type="investigation_result",
            payload={
                "incident_id": incident.incident_id,
                "service": incident.service,
                "environment": incident.environment,
                "logs": logs.model_dump(),
                "metrics": metrics.model_dump(),
                "evidence": evidence,
                "dependencies": dependencies,
                "dependency_metrics": dependency_metrics,
                "dependents": dependents,
                "owner": owner,
                "runbooks": runbooks,
            },
        )