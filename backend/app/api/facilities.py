"""Facilities API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from ..database import get_db
from ..models import Facility, ExtractedEntity

router = APIRouter()


class FacilityCreate(BaseModel):
    """Schema for creating a facility."""
    name: str
    aliases: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    bsl_level: Optional[int] = None
    certifications: Optional[str] = None
    notes: Optional[str] = None
    verified: bool = False
    source_url: Optional[str] = None


class FacilityResponse(BaseModel):
    """Facility response schema."""
    id: int
    name: str
    aliases: Optional[str]
    country: Optional[str]
    city: Optional[str]
    address: Optional[str]
    bsl_level: Optional[int]
    certifications: Optional[str]
    notes: Optional[str]
    verified: bool
    source_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FacilityListResponse(BaseModel):
    """Paginated facility list response."""
    facilities: List[FacilityResponse]
    total: int
    page: int
    page_size: int


@router.get("/", response_model=FacilityListResponse)
async def list_facilities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    bsl_level: Optional[int] = None,
    country: Optional[str] = None,
    verified: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all facilities with pagination."""
    query = db.query(Facility)
    
    if bsl_level is not None:
        query = query.filter(Facility.bsl_level == bsl_level)
    if country:
        query = query.filter(Facility.country.ilike(f"%{country}%"))
    if verified is not None:
        query = query.filter(Facility.verified == verified)
    if search:
        query = query.filter(
            (Facility.name.ilike(f"%{search}%")) |
            (Facility.aliases.ilike(f"%{search}%"))
        )
    
    total = query.count()
    facilities = query.order_by(Facility.name).offset((page - 1) * page_size).limit(page_size).all()
    
    return FacilityListResponse(
        facilities=facilities,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{facility_id}", response_model=FacilityResponse)
async def get_facility(facility_id: int, db: Session = Depends(get_db)):
    """Get a single facility by ID."""
    facility = db.query(Facility).filter(Facility.id == facility_id).first()
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")
    return facility


@router.post("/", response_model=FacilityResponse)
async def create_facility(facility: FacilityCreate, db: Session = Depends(get_db)):
    """Create a new facility."""
    db_facility = Facility(**facility.model_dump())
    db.add(db_facility)
    db.commit()
    db.refresh(db_facility)
    return db_facility


@router.put("/{facility_id}", response_model=FacilityResponse)
async def update_facility(facility_id: int, facility: FacilityCreate, db: Session = Depends(get_db)):
    """Update a facility."""
    db_facility = db.query(Facility).filter(Facility.id == facility_id).first()
    if not db_facility:
        raise HTTPException(status_code=404, detail="Facility not found")
    
    for key, value in facility.model_dump().items():
        setattr(db_facility, key, value)
    
    db.commit()
    db.refresh(db_facility)
    return db_facility


@router.delete("/{facility_id}")
async def delete_facility(facility_id: int, db: Session = Depends(get_db)):
    """Delete a facility."""
    facility = db.query(Facility).filter(Facility.id == facility_id).first()
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")
    
    db.delete(facility)
    db.commit()
    return {"message": "Facility deleted"}


@router.get("/search/name")
async def search_facilities_by_name(
    name: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
):
    """Search facilities by name (fuzzy match)."""
    facilities = db.query(Facility).filter(
        (Facility.name.ilike(f"%{name}%")) |
        (Facility.aliases.ilike(f"%{name}%"))
    ).limit(10).all()
    
    return [FacilityResponse.model_validate(f) for f in facilities]


@router.get("/stats/summary")
async def get_facility_stats(db: Session = Depends(get_db)):
    """Get facility statistics."""
    total = db.query(Facility).count()
    verified = db.query(Facility).filter(Facility.verified == True).count()
    
    # Count by BSL level
    by_bsl = {}
    for level in [1, 2, 3, 4]:
        count = db.query(Facility).filter(Facility.bsl_level == level).count()
        if count > 0:
            by_bsl[f"BSL-{level}"] = count
    
    # Count by country (top 10)
    from sqlalchemy import func
    by_country = db.query(
        Facility.country,
        func.count(Facility.id)
    ).filter(Facility.country != None).group_by(Facility.country).order_by(func.count(Facility.id).desc()).limit(10).all()
    
    return {
        "total": total,
        "verified": verified,
        "unverified": total - verified,
        "by_bsl_level": by_bsl,
        "by_country": {country: count for country, count in by_country if country},
    }

