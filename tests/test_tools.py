from app.tools.logs import get_logs
from app.tools.metrics import get_metrics
from app.tools.restart import simulate_restart
from app.tools.scale import simulate_scale
from app.tools.dependencies import get_dependency_graph

from app.tools.schemas import (
    GetLogsRequest,
    GetMetricsRequest,
    SimulateRestartRequest,
    SimulateScaleRequest,
    GetDependencyGraphRequest,
)


def test_get_logs_success():
    response = get_logs(
        GetLogsRequest(
            service="payment-service",
            timeframe="last_30_minutes",
            environment="production",
        )
    )

    assert response.success is True
    assert response.service == "payment-service"
    assert len(response.logs) > 0
    assert response.error is None


def test_get_metrics_success():
    response = get_metrics(
        GetMetricsRequest(
            service="payment-service",
            environment="production",
        )
    )

    assert response.success is True
    assert response.metrics["healthy"] is False
    assert response.error is None


def test_simulate_restart():
    response = simulate_restart(
        SimulateRestartRequest(
            service="payment-service",
            environment="production",
        )
    )

    assert response.success is True
    assert response.simulated is True
    assert response.action == "restart"


def test_simulate_scale():
    response = simulate_scale(
        SimulateScaleRequest(
            service="payment-service",
            replicas=5,
            environment="production",
        )
    )

    assert response.success is True
    assert response.simulated is True
    assert response.requested_replicas == 5


def test_dependency_graph():
    response = get_dependency_graph(
        GetDependencyGraphRequest(
            service="payment-service",
            environment="production",
        )
    )

    assert response.success is True
    assert "payment-db" in response.dependencies
    assert "checkout-service" in response.dependents