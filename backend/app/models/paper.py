"""Paper model for storing fetched research papers."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum
from sqlalchemy.orm import relationship
import enum

from ..database import Base


class PaperSource(str, enum.Enum):
    """Source of the paper."""
    ARXIV = "arxiv"
    BIORXIV = "biorxiv"
    MEDRXIV = "medrxiv"
    PUBMED = "pubmed"


class Paper(Base):
    """Research paper from various sources."""
    
    __tablename__ = "papers"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Source identification
    source = Column(String(20), nullable=False, index=True)
    external_id = Column(String(100), nullable=False, index=True)  # arXiv ID, DOI, PMID
    
    # Paper metadata
    title = Column(Text, nullable=False)
    authors = Column(Text, nullable=False)  # JSON array of author names
    affiliations = Column(Text, nullable=True)  # JSON array of institutional affiliations
    abstract = Column(Text, nullable=True)
    full_text = Column(Text, nullable=True)  # If available
    
    # URLs
    url = Column(String(500), nullable=True)
    pdf_url = Column(String(500), nullable=True)
    
    # Dates
    published_date = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Processing status
    processed = Column(Boolean, default=False, index=True)
    
    # Categories/keywords from source
    categories = Column(Text, nullable=True)  # JSON array
    
    # Relationships
    assessments = relationship("Assessment", back_populates="paper", cascade="all, delete-orphan")
    entities = relationship("ExtractedEntity", back_populates="paper", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Paper {self.source}:{self.external_id} - {self.title[:50]}...>"

