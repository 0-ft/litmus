"""Queue API endpoints for managing the assessment queue."""
import asyncio
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import not_
from pydantic import BaseModel
from datetime import datetime

from ..database import get_db
from ..models import AssessmentQueueItem, QueueStatus, Paper
from ..queue_worker import queue_worker, queue_events

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Pydantic Schemas
# ============================================================================

class QueueItemResponse(BaseModel):
    """Response for a single queue item."""
    id: int
    paper_id: int
    paper_title: Optional[str] = None
    status: str
    priority: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result_grade: Optional[str] = None
    result_score: Optional[int] = None
    result_flagged: Optional[bool] = None

    class Config:
        from_attributes = True


class QueueStatusResponse(BaseModel):
    """Response for queue status."""
    worker_running: bool
    pending: int
    processing: int
    completed: int
    failed: int
    total: int
    current: Optional[dict] = None


class AddToQueueRequest(BaseModel):
    """Request to add papers to queue."""
    paper_ids: Optional[List[int]] = None  # Specific paper IDs
    add_all_unassessed: bool = False  # Add all unassessed papers
    priority: int = 10  # Lower = higher priority


class AddToQueueResponse(BaseModel):
    """Response for adding to queue."""
    message: str
    added: int
    already_queued: int


class ClearQueueResponse(BaseModel):
    """Response for clearing queue."""
    message: str
    removed: int


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/status", response_model=QueueStatusResponse)
async def get_queue_status():
    """Get current queue status."""
    return queue_worker.get_status()


@router.get("/items", response_model=List[QueueItemResponse])
async def get_queue_items(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get queue items, optionally filtered by status."""
    query = db.query(AssessmentQueueItem).join(Paper)
    
    if status:
        query = query.filter(AssessmentQueueItem.status == status)
    
    items = query.order_by(
        AssessmentQueueItem.priority,
        AssessmentQueueItem.created_at.desc()
    ).limit(limit).all()
    
    return [
        QueueItemResponse(
            id=item.id,
            paper_id=item.paper_id,
            paper_title=item.paper.title if item.paper else None,
            status=item.status,
            priority=item.priority,
            created_at=item.created_at,
            started_at=item.started_at,
            completed_at=item.completed_at,
            error_message=item.error_message,
            result_grade=item.result_grade,
            result_score=item.result_score,
            result_flagged=bool(item.result_flagged) if item.result_flagged is not None else None,
        )
        for item in items
    ]


@router.post("/add", response_model=AddToQueueResponse)
async def add_to_queue(
    request: AddToQueueRequest,
    db: Session = Depends(get_db),
):
    """Add papers to the assessment queue."""
    added = 0
    already_queued = 0
    
    paper_ids = []
    
    if request.add_all_unassessed:
        # Get all unassessed papers
        unassessed = db.query(Paper).filter(Paper.processed == False).all()
        paper_ids = [p.id for p in unassessed]
    elif request.paper_ids:
        paper_ids = request.paper_ids
    
    if not paper_ids:
        return AddToQueueResponse(
            message="No papers to add",
            added=0,
            already_queued=0,
        )
    
    # Get papers already in queue (pending or processing)
    existing = db.query(AssessmentQueueItem.paper_id).filter(
        AssessmentQueueItem.paper_id.in_(paper_ids),
        AssessmentQueueItem.status.in_([QueueStatus.PENDING, QueueStatus.PROCESSING])
    ).all()
    existing_ids = {e[0] for e in existing}
    
    for paper_id in paper_ids:
        if paper_id in existing_ids:
            already_queued += 1
            continue
        
        # Verify paper exists
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            continue
        
        # Add to queue
        item = AssessmentQueueItem(
            paper_id=paper_id,
            status=QueueStatus.PENDING,
            priority=request.priority,
        )
        db.add(item)
        added += 1
    
    db.commit()
    
    # Broadcast update
    status = queue_worker.get_status()
    queue_events.broadcast({
        "type": "queue_updated",
        "pending": status["pending"],
        "processing": status["processing"],
        "added": added,
    })
    
    logger.info(f"Added {added} papers to queue, {already_queued} already queued")
    
    return AddToQueueResponse(
        message=f"Added {added} papers to queue" + (f", {already_queued} already queued" if already_queued else ""),
        added=added,
        already_queued=already_queued,
    )


@router.post("/add/{paper_id}", response_model=AddToQueueResponse)
async def add_single_to_queue(
    paper_id: int,
    priority: int = Query(5, ge=1, le=100),  # Single papers get higher priority by default
    db: Session = Depends(get_db),
):
    """Add a single paper to the assessment queue with high priority."""
    # Verify paper exists
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # Check if already in queue
    existing = db.query(AssessmentQueueItem).filter(
        AssessmentQueueItem.paper_id == paper_id,
        AssessmentQueueItem.status.in_([QueueStatus.PENDING, QueueStatus.PROCESSING])
    ).first()
    
    if existing:
        return AddToQueueResponse(
            message="Paper already in queue",
            added=0,
            already_queued=1,
        )
    
    # Add to queue with high priority
    item = AssessmentQueueItem(
        paper_id=paper_id,
        status=QueueStatus.PENDING,
        priority=priority,
    )
    db.add(item)
    db.commit()
    
    # Broadcast update
    status = queue_worker.get_status()
    queue_events.broadcast({
        "type": "queue_updated",
        "pending": status["pending"],
        "processing": status["processing"],
        "added": 1,
        "paper_id": paper_id,
        "paper_title": paper.title,
    })
    
    logger.info(f"Added paper {paper_id} to queue with priority {priority}")
    
    return AddToQueueResponse(
        message=f"Added paper to queue",
        added=1,
        already_queued=0,
    )


@router.delete("/clear", response_model=ClearQueueResponse)
async def clear_queue(
    status: Optional[str] = Query(None, description="Only clear items with this status"),
    db: Session = Depends(get_db),
):
    """Clear queue items. By default clears completed and failed items."""
    query = db.query(AssessmentQueueItem)
    
    if status:
        query = query.filter(AssessmentQueueItem.status == status)
    else:
        # Default: only clear completed and failed
        query = query.filter(
            AssessmentQueueItem.status.in_([QueueStatus.COMPLETED, QueueStatus.FAILED])
        )
    
    count = query.count()
    query.delete(synchronize_session=False)
    db.commit()
    
    # Broadcast update
    new_status = queue_worker.get_status()
    queue_events.broadcast({
        "type": "queue_cleared",
        "removed": count,
        "pending": new_status["pending"],
    })
    
    logger.info(f"Cleared {count} items from queue")
    
    return ClearQueueResponse(
        message=f"Cleared {count} items from queue",
        removed=count,
    )


@router.delete("/cancel/{item_id}")
async def cancel_queue_item(
    item_id: int,
    db: Session = Depends(get_db),
):
    """Cancel a pending queue item."""
    item = db.query(AssessmentQueueItem).filter(
        AssessmentQueueItem.id == item_id
    ).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    
    if item.status != QueueStatus.PENDING:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel item with status '{item.status}'"
        )
    
    db.delete(item)
    db.commit()
    
    # Broadcast update
    status = queue_worker.get_status()
    queue_events.broadcast({
        "type": "item_cancelled",
        "item_id": item_id,
        "paper_id": item.paper_id,
        "pending": status["pending"],
    })
    
    return {"message": "Queue item cancelled", "item_id": item_id}


@router.get("/stream")
async def queue_stream():
    """SSE stream for real-time queue updates."""
    async def generate():
        listener = queue_events.add_listener()
        try:
            # Send initial status
            status = queue_worker.get_status()
            yield f"data: {json.dumps({'type': 'status', **status})}\n\n"
            
            while True:
                try:
                    # Wait for events with timeout
                    event = await asyncio.wait_for(listener.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            queue_events.remove_listener(listener)
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )

