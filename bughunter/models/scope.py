from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional

class ScanMode(str, Enum):
    passive = "passive"
    safe_active = "safe-active"
    lab_validation = "lab-validation"

class Target(BaseModel):
    model_config = ConfigDict(frozen=True)
    urls: List[str] = Field(default_factory=list)
    hosts: List[str] = Field(default_factory=list)

class CostBudget(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_tokens_per_run: int = 200000
    max_tokens_per_test: int = 15000
    max_cost_usd: float = 1.00
    warn_at_percent: int = 80

class SafetyPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)
    allow_lab_validation: bool = False
    prompt_injection_sensitivity: str = "medium"
    notes: Optional[str] = None

class ScopeProject(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    repo_path: str = "."

class SemgrepRuleConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    sha256: Optional[str] = None

class SemgrepConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    rules: List[SemgrepRuleConfig] = Field(default_factory=list)
    timeout_per_file: int = 30
    max_memory_mb: int = 256

class ScopeScan(BaseModel):
    model_config = ConfigDict(frozen=True)
    mode: ScanMode = ScanMode.safe_active
    max_requests_per_minute: int = 60
    max_depth: int = 2
    max_concurrency: int = 5
    semgrep: SemgrepConfig = Field(default_factory=SemgrepConfig)

class CiConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    fail_on_tier: str = "high"
    fail_on_score: int = 70
    fail_on_cost_usd: float = 0.50
    auto_approve: bool = False

class Scope(BaseModel):
    model_config = ConfigDict(frozen=True)
    project: ScopeProject
    targets: Target = Field(default_factory=Target)
    scan: ScopeScan = Field(default_factory=ScopeScan)
    safety: SafetyPolicy = Field(default_factory=SafetyPolicy)
    cost: CostBudget = Field(default_factory=CostBudget)
    ci: CiConfig = Field(default_factory=CiConfig)
