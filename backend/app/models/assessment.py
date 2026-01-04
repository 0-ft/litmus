"""Assessment model for biosecurity risk analysis results."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float
from sqlalchemy.orm import relationship

from ..database import Base


class Assessment(Base):
    """Biosecurity risk assessment for a paper."""
    
    __tablename__ = "assessments"
    
    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False, index=True)
    
    # Risk grade (A=lowest risk through F=highest concern)
    risk_grade = Column(String(1), nullable=False, index=True)
    
    # Individual scores (0-10)
    overall_score = Column(Float, nullable=False, index=True)
    pathogen_score = Column(Float, nullable=False)
    gof_score = Column(Float, nullable=False)  # Gain-of-function
    containment_score = Column(Float, nullable=False)
    dual_use_score = Column(Float, nullable=False)
    
    # Detailed rationale (JSON with explanations for each category)
    rationale = Column(Text, nullable=False)
    
    # Identified concerns summary
    concerns_summary = Column(Text, nullable=True)
    
    # Pathogens identified (JSON array)
    pathogens_identified = Column(Text, nullable=True)
    
    # Flagged for human review
    flagged = Column(Boolean, default=False, index=True)
    flag_reason = Column(Text, nullable=True)
    
    # Timestamps
    assessed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Model used for assessment
    model_version = Column(String(50), nullable=True)
    
    # Debug/trace information
    input_prompt = Column(Text, nullable=True)  # Full prompt sent to model
    raw_output = Column(Text, nullable=True)    # Raw model response
    
    # Relationship
    paper = relationship("Paper", back_populates="assessments")
    
    def __repr__(self):
        return f"<Assessment paper_id={self.paper_id} grade={self.risk_grade} score={self.overall_score}>"
    
    @staticmethod
    def score_to_grade(score: float) -> str:
        """Convert numeric score (0-10) to letter grade."""
        if score < 2:
            return "A"
        elif score < 4:
            return "B"
        elif score < 6:
            return "C"
        elif score < 8:
            return "D"
        else:
            return "F"

