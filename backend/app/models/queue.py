"""Assessment queue model for managing background assessment jobs."""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class QueueStatus(str, Enum):
    """Status of a queue item."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AssessmentQueueItem(Base):
    """A queued assessment job."""
    
    __tablename__ = "assessment_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False, index=True)
    
    # Status tracking
    status = Column(String(20), default=QueueStatus.PENDING, nullable=False, index=True)
    
    # Priority (lower = higher priority, default 10)
    priority = Column(Integer, default=10, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Error info if failed
    error_message = Column(Text, nullable=True)
    
    # Result summary (for quick display without loading full assessment)
    result_grade = Column(String(1), nullable=True)
    result_score = Column(Integer, nullable=True)
    result_flagged = Column(Integer, nullable=True)  # 0 or 1
    
    # Relationship
    paper = relationship("Paper")
    
    def __repr__(self):
        return f"<QueueItem id={self.id} paper_id={self.paper_id} status={self.status}>"

