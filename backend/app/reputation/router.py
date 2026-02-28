from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User, VerifiableClaim

from .schemas import ClaimResponse, ReputationProfileResponse
from .scoring import compute_trust_score, recalculate_claims

router = APIRouter(prefix="/reputation", tags=["reputation"])


@router.get("/profile", response_model=ReputationProfileResponse)
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VerifiableClaim).where(VerifiableClaim.user_id == user.id)
    )
    claims = result.scalars().all()
    score_data = compute_trust_score(claims)
    return ReputationProfileResponse(
        score=score_data["score"],
        level=score_data["level"],
        breakdown=score_data["breakdown"],
        claims=claims,
    )


@router.get("/claims", response_model=list[ClaimResponse])
async def get_claims(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VerifiableClaim).where(VerifiableClaim.user_id == user.id)
    )
    return result.scalars().all()


@router.post("/recalculate", response_model=ReputationProfileResponse)
async def recalculate(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    claims = await recalculate_claims(db, str(user.id))
    score_data = compute_trust_score(claims)
    return ReputationProfileResponse(
        score=score_data["score"],
        level=score_data["level"],
        breakdown=score_data["breakdown"],
        claims=claims,
    )
