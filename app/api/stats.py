"""
Stats endpoint for analytics.
"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.logging import get_logger
from app.models.message import Message
from app.schemas.message import StatsResponse, SenderCount

logger = get_logger(__name__)

router = APIRouter(tags=["Analytics"])


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Get message statistics",
    description="Returns lightweight analytics about stored messages."
)
async def get_stats(
    db: Annotated[Session, Depends(get_db)],
) -> StatsResponse:
    """
    Get message statistics including:
    
    - Total message count
    - Unique sender count
    - Top 10 senders by message count
    - First and last message timestamps
    """
    # Total messages
    total_messages = db.query(func.count(Message.message_id)).scalar() or 0
    
    # Unique senders count
    senders_count = db.query(func.count(func.distinct(Message.sender))).scalar() or 0
    
    # Top 10 senders by message count
    top_senders_query = (
        db.query(
            Message.sender,
            func.count(Message.message_id).label("count")
        )
        .group_by(Message.sender)
        .order_by(func.count(Message.message_id).desc())
        .limit(10)
        .all()
    )
    
    messages_per_sender = [
        SenderCount(from_=sender, count=count)
        for sender, count in top_senders_query
    ]
    
    # First and last message timestamps
    first_message_ts = db.query(func.min(Message.ts)).scalar()
    last_message_ts = db.query(func.max(Message.ts)).scalar()
    
    logger.debug(
        "Generated stats",
        extra={
            "extra_data": {
                "total_messages": total_messages,
                "senders_count": senders_count,
            }
        }
    )
    
    return StatsResponse(
        total_messages=total_messages,
        senders_count=senders_count,
        messages_per_sender=messages_per_sender,
        first_message_ts=first_message_ts,
        last_message_ts=last_message_ts,
    )
