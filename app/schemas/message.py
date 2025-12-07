"""
Pydantic schemas for request/response validation.
"""
import re
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator


# E.164 phone number regex pattern
E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")


class WebhookMessageRequest(BaseModel):
    """Request schema for POST /webhook."""
    
    message_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique message identifier"
    )
    from_: str = Field(
        ...,
        alias="from",
        description="Sender phone number in E.164 format"
    )
    to: str = Field(
        ...,
        description="Recipient phone number in E.164 format"
    )
    ts: datetime = Field(
        ...,
        description="Message timestamp in ISO-8601 UTC format (must end with Z)"
    )
    text: Optional[str] = Field(
        default=None,
        max_length=4096,
        description="Message text content"
    )
    
    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "message_id": "m1",
                "from": "+919876543210",
                "to": "+14155550100",
                "ts": "2025-01-15T10:00:00Z",
                "text": "Hello"
            }
        }
    }
    
    @field_validator("from_", mode="before")
    @classmethod
    def validate_from_e164(cls, v: str) -> str:
        """Validate sender phone number is E.164 format."""
        if not v or not E164_PATTERN.match(v):
            raise ValueError("Invalid E.164 phone number format. Must start with + followed by digits only.")
        return v
    
    @field_validator("to")
    @classmethod
    def validate_to_e164(cls, v: str) -> str:
        """Validate recipient phone number is E.164 format."""
        if not v or not E164_PATTERN.match(v):
            raise ValueError("Invalid E.164 phone number format. Must start with + followed by digits only.")
        return v
    
    @field_validator("ts", mode="before")
    @classmethod
    def validate_ts_utc(cls, v):
        """Validate timestamp ends with Z (UTC)."""
        if isinstance(v, str):
            if not v.endswith("Z"):
                raise ValueError("Timestamp must be in UTC and end with 'Z'")
        return v


class WebhookResponse(BaseModel):
    """Response schema for POST /webhook."""
    status: str = Field(default="ok")


class MessageResponse(BaseModel):
    """Schema for a single message in responses."""
    message_id: str
    from_: str = Field(alias="from")
    to: str
    ts: datetime
    text: Optional[str] = None
    created_at: Optional[datetime] = None
    
    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
    }


class MessagesListResponse(BaseModel):
    """Response schema for GET /messages."""
    data: List[MessageResponse]
    total: int
    limit: int
    offset: int


class SenderCount(BaseModel):
    """Schema for sender message count."""
    from_: str = Field(alias="from")
    count: int
    
    model_config = {
        "populate_by_name": True,
    }


class StatsResponse(BaseModel):
    """Response schema for GET /stats."""
    total_messages: int
    senders_count: int
    messages_per_sender: List[SenderCount]
    first_message_ts: Optional[datetime] = None
    last_message_ts: Optional[datetime] = None


class HealthResponse(BaseModel):
    """Response schema for health endpoints."""
    status: str
    checks: Optional[dict] = None


class ErrorResponse(BaseModel):
    """Standard error response schema."""
    detail: str
