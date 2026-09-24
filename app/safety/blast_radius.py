from app.config import settings
from app.rag.knowledge_graph import KnowledgeGraph


class BlastRadiusCalculator:
    def __init__(self):
        self.graph = KnowledgeGraph()

    def calculate(self, service: str) -> dict:
        dependencies = self.graph.get_dependencies(service)
        dependents = self.graph.get_dependents(service)

        # The action directly affects the target service.
        # Dependents represent services that may be impacted by the action.
        affected_services = set(
            [service] + dependents
        )

        blast_radius = len(affected_services)

        return {
            "service": service,
            "dependencies": dependencies,
            "dependents": dependents,
            "affected_services": sorted(affected_services),
            "blast_radius": blast_radius,
            "max_allowed_blast_radius": settings.max_blast_radius,
            "within_limit": blast_radius <= settings.max_blast_radius,
        }