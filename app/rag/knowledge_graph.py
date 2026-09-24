import json
from pathlib import Path

import networkx as nx


SERVICES_FILE = Path("data/infrastructure/services.json")


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
            self.graph.add_node(
                service_name,
                type="service",
                environment=service_data["environment"],
                version=service_data["version"],
                owner=service_data["owner"],
            )

            for dependency in service_data.get("dependencies", []):
                self.graph.add_edge(
                    service_name,
                    dependency,
                    relationship="depends_on",
                )

    def get_dependencies(self, service: str) -> list[str]:
        if service not in self.graph:
            return []

        return list(self.graph.successors(service))

    def get_dependents(self, service: str) -> list[str]:
        if service not in self.graph:
            return []

        return list(self.graph.predecessors(service))

    def get_owner(self, service: str) -> str | None:
        if service not in self.graph:
            return None

        return self.graph.nodes[service].get("owner")