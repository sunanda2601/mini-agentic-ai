from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from app.models.incident import Incident
from app.orchestration.graph import IncidentWorkflow

app = FastAPI(
    title="Mini Agentic AI Platform",
    version="1.0.0",
    description="API for the multi-agent incident response workflow.",
)

workflow = IncidentWorkflow()


class IncidentRequest(BaseModel):
    incident_id: str = Field(..., description="Unique incident identifier")
    service: str = Field(..., description="Target service name")
    environment: str = Field(..., description="Deployment environment")
    description: str = Field(..., description="Incident description")
    severity: str = Field(
        default="medium",
        description="Severity level (e.g., low, medium, high, critical)",
    )


class RejectionRequest(BaseModel):
    reason: str = Field(default="Rejected by human reviewer.")


class StopRequest(BaseModel):
    reason: str = Field(default="Workflow stopped by operator.")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "mini-agentic-ai",
    }


@app.post("/incidents", status_code=status.HTTP_201_CREATED)
def create_incident(request: IncidentRequest):
    try:
        incident = Incident(
            incident_id=request.incident_id,
            service=request.service,
            environment=request.environment,
            description=request.description,
            severity=request.severity,
        )
        result = workflow.run(incident)
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@app.get("/incidents/{workflow_id}")
def get_incident(workflow_id: str):
    try:
        return workflow.state_store.load(workflow_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@app.post("/incidents/{workflow_id}/approve")
def approve_incident(workflow_id: str):
    try:
        return workflow.approve(workflow_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.post("/incidents/{workflow_id}/reject")
def reject_incident(
    workflow_id: str,
    payload: RejectionRequest | None = None,
    reason: str | None = None,
):
    try:
        rejection_reason = (
            reason
            if reason
            else (payload.reason if payload else "Rejected by human reviewer.")
        )
        return workflow.reject(
            workflow_id,
            reason=rejection_reason,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.post("/incidents/{workflow_id}/stop")
def stop_incident(
    workflow_id: str,
    payload: StopRequest | None = None,
    reason: str | None = None,
):
    try:
        stop_reason = (
            reason
            if reason
            else (payload.reason if payload else "Workflow stopped by operator.")
        )
        return workflow.stop(
            workflow_id,
            reason=stop_reason,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc