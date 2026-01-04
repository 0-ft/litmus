"""Background worker for processing the assessment queue."""
import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import AssessmentQueueItem, QueueStatus, Paper, Assessment
from .analysis import BiosecurityAssessor

logger = logging.getLogger(__name__)


class QueueEventManager:
    """Manages SSE connections for queue updates."""
    
    def __init__(self):
        self._listeners: List[asyncio.Queue] = []
        self._lock = threading.Lock()
    
    def add_listener(self) -> asyncio.Queue:
        """Add a new listener and return their queue."""
        queue = asyncio.Queue()
        with self._lock:
            self._listeners.append(queue)
        return queue
    
    def remove_listener(self, queue: asyncio.Queue):
        """Remove a listener."""
        with self._lock:
            if queue in self._listeners:
                self._listeners.remove(queue)
    
    def broadcast(self, event: Dict[str, Any]):
        """Broadcast an event to all listeners."""
        with self._lock:
            for listener in self._listeners:
                try:
                    listener.put_nowait(event)
                except asyncio.QueueFull:
                    pass  # Skip if queue is full


# Global event manager
queue_events = QueueEventManager()


class QueueWorker:
    """Background worker that processes the assessment queue."""
    
    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_item_id: Optional[int] = None
    
    def start(self):
        """Start the background worker."""
        if self._running:
            logger.warning("Queue worker already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Queue worker started")
    
    def stop(self):
        """Stop the background worker."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("Queue worker stopped")
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def current_item_id(self) -> Optional[int]:
        return self._current_item_id
    
    def _run(self):
        """Main worker loop."""
        logger.info("Queue worker loop started")
        
        while self._running:
            try:
                self._process_next()
            except Exception as e:
                logger.error(f"Error in queue worker: {e}")
            
            # Sleep between checks
            time.sleep(self.poll_interval)
        
        logger.info("Queue worker loop ended")
    
    def _process_next(self):
        """Process the next item in the queue."""
        db = SessionLocal()
        try:
            # Get next pending item (ordered by priority, then created_at)
            item = db.query(AssessmentQueueItem).filter(
                AssessmentQueueItem.status == QueueStatus.PENDING
            ).order_by(
                AssessmentQueueItem.priority,
                AssessmentQueueItem.created_at
            ).first()
            
            if not item:
                return  # No pending items
            
            # Mark as processing
            item.status = QueueStatus.PROCESSING
            item.started_at = datetime.utcnow()
            db.commit()
            
            self._current_item_id = item.id
            
            # Broadcast status update
            paper = db.query(Paper).filter(Paper.id == item.paper_id).first()
            queue_events.broadcast({
                "type": "processing",
                "item_id": item.id,
                "paper_id": item.paper_id,
                "paper_title": paper.title if paper else "Unknown",
                "status": "processing",
            })
            
            logger.info(f"Processing queue item {item.id} (paper {item.paper_id})")
            
            # Run assessment
            try:
                assessor = BiosecurityAssessor(db)
                assessment = assessor.assess_paper(paper)
                
                if assessment:
                    # Update queue item with results
                    item.status = QueueStatus.COMPLETED
                    item.completed_at = datetime.utcnow()
                    item.result_grade = assessment.risk_grade
                    item.result_score = int(assessment.overall_score)
                    item.result_flagged = 1 if assessment.flagged else 0
                    db.commit()
                    
                    # Broadcast completion
                    queue_events.broadcast({
                        "type": "completed",
                        "item_id": item.id,
                        "paper_id": item.paper_id,
                        "paper_title": paper.title if paper else "Unknown",
                        "status": "completed",
                        "risk_grade": assessment.risk_grade,
                        "overall_score": assessment.overall_score,
                        "flagged": assessment.flagged,
                        "concerns_summary": assessment.concerns_summary,
                    })
                    
                    logger.info(f"Completed queue item {item.id}: grade={assessment.risk_grade}")
                else:
                    raise Exception("Assessment returned None")
                    
            except Exception as e:
                # Mark as failed
                item.status = QueueStatus.FAILED
                item.completed_at = datetime.utcnow()
                item.error_message = str(e)[:500]  # Truncate long errors
                db.commit()
                
                # Broadcast failure
                queue_events.broadcast({
                    "type": "failed",
                    "item_id": item.id,
                    "paper_id": item.paper_id,
                    "paper_title": paper.title if paper else "Unknown",
                    "status": "failed",
                    "error": str(e)[:200],
                })
                
                logger.error(f"Failed queue item {item.id}: {e}")
            
            self._current_item_id = None
            
        finally:
            db.close()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        db = SessionLocal()
        try:
            pending = db.query(AssessmentQueueItem).filter(
                AssessmentQueueItem.status == QueueStatus.PENDING
            ).count()
            
            processing = db.query(AssessmentQueueItem).filter(
                AssessmentQueueItem.status == QueueStatus.PROCESSING
            ).count()
            
            completed = db.query(AssessmentQueueItem).filter(
                AssessmentQueueItem.status == QueueStatus.COMPLETED
            ).count()
            
            failed = db.query(AssessmentQueueItem).filter(
                AssessmentQueueItem.status == QueueStatus.FAILED
            ).count()
            
            # Get current processing item
            current = None
            if self._current_item_id:
                item = db.query(AssessmentQueueItem).filter(
                    AssessmentQueueItem.id == self._current_item_id
                ).first()
                if item:
                    paper = item.paper
                    current = {
                        "item_id": item.id,
                        "paper_id": item.paper_id,
                        "paper_title": paper.title if paper else "Unknown",
                        "started_at": item.started_at.isoformat() if item.started_at else None,
                    }
            
            return {
                "worker_running": self._running,
                "pending": pending,
                "processing": processing,
                "completed": completed,
                "failed": failed,
                "total": pending + processing + completed + failed,
                "current": current,
            }
        finally:
            db.close()


# Global worker instance
queue_worker = QueueWorker()

