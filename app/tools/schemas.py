from pydantic import BaseModel


class GetLogsRequest(BaseModel):
    tenant_id: str = "demo-tenant"
    service: str
    timeframe: str
    environment: str = "production"


class ToolError(BaseModel):
    code: str
    message: str


class GetLogsResponse(BaseModel):
    success: bool
    tenant_id: str
    service: str
    environment: str
    timeframe: str
    logs: list[str] = []
    version: str = "1.0.0"
    error: ToolError | None = None


class GetMetricsRequest(BaseModel):
    tenant_id: str = "demo-tenant"
    service: str
    environment: str = "production"


class GetMetricsResponse(BaseModel):
    success: bool
    tenant_id: str
    service: str
    environment: str
    metrics: dict = {}
    version: str = "1.0.0"
    error: ToolError | None = None


class SimulateRestartRequest(BaseModel):
    tenant_id: str = "demo-tenant"
    service: str
    environment: str = "production"


class SimulateRestartResponse(BaseModel):
    success: bool
    tenant_id: str
    service: str
    environment: str
    action: str
    simulated: bool
    message: str
    version: str = "1.0.0"
    error: ToolError | None = None


class SimulateScaleRequest(BaseModel):
    tenant_id: str = "demo-tenant"
    service: str
    replicas: int
    environment: str = "production"


class SimulateScaleResponse(BaseModel):
    success: bool
    tenant_id: str
    service: str
    environment: str
    requested_replicas: int
    action: str
    simulated: bool
    message: str
    version: str = "1.0.0"
    error: ToolError | None = None


class GetDependencyGraphRequest(BaseModel):
    tenant_id: str = "demo-tenant"
    service: str
    environment: str = "production"


class GetDependencyGraphResponse(BaseModel):
    success: bool
    tenant_id: str
    service: str
    environment: str
    dependencies: list[str] = []
    dependents: list[str] = []
    version: str = "1.0.0"
    error: ToolError | None = None