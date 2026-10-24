from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from app.models.incident import Incident
from app.orchestration.graph import IncidentWorkflow

import hashlib
from pathlib import Path

from app.tracing.tracer import Tracer, TraceIntegrityError

app = FastAPI(
    title="Mini Agentic AI Platform",
    version="1.0.0",
    description="API for the multi-agent incident response workflow.",
)

workflow = IncidentWorkflow()

def _get_audit_tracer(workflow_id: str) -> Tracer:
    """Load the verified audit trace for an existing workflow."""

    # Do not expose audit information for an unknown workflow.
    workflow.state_store.load(workflow_id)

    # Match the audit directory convention used by IncidentWorkflow.
    base_directory = workflow.audit_directory
    if base_directory is None:
        base_directory = Path(workflow.state_store.directory) / "audit"

    # Hash the workflow ID to avoid unsafe filenames.
    safe_name = hashlib.sha256(
        workflow_id.encode("utf-8")
    ).hexdigest()

    audit_path = base_directory / f"{safe_name}.jsonl"

    if not audit_path.is_file():
        raise FileNotFoundError(
            f"Audit trace for workflow '{workflow_id}' was not found."
        )

    # Tracer loads the persisted events and verifies their hash chain.
    return Tracer(audit_path=str(audit_path))


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

@app.get("/incidents/{workflow_id}/audit")
def get_incident_audit(workflow_id: str):
    """Retrieve the verified audit events for a workflow."""
    try:
        tracer = _get_audit_tracer(workflow_id)
        events = tracer.get_events()

        return {
            "workflow_id": workflow_id,
            "event_count": len(events),
            "events": events,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except TraceIntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Audit trace integrity verification failed: {exc}",
        ) from exc


@app.get("/incidents/{workflow_id}/audit/verify")
def verify_incident_audit(workflow_id: str):
    """Verify the integrity of a workflow's persisted audit trace."""
    try:
        tracer = _get_audit_tracer(workflow_id)
        events = tracer.get_events()

        # Explicit verification makes the endpoint's purpose clear.
        Tracer.verify_trace(events)

        return {
            "workflow_id": workflow_id,
            "valid": True,
            "event_count": len(events),
            "message": "Audit trace integrity verified.",
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except TraceIntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Audit trace integrity verification failed: {exc}",
        ) from exc


@app.get("/incidents/{workflow_id}/audit/replay")
def replay_incident_audit(workflow_id: str):
    """Replay verified audit records without rerunning workflow actions."""
    try:
        tracer = _get_audit_tracer(workflow_id)

        # This validates and returns recorded events only.
        events = tracer.replay()

        event_types = {}
        for event in events:
            event_type = event["event_type"]
            event_types[event_type] = event_types.get(event_type, 0) + 1

        return {
            "workflow_id": workflow_id,
            "valid": True,
            "event_count": len(events),
            "event_types": event_types,
            "first_event": events[0] if events else None,
            "last_event": events[-1] if events else None,
            "events": events,
            "replay_mode": "audit_only",
            "actions_reexecuted": False,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except TraceIntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Audit trace integrity verification failed: {exc}",
        ) from exc
