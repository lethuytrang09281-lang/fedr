"""Document model for storing extracted attachment data."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from src.database.models import Base


class Document(Base):
    """Stores extracted data from message attachments."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=True, index=True)
    message_guid = Column(UUID(as_uuid=True), index=True)
    filename = Column(String(255), nullable=False)
    document_type = Column(String(50), nullable=False)  # egr_extract, appraisal_report, etc.
    file_size = Column(Integer)  # Size in bytes
    extracted_data = Column(JSON)  # All extracted structured data
    downloaded_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationship
    lot = relationship("Lot", back_populates="documents")
