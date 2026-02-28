"""Full document processing pipeline: upload → COS → text extraction → LLM → save."""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import Document, ExtractedTransaction
from app.watson.cos_helper import get_cos_uri, upload_to_cos
from app.watson.llm_extraction import classify_document, extract_transactions
from app.watson.text_extraction import extract_text_async

logger = logging.getLogger(__name__)


async def upload_document(
    db: AsyncSession,
    user_id: str,
    filename: str,
    content_type: str,
    file_bytes: bytes,
) -> Document:
    """Upload file to COS and create document record."""
    cos_key = upload_to_cos(file_bytes, filename, content_type)

    doc = Document(
        user_id=user_id,
        filename=filename,
        content_type=content_type,
        file_size=len(file_bytes),
        cos_key=cos_key,
        status="uploaded",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def process_document(document_id: str) -> None:
    """Background pipeline: OCR → classify → extract transactions → save."""
    async with async_session() as db:
        result = await db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            logger.error("Document %s not found", document_id)
            return

        try:
            # Phase 1: Text extraction via Watson
            doc.status = "extracting"
            await db.commit()

            cos_uri = get_cos_uri(doc.cos_key)
            raw_text = await extract_text_async(cos_uri)
            doc.raw_extracted_text = raw_text

            # Phase 2: LLM classification & extraction
            doc.status = "analyzing"
            await db.commit()

            doc_type = await classify_document(raw_text)
            doc.document_type = doc_type

            transactions = await extract_transactions(raw_text, doc_type)

            # Save extracted transactions
            for txn in transactions:
                extracted = ExtractedTransaction(
                    document_id=doc.id,
                    user_id=doc.user_id,
                    category=txn.get("category", "other"),
                    amount=float(txn.get("amount", 0)),
                    currency=txn.get("currency", "USD"),
                    transaction_date=_parse_date(txn.get("date")),
                    payee=txn.get("payee"),
                    description=txn.get("description"),
                    is_on_time=txn.get("is_on_time"),
                    confidence=0.85,
                )
                db.add(extracted)

            doc.status = "completed"
            doc.processed_at = datetime.utcnow()
            await db.commit()
            logger.info("Document %s processed: %d transactions", document_id, len(transactions))

        except Exception as e:
            doc.status = "failed"
            doc.error_message = str(e)[:500]
            await db.commit()
            logger.exception("Failed to process document %s", document_id)


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None
