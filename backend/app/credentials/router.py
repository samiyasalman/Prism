import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.config import settings
from app.database import get_db
from app.models import SharedCredential, User, VerifiableClaim

from .schemas import (
    CredentialResponse,
    GenerateCredentialRequest,
    VerifiedClaimDisplay,
    VerifyResponse,
)
from .signing import sign_credential, verify_credential

router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.post("/generate", response_model=CredentialResponse, status_code=201)
async def generate(
    body: GenerateCredentialRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Load selected claims
    claim_uuids = [uuid.UUID(cid) for cid in body.claim_ids]
    result = await db.execute(
        select(VerifiableClaim).where(
            VerifiableClaim.id.in_(claim_uuids),
            VerifiableClaim.user_id == user.id,
        )
    )
    claims = result.scalars().all()
    if not claims:
        raise HTTPException(status_code=400, detail="No valid claims selected")

    # Build JWT payload
    payload = {
        "holder_name": user.full_name,
        "holder_id": str(user.id),
        "claims": [
            {
                "type": c.claim_type,
                "text": c.claim_text,
                "data": c.claim_data,
                "confidence": c.confidence,
            }
            for c in claims
        ],
        "disclosure_rules": body.disclosure_rules,
    }

    signed_jwt = sign_credential(payload, expires_hours=body.expires_hours)
    token = str(uuid.uuid4())

    credential = SharedCredential(
        user_id=user.id,
        token=token,
        claim_ids=[c.id for c in claims],
        disclosure_rules=body.disclosure_rules,
        signed_jwt=signed_jwt,
        expires_at=datetime.utcnow() + timedelta(hours=body.expires_hours),
    )
    db.add(credential)
    await db.commit()
    await db.refresh(credential)

    return _to_response(credential)


@router.get("", response_model=list[CredentialResponse])
@router.get("/", response_model=list[CredentialResponse], include_in_schema=False)
async def list_credentials(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SharedCredential)
        .where(SharedCredential.user_id == user.id)
        .order_by(SharedCredential.created_at.desc())
    )
    return [_to_response(c) for c in result.scalars().all()]


@router.delete("/{credential_id}", status_code=204)
async def revoke(
    credential_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SharedCredential).where(
            SharedCredential.id == credential_id,
            SharedCredential.user_id == user.id,
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    cred.is_revoked = True
    await db.commit()


@router.get("/verify/{token}", response_model=VerifyResponse)
async def verify(token: str, db: AsyncSession = Depends(get_db)):
    """Public endpoint — no auth required."""
    result = await db.execute(
        select(SharedCredential).where(SharedCredential.token == token)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    # Increment view count
    cred.view_count = (cred.view_count or 0) + 1
    await db.commit()

    # Verify JWT signature
    payload = verify_credential(cred.signed_jwt)
    now = datetime.utcnow()
    expired = now > cred.expires_at

    if not payload:
        return VerifyResponse(
            valid=False, expired=expired, revoked=cred.is_revoked,
            issuer=None, issued_at=None, expires_at=cred.expires_at,
            holder_name=None, claims=[],
        )

    claims = [
        VerifiedClaimDisplay(
            claim_type=c["type"],
            claim_text=c["text"],
            claim_data=c.get("data", {}),
            confidence=c.get("confidence", 0),
        )
        for c in payload.get("claims", [])
    ]

    return VerifyResponse(
        valid=not expired and not cred.is_revoked,
        expired=expired,
        revoked=cred.is_revoked,
        issuer=payload.get("iss"),
        issued_at=datetime.utcfromtimestamp(payload["iat"]) if "iat" in payload else None,
        expires_at=cred.expires_at,
        holder_name=payload.get("holder_name"),
        claims=claims,
    )


def _to_response(cred: SharedCredential) -> CredentialResponse:
    return CredentialResponse(
        id=str(cred.id),
        token=cred.token,
        share_url=f"{settings.frontend_url}/verify/{cred.token}",
        claim_ids=[str(c) for c in (cred.claim_ids or [])],
        disclosure_rules=cred.disclosure_rules,
        expires_at=cred.expires_at,
        view_count=cred.view_count or 0,
        is_revoked=cred.is_revoked,
        created_at=cred.created_at,
    )
