from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.orchestration.graph import IncidentWorkflow


app = FastAPI(
    title="Mini Agentic AI Platform",
    version="1.0.0",
    description="API for the multi-agent incident response workflow.",
)

workflow = IncidentWorkflow()


class IncidentRequest(BaseModel):
    incident_id: str
    service: str
    environment: str
    description: str


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "mini-agentic-ai",
    }


@app.post("/incidents")
def create_incident(request: IncidentRequest):
    try:
        result = workflow.run(
            incident_id=request.incident_id,
            service=request.service,
            environment=request.environment,
            description=request.description,
        )
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


@app.post("/incidents/{workflow_id}/approve")
def approve_incident(workflow_id: str):
    try:
        return workflow.approve(workflow_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.post("/incidents/{workflow_id}/reject")
def reject_incident(
    workflow_id: str,
    reason: str = "Rejected by human reviewer.",
):
    try:
        return workflow.reject(
            workflow_id,
            reason=reason,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.post("/incidents/{workflow_id}/stop")
def stop_incident(
    workflow_id: str,
    reason: str = "Workflow stopped by operator.",
):
    try:
        return workflow.stop(
            workflow_id,
            reason=reason,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc