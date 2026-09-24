from pathlib import Path

from app.tools.schemas import (
    GetLogsRequest,
    GetLogsResponse,
    ToolError,
)


LOG_DIR = Path("data/logs")


def get_logs(request: GetLogsRequest) -> GetLogsResponse:
    log_file = LOG_DIR / f"{request.service}.log"

    if request.environment != "production":
        return GetLogsResponse(
            success=False,
            service=request.service,
            environment=request.environment,
            timeframe=request.timeframe,
            error=ToolError(
                code="UNSUPPORTED_ENVIRONMENT",
                message=f"Environment '{request.environment}' is not available.",
            ),
        )

    if not log_file.exists():
        return GetLogsResponse(
            success=False,
            service=request.service,
            environment=request.environment,
            timeframe=request.timeframe,
            error=ToolError(
                code="SERVICE_LOG_NOT_FOUND",
                message=f"No logs found for service '{request.service}'.",
            ),
        )

    logs = log_file.read_text(encoding="utf-8").splitlines()

    return GetLogsResponse(
        success=True,
        service=request.service,
        environment=request.environment,
        timeframe=request.timeframe,
        logs=logs,
    )