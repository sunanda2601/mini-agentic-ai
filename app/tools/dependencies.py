import json
from pathlib import Path

from app.tools.schemas import (
    GetDependencyGraphRequest,
    GetDependencyGraphResponse,
    ToolError,
)


SERVICES_FILE = Path("data/infrastructure/services.json")


def get_dependency_graph(
    request: GetDependencyGraphRequest,
) -> GetDependencyGraphResponse:

    if request.environment != "production":
        return GetDependencyGraphResponse(
            success=False,
            tenant_id=request.tenant_id,
            service=request.service,
            environment=request.environment,
            error=ToolError(
                code="UNSUPPORTED_ENVIRONMENT",
                message=(
                    f"Environment '{request.environment}' "
                    "is not available."
                ),
            ),
        )

    if not SERVICES_FILE.exists():
        return GetDependencyGraphResponse(
            success=False,
            tenant_id=request.tenant_id,
            service=request.service,
            environment=request.environment,
            error=ToolError(
                code="INFRASTRUCTURE_DATA_NOT_FOUND",
                message="Infrastructure data is unavailable.",
            ),
        )

    services = json.loads(
        SERVICES_FILE.read_text(
            encoding="utf-8"
        )
    )

    if request.service not in services:
        return GetDependencyGraphResponse(
            success=False,
            tenant_id=request.tenant_id,
            service=request.service,
            environment=request.environment,
            error=ToolError(
                code="SERVICE_NOT_FOUND",
                message=(
                    f"Service '{request.service}' "
                    "does not exist."
                ),
            ),
        )

    dependencies = services[request.service].get(
        "dependencies",
        [],
    )

    dependents = [
        service_name
        for service_name, service_data in services.items()
        if request.service in service_data.get(
            "dependencies",
            [],
        )
    ]

    return GetDependencyGraphResponse(
        success=True,
        tenant_id=request.tenant_id,
        service=request.service,
        environment=request.environment,
        dependencies=dependencies,
        dependents=dependents,
    )