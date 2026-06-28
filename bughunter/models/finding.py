from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime, timezone

class FindingStatus(str, Enum):
    open = "open"
    fixed = "fixed"
    false_positive = "false_positive"

class Confidence(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    certain = "certain"

class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    run_id: str
    title: str
    severity: Severity
    confidence: Confidence
    category: str
    affected_component: str
    evidence_ids: List[str] = Field(default_factory=list)
    impact: str
    reproduction_steps: str
    recommendation: str
    retest_steps: str
    status: FindingStatus = FindingStatus.open
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
