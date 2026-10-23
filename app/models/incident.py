from pydantic import BaseModel, Field


class Incident(BaseModel):
    incident_id: str = Field(..., description="Unique incident identifier")
    service: str = Field(..., description="Target service name")
    environment: str = Field(..., description="Deployment environment (staging or production)")
    description: str = Field(..., description="Incident description")
    severity: str = Field(default="medium", description="Severity level")