import json
from pathlib import Path

from app.tools.schemas import (
    SimulateRestartRequest,
    SimulateRestartResponse,
    ToolError,
)


SERVICES_FILE = Path("data/infrastructure/services.json")


def simulate_restart(
    request: SimulateRestartRequest,
) -> SimulateRestartResponse:

    if request.environment != "production":
        return SimulateRestartResponse(
            success=False,
            tenant_id=request.tenant_id,
            service=request.service,
            environment=request.environment,
            action="restart",
            simulated=True,
            message="Restart was not executed.",
            error=ToolError(
                code="UNSUPPORTED_ENVIRONMENT",
                message=(
                    f"Environment '{request.environment}' "
                    "is not available."
                ),
            ),
        )

    if not SERVICES_FILE.exists():
        return SimulateRestartResponse(
            success=False,
            tenant_id=request.tenant_id,
            service=request.service,
            environment=request.environment,
            action="restart",
            simulated=True,
            message="Restart was not executed.",
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
        return SimulateRestartResponse(
            success=False,
            tenant_id=request.tenant_id,
            service=request.service,
            environment=request.environment,
            action="restart",
            simulated=True,
            message="Restart was not executed.",
            error=ToolError(
                code="SERVICE_NOT_FOUND",
                message=(
                    f"Service '{request.service}' "
                    "does not exist."
                ),
            ),
        )

    return SimulateRestartResponse(
        success=True,
        tenant_id=request.tenant_id,
        service=request.service,
        environment=request.environment,
        action="restart",
        simulated=True,
        message=(
            f"Restart of '{request.service}' "
            "simulated successfully."
        ),
    )