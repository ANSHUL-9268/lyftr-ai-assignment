"""
Webhook endpoint for ingesting WhatsApp messages.
"""
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_validated_body
from app.core.logging import get_logger
from app.models.message import Message
from app.schemas.message import WebhookMessageRequest, WebhookResponse, ErrorResponse

logger = get_logger(__name__)

router = APIRouter(tags=["Webhook"])


@router.post(
    "/webhook",
    response_model=WebhookResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid signature"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
    summary="Ingest WhatsApp message",
    description="Receive and store an inbound WhatsApp message. Requires valid HMAC-SHA256 signature."
)
async def ingest_message(
    validated_body: Annotated[bytes, Depends(get_validated_body)],
    db: Annotated[Session, Depends(get_db)],
) -> WebhookResponse:
    """
    Ingest an inbound WhatsApp message.
    
    - Validates HMAC-SHA256 signature (via dependency)
    - Validates message payload
    - Stores message with idempotency (duplicate message_id returns ok)
    """
    # Parse and validate the JSON body
    try:
        data = json.loads(validated_body)
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in webhook request: {e}")
        raise HTTPException(status_code=422, detail="Invalid JSON")
    
    # Validate with Pydantic
    try:
        message_data = WebhookMessageRequest.model_validate(data)
    except Exception as e:
        logger.warning(f"Validation error in webhook request: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    
    # Check if message already exists (idempotency)
    existing = db.query(Message).filter(
        Message.message_id == message_data.message_id
    ).first()
    
    if existing:
        logger.info(
            f"Duplicate message received, returning ok",
            extra={"extra_data": {"message_id": message_data.message_id}}
        )
        return WebhookResponse(status="ok")
    
    # Create new message
    message = Message(
        message_id=message_data.message_id,
        sender=message_data.from_,
        recipient=message_data.to,
        ts=message_data.ts,
        text=message_data.text,
    )
    
    try:
        db.add(message)
        db.commit()
        logger.info(
            "Message ingested successfully",
            extra={
                "extra_data": {
                    "message_id": message_data.message_id,
                    "sender": message_data.from_,
                }
            }
        )
    except IntegrityError:
        # Race condition: another request inserted the same message_id
        db.rollback()
        logger.info(
            "Duplicate message detected via constraint",
            extra={"extra_data": {"message_id": message_data.message_id}}
        )
    
    return WebhookResponse(status="ok")
