"""Facility and extracted entity models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class Facility(Base):
    """BSL facility for containment level verification."""
    
    __tablename__ = "facilities"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Identification
    name = Column(String(500), nullable=False, index=True)
    aliases = Column(Text, nullable=True)  # JSON array of alternative names
    
    # Location
    country = Column(String(100), nullable=True, index=True)
    city = Column(String(200), nullable=True)
    address = Column(Text, nullable=True)
    
    # BSL classification
    bsl_level = Column(Integer, nullable=True, index=True)  # 1, 2, 3, or 4
    
    # Additional info
    certifications = Column(Text, nullable=True)  # JSON array
    notes = Column(Text, nullable=True)
    
    # Data quality
    verified = Column(Boolean, default=False)
    source_url = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    entities = relationship("ExtractedEntity", back_populates="facility")
    
    def __repr__(self):
        return f"<Facility {self.name} BSL-{self.bsl_level}>"


class ExtractedEntity(Base):
    """Entities extracted from papers (facilities, pathogens, techniques)."""
    
    __tablename__ = "extracted_entities"
    
    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False, index=True)
    
    # Entity details
    entity_type = Column(String(50), nullable=False, index=True)  # facility, pathogen, technique
    entity_value = Column(Text, nullable=False)
    
    # Optional link to facility if matched
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=True, index=True)
    
    # Confidence of extraction (0-1)
    confidence = Column(Integer, nullable=True)
    
    # Context where entity was found
    context = Column(Text, nullable=True)
    
    # Timestamps
    extracted_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    paper = relationship("Paper", back_populates="entities")
    facility = relationship("Facility", back_populates="entities")
    
    def __repr__(self):
        return f"<ExtractedEntity {self.entity_type}: {self.entity_value[:50]}>"

