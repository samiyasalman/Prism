"""TrustScore algorithm — aggregate transactions into verifiable claims and a 0-100 score."""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExtractedTransaction, VerifiableClaim

logger = logging.getLogger(__name__)

# Score weights per category
WEIGHTS = {
    "rent_history": 0.30,
    "income_stability": 0.30,
    "utility_payment": 0.20,
    "bank_health": 0.20,
}


async def recalculate_claims(db: AsyncSession, user_id: str) -> list[VerifiableClaim]:
    """Delete old claims, re-aggregate from all transactions, return new claims."""
    # Remove existing claims
    result = await db.execute(select(VerifiableClaim).where(VerifiableClaim.user_id == user_id))
    for claim in result.scalars().all():
        await db.delete(claim)

    # Load all transactions
    result = await db.execute(
        select(ExtractedTransaction)
        .where(ExtractedTransaction.user_id == user_id)
        .order_by(ExtractedTransaction.transaction_date)
    )
    transactions = result.scalars().all()
    if not transactions:
        await db.commit()
        return []

    claims = []

    # Group by category
    rent_txns = [t for t in transactions if t.category == "rent"]
    income_txns = [t for t in transactions if t.category == "income"]
    utility_txns = [t for t in transactions if t.category == "utility"]
    all_txns = transactions

    # Rent history claim
    if rent_txns:
        on_time = sum(1 for t in rent_txns if t.is_on_time is True)
        total = len(rent_txns)
        avg_amount = sum(abs(t.amount) for t in rent_txns) / total
        dates = [t.transaction_date for t in rent_txns if t.transaction_date]
        claim = VerifiableClaim(
            user_id=user_id,
            claim_type="rent_history",
            claim_text=f"Paid rent on time {on_time}/{total} payments, avg ${avg_amount:,.0f}/mo",
            claim_data={
                "total_payments": total,
                "on_time_payments": on_time,
                "on_time_rate": round(on_time / total, 2) if total else 0,
                "average_amount": round(avg_amount, 2),
                "currency": "USD",
            },
            confidence=min(0.95, 0.6 + (total * 0.03)),
            period_start=min(dates) if dates else None,
            period_end=max(dates) if dates else None,
        )
        claims.append(claim)

    # Income stability claim
    if income_txns:
        total_income = sum(abs(t.amount) for t in income_txns)
        avg_income = total_income / len(income_txns)
        dates = [t.transaction_date for t in income_txns if t.transaction_date]
        claim = VerifiableClaim(
            user_id=user_id,
            claim_type="income_stability",
            claim_text=f"Regular income of avg ${avg_income:,.0f} across {len(income_txns)} deposits",
            claim_data={
                "total_deposits": len(income_txns),
                "total_income": round(total_income, 2),
                "average_deposit": round(avg_income, 2),
                "currency": "USD",
            },
            confidence=min(0.95, 0.5 + (len(income_txns) * 0.04)),
            period_start=min(dates) if dates else None,
            period_end=max(dates) if dates else None,
        )
        claims.append(claim)

    # Utility payment claim
    if utility_txns:
        on_time = sum(1 for t in utility_txns if t.is_on_time is True)
        total = len(utility_txns)
        dates = [t.transaction_date for t in utility_txns if t.transaction_date]
        claim = VerifiableClaim(
            user_id=user_id,
            claim_type="utility_payment",
            claim_text=f"Utility payments: {on_time}/{total} on time",
            claim_data={
                "total_payments": total,
                "on_time_payments": on_time,
                "on_time_rate": round(on_time / total, 2) if total else 0,
            },
            confidence=min(0.90, 0.5 + (total * 0.03)),
            period_start=min(dates) if dates else None,
            period_end=max(dates) if dates else None,
        )
        claims.append(claim)

    # Bank health claim
    if all_txns:
        total_in = sum(abs(t.amount) for t in all_txns if t.amount > 0)
        total_out = sum(abs(t.amount) for t in all_txns if t.amount < 0)
        net = total_in - total_out
        claim = VerifiableClaim(
            user_id=user_id,
            claim_type="bank_health",
            claim_text=f"Net cash flow: ${net:+,.0f} ({len(all_txns)} transactions analyzed)",
            claim_data={
                "total_inflow": round(total_in, 2),
                "total_outflow": round(total_out, 2),
                "net_flow": round(net, 2),
                "transaction_count": len(all_txns),
            },
            confidence=min(0.90, 0.5 + (len(all_txns) * 0.02)),
        )
        claims.append(claim)

    for c in claims:
        db.add(c)
    await db.commit()
    for c in claims:
        await db.refresh(c)
    return claims


def compute_trust_score(claims: list[VerifiableClaim]) -> dict:
    """Compute weighted TrustScore (0-100) from claims."""
    if not claims:
        return {"score": 0, "breakdown": {}, "level": "No Data"}

    breakdown = {}
    for claim in claims:
        ct = claim.claim_type
        data = claim.claim_data or {}
        weight = WEIGHTS.get(ct, 0.1)

        if ct == "rent_history":
            rate = data.get("on_time_rate", 0)
            count_bonus = min(1.0, data.get("total_payments", 0) / 12)
            raw = (rate * 0.7 + count_bonus * 0.3) * 100
        elif ct == "income_stability":
            count_bonus = min(1.0, data.get("total_deposits", 0) / 12)
            raw = count_bonus * 100
        elif ct == "utility_payment":
            rate = data.get("on_time_rate", 0)
            raw = rate * 100
        elif ct == "bank_health":
            net = data.get("net_flow", 0)
            raw = min(100, max(0, 50 + (net / 100)))
        else:
            raw = 50

        breakdown[ct] = {"raw_score": round(raw, 1), "weight": weight, "weighted": round(raw * weight, 1)}

    score = sum(v["weighted"] for v in breakdown.values())
    score = round(min(100, max(0, score)), 1)

    if score >= 80:
        level = "Excellent"
    elif score >= 60:
        level = "Good"
    elif score >= 40:
        level = "Fair"
    elif score >= 20:
        level = "Building"
    else:
        level = "New"

    return {"score": score, "breakdown": breakdown, "level": level}
