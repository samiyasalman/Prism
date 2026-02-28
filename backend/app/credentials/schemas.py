from datetime import datetime

from pydantic import BaseModel


class GenerateCredentialRequest(BaseModel):
    claim_ids: list[str]
    disclosure_rules: dict | None = None
    expires_hours: int = 168  # 7 days default


class CredentialResponse(BaseModel):
    id: str
    token: str
    share_url: str
    claim_ids: list[str]
    disclosure_rules: dict | None
    expires_at: datetime
    view_count: int
    is_revoked: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class VerifiedClaimDisplay(BaseModel):
    claim_type: str
    claim_text: str
    claim_data: dict
    confidence: float


class VerifyResponse(BaseModel):
    valid: bool
    expired: bool
    revoked: bool
    issuer: str | None
    issued_at: datetime | None
    expires_at: datetime | None
    holder_name: str | None
    claims: list[VerifiedClaimDisplay]
