"""Seed demo data for a user — sample documents, transactions, and claims."""
import asyncio
import sys
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select

sys.path.insert(0, ".")
from app.database import async_session
from app.models import Document, ExtractedTransaction, VerifiableClaim
from app.reputation.scoring import recalculate_claims


async def seed(user_id: str):
    async with async_session() as db:
        uid = uuid.UUID(user_id)

        # --- Document 1: Bank Statement ---
        doc1 = Document(
            user_id=uid,
            filename="chase_bank_statement_jan2026.pdf",
            content_type="application/pdf",
            file_size=245000,
            cos_key="demo/bank_statement.pdf",
            status="completed",
            document_type="bank_statement",
            raw_extracted_text="[Demo] Chase Bank Statement - January 2026",
            processed_at=datetime.utcnow(),
        )
        db.add(doc1)
        await db.flush()

        bank_txns = [
            ("income", 4200.00, "2025-08-01", "Acme Corp", "Salary deposit", True),
            ("income", 4200.00, "2025-09-01", "Acme Corp", "Salary deposit", True),
            ("income", 4200.00, "2025-10-01", "Acme Corp", "Salary deposit", True),
            ("income", 4200.00, "2025-11-01", "Acme Corp", "Salary deposit", True),
            ("income", 4200.00, "2025-12-01", "Acme Corp", "Salary deposit", True),
            ("income", 4200.00, "2026-01-01", "Acme Corp", "Salary deposit", True),
            ("rent", -1450.00, "2025-08-01", "Parkview Apartments", "Rent payment", True),
            ("rent", -1450.00, "2025-09-01", "Parkview Apartments", "Rent payment", True),
            ("rent", -1450.00, "2025-10-01", "Parkview Apartments", "Rent payment", True),
            ("rent", -1450.00, "2025-11-01", "Parkview Apartments", "Rent payment", True),
            ("rent", -1450.00, "2025-12-03", "Parkview Apartments", "Rent payment", False),
            ("rent", -1450.00, "2026-01-01", "Parkview Apartments", "Rent payment", True),
            ("groceries", -320.50, "2025-10-15", "Whole Foods", "Groceries", None),
            ("bank_transfer", -500.00, "2025-11-10", "Savings Account", "Transfer to savings", None),
            ("bank_transfer", -500.00, "2025-12-10", "Savings Account", "Transfer to savings", None),
        ]

        for cat, amt, dt, payee, desc, on_time in bank_txns:
            db.add(ExtractedTransaction(
                document_id=doc1.id, user_id=uid, category=cat,
                amount=amt, currency="USD",
                transaction_date=datetime.strptime(dt, "%Y-%m-%d"),
                payee=payee, description=desc, is_on_time=on_time, confidence=0.92,
            ))

        # --- Document 2: Rent Receipts ---
        doc2 = Document(
            user_id=uid,
            filename="parkview_rent_receipts.pdf",
            content_type="application/pdf",
            file_size=180000,
            cos_key="demo/rent_receipts.pdf",
            status="completed",
            document_type="rent_receipt",
            raw_extracted_text="[Demo] Parkview Apartments - Rent Receipts 2025",
            processed_at=datetime.utcnow(),
        )
        db.add(doc2)
        await db.flush()

        for month in range(2, 8):  # Feb-Jul 2025
            dt = f"2025-{month:02d}-01"
            db.add(ExtractedTransaction(
                document_id=doc2.id, user_id=uid, category="rent",
                amount=-1450.00, currency="USD",
                transaction_date=datetime.strptime(dt, "%Y-%m-%d"),
                payee="Parkview Apartments", description=f"Rent - {dt[:7]}",
                is_on_time=True, confidence=0.95,
            ))

        # --- Document 3: Utility Bills ---
        doc3 = Document(
            user_id=uid,
            filename="con_edison_bills_2025.pdf",
            content_type="application/pdf",
            file_size=95000,
            cos_key="demo/utility_bills.pdf",
            status="completed",
            document_type="utility_bill",
            raw_extracted_text="[Demo] Con Edison - Electric Bills 2025",
            processed_at=datetime.utcnow(),
        )
        db.add(doc3)
        await db.flush()

        for month in range(1, 13):
            dt = f"2025-{month:02d}-15"
            on_time = month != 7  # one late payment
            db.add(ExtractedTransaction(
                document_id=doc3.id, user_id=uid, category="utility",
                amount=-(85 + (month * 3.5)), currency="USD",
                transaction_date=datetime.strptime(dt, "%Y-%m-%d"),
                payee="Con Edison", description=f"Electric bill - {dt[:7]}",
                is_on_time=on_time, confidence=0.88,
            ))

        await db.commit()

        # Now recalculate claims and score
        claims = await recalculate_claims(db, user_id)
        print(f"Seeded 3 documents with transactions for user {user_id}")
        print(f"Generated {len(claims)} claims:")
        for c in claims:
            print(f"  - {c.claim_type}: {c.claim_text}")


if __name__ == "__main__":
    user_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not user_id:
        print("Usage: python seed_demo.py <user_id>")
        sys.exit(1)
    asyncio.run(seed(user_id))
