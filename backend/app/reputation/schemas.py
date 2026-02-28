import uuid
from datetime import datetime

from pydantic import BaseModel


class ClaimResponse(BaseModel):
    id: uuid.UUID
    claim_type: str
    claim_text: str
    claim_data: dict
    confidence: float
    period_start: datetime | None
    period_end: datetime | None

    model_config = {"from_attributes": True}


class ScoreBreakdown(BaseModel):
    raw_score: float
    weight: float
    weighted: float


class ReputationProfileResponse(BaseModel):
    score: float
    level: str
    breakdown: dict[str, ScoreBreakdown]
    claims: list[ClaimResponse]
