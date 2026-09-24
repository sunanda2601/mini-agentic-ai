import json
from pathlib import Path

import networkx as nx


SERVICES_FILE = Path("data/infrastructure/services.json")
RUNBOOKS_DIR = Path("data/runbooks")


class KnowledgeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()
        self._build_graph()

    def _build_graph(self):
        if not SERVICES_FILE.exists():
            return

        services = json.loads(
            SERVICES_FILE.read_text(encoding="utf-8")
        )

        for service_name, service_data in services.items():
            # -----------------------------------------------------
            # Service node
            # -----------------------------------------------------
            self.graph.add_node(
                service_name,
                type="service",
                environment=service_data["environment"],
                version=service_data["version"],
                owner=service_data["owner"],
            )

            # -----------------------------------------------------
            # Dependency relationships
            # -----------------------------------------------------
            for dependency in service_data.get(
                "dependencies",
                [],
            ):
                self.graph.add_edge(
                    service_name,
                    dependency,
                    relationship="depends_on",
                )

            # -----------------------------------------------------
            # Runbook relationships
            # -----------------------------------------------------
            self._add_runbook_relationships(
                service_name
            )

    def _add_runbook_relationships(
        self,
        service: str,
    ) -> None:
        if not RUNBOOKS_DIR.exists():
            return

        # Find runbooks whose filename starts with the
        # service name.
        runbook_files = RUNBOOKS_DIR.glob(
            f"{service}-*.md"
        )

        for runbook_path in runbook_files:
            runbook_id = runbook_path.stem

            self.graph.add_node(
                runbook_id,
                type="runbook",
                service=service,
                source=str(runbook_path),
            )

            self.graph.add_edge(
                service,
                runbook_id,
                relationship="has_runbook",
            )

    def get_dependencies(
        self,
        service: str,
    ) -> list[str]:
        if service not in self.graph:
            return []

        return [
            node
            for node in self.graph.successors(service)
            if self.graph.edges[
                service,
                node,
            ].get("relationship") == "depends_on"
        ]

    def get_dependents(
        self,
        service: str,
    ) -> list[str]:
        if service not in self.graph:
            return []

        return [
            node
            for node in self.graph.predecessors(service)
            if self.graph.edges[
                node,
                service,
            ].get("relationship") == "depends_on"
        ]

    def get_owner(
        self,
        service: str,
    ) -> str | None:
        if service not in self.graph:
            return None

        return self.graph.nodes[
            service
        ].get("owner")

    def get_runbooks(
        self,
        service: str,
    ) -> list[str]:
        if service not in self.graph:
            return []

        return [
            node
            for node in self.graph.successors(service)
            if self.graph.edges[
                service,
                node,
            ].get("relationship") == "has_runbook"
        ]