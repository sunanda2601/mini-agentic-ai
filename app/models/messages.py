from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class A2AMessage(BaseModel):
    message_id: str
    sender: str
    receiver: str
    message_type: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    payload: dict[str, Any]