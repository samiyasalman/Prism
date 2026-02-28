import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    countries = Column(ARRAY(String), default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    credentials = relationship("SharedCredential", back_populates="user", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    cos_key = Column(String(500))
    status = Column(String(50), default="uploaded")  # uploaded, extracting, analyzing, completed, failed
    watson_job_id = Column(String(255))
    raw_extracted_text = Column(Text)
    document_type = Column(String(100))  # bank_statement, rent_receipt, utility_bill, pay_stub
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)

    user = relationship("User", back_populates="documents")
    transactions = relationship("ExtractedTransaction", back_populates="document", cascade="all, delete-orphan")


class ExtractedTransaction(Base):
    __tablename__ = "extracted_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    category = Column(String(100), nullable=False)  # rent, income, utility, bank_transfer, other
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USD")
    transaction_date = Column(DateTime)
    payee = Column(String(255))
    description = Column(Text)
    is_on_time = Column(Boolean)
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="transactions")


class VerifiableClaim(Base):
    __tablename__ = "verifiable_claims"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    claim_type = Column(String(100), nullable=False)  # rent_history, income_stability, utility_payment, bank_health
    claim_text = Column(Text, nullable=False)  # Human-readable: "Paid rent on time for 12 months"
    claim_data = Column(JSON, nullable=False)  # Structured data for verification
    confidence = Column(Float, default=0.0)
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SharedCredential(Base):
    __tablename__ = "shared_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(500), unique=True, nullable=False, index=True)
    claim_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False)
    disclosure_rules = Column(JSON)  # e.g. {"income": "threshold", "threshold_text": "income > 3x rent"}
    signed_jwt = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    view_count = Column(Integer, default=0)
    is_revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="credentials")
