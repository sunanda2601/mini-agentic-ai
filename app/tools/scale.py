import json
from pathlib import Path

from app.tools.schemas import (
    SimulateScaleRequest,
    SimulateScaleResponse,
    ToolError,
)


SERVICES_FILE = Path("data/infrastructure/services.json")


def simulate_scale(
    request: SimulateScaleRequest,
) -> SimulateScaleResponse:

    if request.environment != "production":
        return SimulateScaleResponse(
            success=False,
            service=request.service,
            environment=request.environment,
            requested_replicas=request.replicas,
            action="scale",
            simulated=True,
            message="Scale action was not executed.",
            error=ToolError(
                code="UNSUPPORTED_ENVIRONMENT",
                message=f"Environment '{request.environment}' is not available.",
            ),
        )

    if request.replicas < 1:
        return SimulateScaleResponse(
            success=False,
            service=request.service,
            environment=request.environment,
            requested_replicas=request.replicas,
            action="scale",
            simulated=True,
            message="Scale action was not executed.",
            error=ToolError(
                code="INVALID_REPLICA_COUNT",
                message="Replica count must be at least 1.",
            ),
        )

    if not SERVICES_FILE.exists():
        return SimulateScaleResponse(
            success=False,
            service=request.service,
            environment=request.environment,
            requested_replicas=request.replicas,
            action="scale",
            simulated=True,
            message="Scale action was not executed.",
            error=ToolError(
                code="INFRASTRUCTURE_DATA_NOT_FOUND",
                message="Infrastructure data is unavailable.",
            ),
        )

    services = json.loads(
        SERVICES_FILE.read_text(encoding="utf-8")
    )

    if request.service not in services:
        return SimulateScaleResponse(
            success=False,
            service=request.service,
            environment=request.environment,
            requested_replicas=request.replicas,
            action="scale",
            simulated=True,
            message="Scale action was not executed.",
            error=ToolError(
                code="SERVICE_NOT_FOUND",
                message=f"Service '{request.service}' does not exist.",
            ),
        )

    return SimulateScaleResponse(
        success=True,
        service=request.service,
        environment=request.environment,
        requested_replicas=request.replicas,
        action="scale",
        simulated=True,
        message=(
            f"Scaling '{request.service}' to "
            f"{request.replicas} replicas simulated successfully."
        ),
    )
    