from pathlib import Path

from app.tools.schemas import (
    GetMetricsRequest,
    GetMetricsResponse,
    ToolError,
)


METRICS_DIR = Path("data/metrics")


def get_metrics(request: GetMetricsRequest) -> GetMetricsResponse:
    metrics_file = METRICS_DIR / f"{request.service}.json"

    if request.environment != "production":
        return GetMetricsResponse(
            success=False,
            service=request.service,
            environment=request.environment,
            error=ToolError(
                code="UNSUPPORTED_ENVIRONMENT",
                message=f"Environment '{request.environment}' is not available.",
            ),
        )

    if not metrics_file.exists():
        return GetMetricsResponse(
            success=False,
            service=request.service,
            environment=request.environment,
            error=ToolError(
                code="SERVICE_METRICS_NOT_FOUND",
                message=f"No metrics found for service '{request.service}'.",
            ),
        )

    import json

    metrics = json.loads(metrics_file.read_text(encoding="utf-8"))

    return GetMetricsResponse(
        success=True,
        service=request.service,
        environment=request.environment,
        metrics=metrics,
    )