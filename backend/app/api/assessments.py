"""Assessments API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from ..database import get_db
from ..models import Assessment, Paper

router = APIRouter()


class AssessmentResponse(BaseModel):
    """Assessment response schema."""
    id: int
    paper_id: int
    risk_grade: str
    overall_score: float
    pathogen_score: float
    gof_score: float
    containment_score: float
    dual_use_score: float
    rationale: str
    concerns_summary: Optional[str]
    pathogens_identified: Optional[str]
    flagged: bool
    flag_reason: Optional[str]
    assessed_at: datetime
    model_version: Optional[str]

    class Config:
        from_attributes = True


class AssessmentWithPaperResponse(AssessmentResponse):
    """Assessment with paper info."""
    paper_title: str
    paper_source: str
    paper_external_id: str


class AssessmentListResponse(BaseModel):
    """Paginated assessment list response."""
    assessments: List[AssessmentWithPaperResponse]
    total: int
    page: int
    page_size: int


@router.get("/", response_model=AssessmentListResponse)
async def list_assessments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    risk_grade: Optional[str] = None,
    flagged: Optional[bool] = None,
    min_score: Optional[float] = None,
    db: Session = Depends(get_db),
):
    """List all assessments with pagination."""
    query = db.query(Assessment).join(Paper)
    
    if risk_grade:
        query = query.filter(Assessment.risk_grade == risk_grade.upper())
    if flagged is not None:
        query = query.filter(Assessment.flagged == flagged)
    if min_score is not None:
        query = query.filter(Assessment.overall_score >= min_score)
    
    total = query.count()
    results = query.order_by(Assessment.overall_score.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    assessments = []
    for assessment in results:
        paper = assessment.paper
        assessments.append(AssessmentWithPaperResponse(
            id=assessment.id,
            paper_id=assessment.paper_id,
            risk_grade=assessment.risk_grade,
            overall_score=assessment.overall_score,
            pathogen_score=assessment.pathogen_score,
            gof_score=assessment.gof_score,
            containment_score=assessment.containment_score,
            dual_use_score=assessment.dual_use_score,
            rationale=assessment.rationale,
            concerns_summary=assessment.concerns_summary,
            pathogens_identified=assessment.pathogens_identified,
            flagged=assessment.flagged,
            flag_reason=assessment.flag_reason,
            assessed_at=assessment.assessed_at,
            model_version=assessment.model_version,
            paper_title=paper.title,
            paper_source=paper.source,
            paper_external_id=paper.external_id,
        ))
    
    return AssessmentListResponse(
        assessments=assessments,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/flagged", response_model=List[AssessmentWithPaperResponse])
async def get_flagged_assessments(db: Session = Depends(get_db)):
    """Get all flagged assessments (high-risk papers)."""
    results = db.query(Assessment).join(Paper).filter(Assessment.flagged == True).order_by(Assessment.overall_score.desc()).all()
    
    assessments = []
    for assessment in results:
        paper = assessment.paper
        assessments.append(AssessmentWithPaperResponse(
            id=assessment.id,
            paper_id=assessment.paper_id,
            risk_grade=assessment.risk_grade,
            overall_score=assessment.overall_score,
            pathogen_score=assessment.pathogen_score,
            gof_score=assessment.gof_score,
            containment_score=assessment.containment_score,
            dual_use_score=assessment.dual_use_score,
            rationale=assessment.rationale,
            concerns_summary=assessment.concerns_summary,
            pathogens_identified=assessment.pathogens_identified,
            flagged=assessment.flagged,
            flag_reason=assessment.flag_reason,
            assessed_at=assessment.assessed_at,
            model_version=assessment.model_version,
            paper_title=paper.title,
            paper_source=paper.source,
            paper_external_id=paper.external_id,
        ))
    
    return assessments


@router.get("/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(assessment_id: int, db: Session = Depends(get_db)):
    """Get a single assessment by ID."""
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment


@router.get("/paper/{paper_id}", response_model=List[AssessmentResponse])
async def get_paper_assessments(paper_id: int, db: Session = Depends(get_db)):
    """Get all assessments for a paper."""
    assessments = db.query(Assessment).filter(Assessment.paper_id == paper_id).all()
    return assessments


@router.get("/stats/summary")
async def get_assessment_stats(db: Session = Depends(get_db)):
    """Get assessment statistics."""
    total = db.query(Assessment).count()
    flagged = db.query(Assessment).filter(Assessment.flagged == True).count()
    
    # Count by grade
    by_grade = {}
    for grade in ["A", "B", "C", "D", "F"]:
        count = db.query(Assessment).filter(Assessment.risk_grade == grade).count()
        by_grade[grade] = count
    
    # Average scores
    from sqlalchemy import func
    avg_scores = db.query(
        func.avg(Assessment.overall_score),
        func.avg(Assessment.pathogen_score),
        func.avg(Assessment.gof_score),
        func.avg(Assessment.containment_score),
        func.avg(Assessment.dual_use_score),
    ).first()
    
    return {
        "total": total,
        "flagged": flagged,
        "by_grade": by_grade,
        "average_scores": {
            "overall": round(avg_scores[0] or 0, 2),
            "pathogen": round(avg_scores[1] or 0, 2),
            "gof": round(avg_scores[2] or 0, 2),
            "containment": round(avg_scores[3] or 0, 2),
            "dual_use": round(avg_scores[4] or 0, 2),
        } if avg_scores[0] else None,
    }

