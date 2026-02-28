import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    file_size: int
    status: str
    document_type: str | None
    error_message: str | None
    created_at: datetime
    processed_at: datetime | None

    model_config = {"from_attributes": True}


class DocumentStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    document_type: str | None
    error_message: str | None

    model_config = {"from_attributes": True}


class TransactionResponse(BaseModel):
    id: uuid.UUID
    category: str
    amount: float
    currency: str
    transaction_date: datetime | None
    payee: str | None
    description: str | None
    is_on_time: bool | None
    confidence: float

    model_config = {"from_attributes": True}


class DocumentDetailResponse(DocumentResponse):
    transactions: list[TransactionResponse] = []
