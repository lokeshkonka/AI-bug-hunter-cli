from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from typing import Dict, Any
from datetime import datetime, timezone

class EventType(str, Enum):
    phase_started = "phase_started"
    phase_completed = "phase_completed"
    tool_started = "tool_started"
    tool_progress = "tool_progress"
    tool_completed = "tool_completed"
    observation = "observation"
    finding_candidate = "finding_candidate"
    finding_confirmed = "finding_confirmed"
    finding_rejected = "finding_rejected"
    report_written = "report_written"
    policy_violation = "policy_violation"
    security_event = "security_event"
    error = "error"
    budget_warning = "budget_warning"

class BugHunterEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    run_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    type: EventType
    agent: str
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
