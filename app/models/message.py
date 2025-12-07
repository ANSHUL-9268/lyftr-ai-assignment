"""
Message database model.
"""
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text, Index

from app.core.database import Base


class Message(Base):
    """SQLite model for storing WhatsApp messages."""
    
    __tablename__ = "messages"
    
    # Primary key - message_id must be unique for idempotency
    message_id = Column(String(255), primary_key=True, nullable=False)
    
    # Sender and recipient (E.164 format)
    sender = Column(String(20), nullable=False, index=True)  # 'from' is reserved
    recipient = Column(String(20), nullable=False)  # 'to'
    
    # Timestamp from the message
    ts = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Message content (optional, max 4096 chars)
    text = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    # Composite index for efficient ordering
    __table_args__ = (
        Index("ix_messages_ts_message_id", "ts", "message_id"),
    )
    
    def __repr__(self) -> str:
        return f"<Message(message_id={self.message_id}, sender={self.sender})>"
    
    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "message_id": self.message_id,
            "from": self.sender,
            "to": self.recipient,
            "ts": self.ts.isoformat() if self.ts else None,
            "text": self.text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
