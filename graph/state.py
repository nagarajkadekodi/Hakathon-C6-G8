from typing import Optional, TypedDict

from pydantic import BaseModel


class Classification(BaseModel):
    issue_type: str  # OOM_KILL | DB_TIMEOUT | DEPLOY_FAILURE | AUTH_ERROR | DISK_FULL | NETWORK_ERROR | UNKNOWN
    description: str
    affected_services: list[str]
    evidence_lines: list[str]
    confidence: float  # 0.0–1.0


class IssueSeverity(BaseModel):
    issue_type: str
    severity: str  # P0 | P1 | P2 | P3
    justification: str


class SeverityResult(BaseModel):
    per_issue: list[IssueSeverity]
    overall_severity: str
    overall_justification: str


class RemediationStep(BaseModel):
    step_number: int
    action: str
    estimated_time_min: int
    owner_role: str
    runbook_slug: str


class RemediationPlan(BaseModel):
    issue_type: str
    steps: list[RemediationStep]


class IncidentState(TypedDict):
    incident_id: str
    raw_log: str
    classifications: list[dict]  # Classification dicts — populated by Node 1
    severity: Optional[dict]     # SeverityResult dict — populated by Node 2
    remediation: list[dict]      # RemediationPlan dicts — populated by Node 3
    artifacts: Optional[dict]    # artifact bundle dict — populated by Node 4
    review: Optional[dict]       # AI reviewer output — populated by Node 5
