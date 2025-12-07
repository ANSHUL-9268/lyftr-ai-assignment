"""
Messages endpoint for querying stored messages.
"""
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.logging import get_logger
from app.models.message import Message
from app.schemas.message import MessagesListResponse, MessageResponse

logger = get_logger(__name__)

router = APIRouter(tags=["Messages"])


@router.get(
    "/messages",
    response_model=MessagesListResponse,
    summary="List messages",
    description="Retrieve stored messages with pagination and filtering."
)
async def list_messages(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100, description="Number of messages to return")] = 50,
    offset: Annotated[int, Query(ge=0, description="Number of messages to skip")] = 0,
    from_: Annotated[Optional[str], Query(alias="from", description="Filter by sender")] = None,
    since: Annotated[Optional[datetime], Query(description="Filter messages since timestamp (ISO-8601)")] = None,
    q: Annotated[Optional[str], Query(description="Case-insensitive text search")] = None,
) -> MessagesListResponse:
    """
    List messages with pagination and optional filters.
    
    - **limit**: Number of messages per page (1-100, default 50)
    - **offset**: Number of messages to skip (default 0)
    - **from**: Filter by exact sender phone number
    - **since**: Filter messages with ts >= given timestamp
    - **q**: Case-insensitive substring search in message text
    """
    # Build base query
    query = db.query(Message)
    count_query = db.query(func.count(Message.message_id))
    
    # Apply filters
    if from_:
        query = query.filter(Message.sender == from_)
        count_query = count_query.filter(Message.sender == from_)
    
    if since:
        query = query.filter(Message.ts >= since)
        count_query = count_query.filter(Message.ts >= since)
    
    if q:
        # Case-insensitive search using LIKE
        search_pattern = f"%{q}%"
        query = query.filter(Message.text.ilike(search_pattern))
        count_query = count_query.filter(Message.text.ilike(search_pattern))
    
    # Get total count before pagination
    total = count_query.scalar()
    
    # Apply ordering: ORDER BY ts ASC, message_id ASC
    query = query.order_by(Message.ts.asc(), Message.message_id.asc())
    
    # Apply pagination
    query = query.offset(offset).limit(limit)
    
    # Execute query
    messages = query.all()
    
    # Convert to response models
    data = [
        MessageResponse(
            message_id=msg.message_id,
            from_=msg.sender,
            to=msg.recipient,
            ts=msg.ts,
            text=msg.text,
            created_at=msg.created_at,
        )
        for msg in messages
    ]
    
    logger.debug(
        f"Listed messages",
        extra={
            "extra_data": {
                "total": total,
                "returned": len(data),
                "limit": limit,
                "offset": offset,
            }
        }
    )
    
    return MessagesListResponse(
        data=data,
        total=total,
        limit=limit,
        offset=offset,
    )
