from pydantic import BaseModel


class Incident(BaseModel):
    incident_id: str
    service: str
    environment: str
    description: str
    severity: str