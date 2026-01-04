"""Reference (gold standard) assessment model for pipeline evaluation."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class ReferenceAssessment(Base):
    """Human-written gold standard assessment for evaluating pipeline accuracy."""
    
    __tablename__ = "reference_assessments"
    
    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False, unique=True, index=True)
    
    # Who created this reference assessment
    created_by = Column(String(100), nullable=True)
    
    # Scores (0-10 scale, matching AI assessment)
    overall_score = Column(Float, nullable=False)
    pathogen_score = Column(Float, nullable=False)
    gof_score = Column(Float, nullable=False)
    containment_score = Column(Float, nullable=False)
    dual_use_score = Column(Float, nullable=False)
    
    # Pathogens identified (JSON array of strings)
    # e.g. ["SARS-CoV-2", "Influenza A H5N1"]
    pathogens_identified = Column(Text, nullable=True)
    
    # Research facilities (JSON array of objects)
    # e.g. [{"name": "Wuhan Institute of Virology", "bsl_level": "BSL-4"}]
    research_facilities = Column(Text, nullable=True)
    
    # Stated BSL level for the research
    # e.g. "BSL-2", "BSL-3", "Unknown"
    stated_bsl = Column(String(20), nullable=True)
    
    # Notes/reasoning for the human assessment
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship
    paper = relationship("Paper", back_populates="reference_assessment")
    
    def __repr__(self):
        return f"<ReferenceAssessment paper_id={self.paper_id} score={self.overall_score}>"

