"""Reference assessments API endpoints for pipeline evaluation."""
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field
from datetime import datetime

from ..database import get_db
from ..models import ReferenceAssessment, Assessment, Paper


router = APIRouter()


# ============================================================================
# Pydantic Schemas
# ============================================================================

class FacilityInfo(BaseModel):
    """Facility information for reference assessment."""
    name: str
    bsl_level: str


class ReferenceAssessmentCreate(BaseModel):
    """Schema for creating a reference assessment."""
    paper_id: int
    created_by: Optional[str] = None
    overall_score: float = Field(ge=0, le=10)
    pathogen_score: float = Field(ge=0, le=10)
    gof_score: float = Field(ge=0, le=10)
    containment_score: float = Field(ge=0, le=10)
    dual_use_score: float = Field(ge=0, le=10)
    pathogens_identified: Optional[List[str]] = None
    research_facilities: Optional[List[FacilityInfo]] = None
    stated_bsl: Optional[str] = None
    notes: Optional[str] = None


class ReferenceAssessmentUpdate(BaseModel):
    """Schema for updating a reference assessment."""
    created_by: Optional[str] = None
    overall_score: Optional[float] = Field(None, ge=0, le=10)
    pathogen_score: Optional[float] = Field(None, ge=0, le=10)
    gof_score: Optional[float] = Field(None, ge=0, le=10)
    containment_score: Optional[float] = Field(None, ge=0, le=10)
    dual_use_score: Optional[float] = Field(None, ge=0, le=10)
    pathogens_identified: Optional[List[str]] = None
    research_facilities: Optional[List[FacilityInfo]] = None
    stated_bsl: Optional[str] = None
    notes: Optional[str] = None


class ReferenceAssessmentResponse(BaseModel):
    """Response schema for reference assessment."""
    id: int
    paper_id: int
    created_by: Optional[str]
    overall_score: float
    pathogen_score: float
    gof_score: float
    containment_score: float
    dual_use_score: float
    pathogens_identified: Optional[List[str]]
    research_facilities: Optional[List[FacilityInfo]]
    stated_bsl: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    # Paper info
    paper_title: Optional[str] = None
    paper_source: Optional[str] = None
    paper_external_id: Optional[str] = None

    class Config:
        from_attributes = True


class ScoreComparison(BaseModel):
    """Comparison of scores between AI and reference."""
    ai_score: float
    reference_score: float
    difference: float  # AI - Reference (positive = AI scored higher)
    absolute_error: float


class ComparisonResult(BaseModel):
    """Comparison result for a single paper."""
    paper_id: int
    paper_title: str
    ai_assessment_id: int
    reference_assessment_id: int
    # Score comparisons
    overall: ScoreComparison
    pathogen: ScoreComparison
    gof: ScoreComparison
    containment: ScoreComparison
    dual_use: ScoreComparison
    # Pathogen comparison
    pathogens_ai: List[str]
    pathogens_reference: List[str]
    pathogens_matched: List[str]
    pathogens_missed: List[str]  # In reference but not AI
    pathogens_extra: List[str]   # In AI but not reference
    pathogen_precision: float
    pathogen_recall: float
    pathogen_f1: float
    # Facility comparison
    facilities_ai: List[FacilityInfo]
    facilities_reference: List[FacilityInfo]
    facilities_matched: List[str]  # Names matched
    facilities_missed: List[str]
    facilities_extra: List[str]
    facility_precision: float
    facility_recall: float
    facility_f1: float
    # BSL comparison
    bsl_ai: Optional[str]
    bsl_reference: Optional[str]
    bsl_match: bool


class AggregateMetrics(BaseModel):
    """Aggregate metrics across all compared papers."""
    num_papers: int
    # Score metrics
    mean_absolute_error: dict  # {overall, pathogen, gof, containment, dual_use}
    mean_signed_error: dict    # Positive = AI scores higher on average
    score_correlation: dict    # Pearson correlation per category
    # Pathogen metrics
    avg_pathogen_precision: float
    avg_pathogen_recall: float
    avg_pathogen_f1: float
    # Facility metrics
    avg_facility_precision: float
    avg_facility_recall: float
    avg_facility_f1: float
    # BSL metrics
    bsl_accuracy: float  # % exact match


class FullComparisonResponse(BaseModel):
    """Full comparison response with individual and aggregate results."""
    comparisons: List[ComparisonResult]
    aggregate: AggregateMetrics


# ============================================================================
# Helper Functions
# ============================================================================

def _parse_json_field(field_value: Optional[str], default=None):
    """Parse JSON field from database."""
    if not field_value:
        return default if default is not None else []
    try:
        return json.loads(field_value)
    except json.JSONDecodeError:
        return default if default is not None else []


def _normalize_pathogen(name: str) -> str:
    """Normalize pathogen name for comparison."""
    return name.lower().strip()


def _normalize_facility(name: str) -> str:
    """Normalize facility name for comparison."""
    return name.lower().strip()


def _calculate_precision_recall_f1(predicted: set, actual: set) -> tuple:
    """Calculate precision, recall, and F1 score."""
    if not predicted and not actual:
        return 1.0, 1.0, 1.0
    if not predicted:
        return 0.0, 0.0, 0.0
    if not actual:
        return 0.0, 1.0, 0.0
    
    true_positives = len(predicted & actual)
    precision = true_positives / len(predicted) if predicted else 0.0
    recall = true_positives / len(actual) if actual else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return precision, recall, f1


def _extract_ai_bsl(rationale_str: Optional[str]) -> Optional[str]:
    """Extract stated BSL from AI assessment rationale."""
    if not rationale_str:
        return None
    try:
        rationale = json.loads(rationale_str)
        return rationale.get("containment_analysis", {}).get("stated_bsl")
    except (json.JSONDecodeError, AttributeError):
        return None


def _extract_ai_facilities(rationale_str: Optional[str]) -> List[FacilityInfo]:
    """Extract facilities from AI assessment rationale."""
    if not rationale_str:
        return []
    try:
        rationale = json.loads(rationale_str)
        facilities_raw = rationale.get("containment_analysis", {}).get("research_facilities", [])
        return [FacilityInfo(name=f.get("name", ""), bsl_level=f.get("bsl_level", "")) for f in facilities_raw]
    except (json.JSONDecodeError, AttributeError):
        return []


def _compare_single(ai: Assessment, ref: ReferenceAssessment, paper: Paper) -> ComparisonResult:
    """Compare a single AI assessment against reference."""
    # Score comparisons
    def make_score_comparison(ai_score: float, ref_score: float) -> ScoreComparison:
        diff = ai_score - ref_score
        return ScoreComparison(
            ai_score=ai_score,
            reference_score=ref_score,
            difference=diff,
            absolute_error=abs(diff)
        )
    
    # Parse pathogens
    ai_pathogens = _parse_json_field(ai.pathogens_identified, [])
    ref_pathogens = _parse_json_field(ref.pathogens_identified, [])
    
    ai_pathogens_norm = {_normalize_pathogen(p) for p in ai_pathogens}
    ref_pathogens_norm = {_normalize_pathogen(p) for p in ref_pathogens}
    
    matched_pathogens = ai_pathogens_norm & ref_pathogens_norm
    missed_pathogens = ref_pathogens_norm - ai_pathogens_norm
    extra_pathogens = ai_pathogens_norm - ref_pathogens_norm
    
    pathogen_precision, pathogen_recall, pathogen_f1 = _calculate_precision_recall_f1(
        ai_pathogens_norm, ref_pathogens_norm
    )
    
    # Parse facilities
    ai_facilities = _extract_ai_facilities(ai.rationale)
    ref_facilities = _parse_json_field(ref.research_facilities, [])
    ref_facilities = [FacilityInfo(**f) if isinstance(f, dict) else f for f in ref_facilities]
    
    ai_facility_names = {_normalize_facility(f.name) for f in ai_facilities}
    ref_facility_names = {_normalize_facility(f["name"] if isinstance(f, dict) else f.name) for f in ref_facilities}
    
    matched_facilities = ai_facility_names & ref_facility_names
    missed_facilities = ref_facility_names - ai_facility_names
    extra_facilities = ai_facility_names - ref_facility_names
    
    facility_precision, facility_recall, facility_f1 = _calculate_precision_recall_f1(
        ai_facility_names, ref_facility_names
    )
    
    # BSL comparison
    ai_bsl = _extract_ai_bsl(ai.rationale)
    ref_bsl = ref.stated_bsl
    bsl_match = (ai_bsl or "").lower() == (ref_bsl or "").lower()
    
    return ComparisonResult(
        paper_id=paper.id,
        paper_title=paper.title,
        ai_assessment_id=ai.id,
        reference_assessment_id=ref.id,
        overall=make_score_comparison(ai.overall_score, ref.overall_score),
        pathogen=make_score_comparison(ai.pathogen_score, ref.pathogen_score),
        gof=make_score_comparison(ai.gof_score, ref.gof_score),
        containment=make_score_comparison(ai.containment_score, ref.containment_score),
        dual_use=make_score_comparison(ai.dual_use_score, ref.dual_use_score),
        pathogens_ai=ai_pathogens,
        pathogens_reference=ref_pathogens,
        pathogens_matched=list(matched_pathogens),
        pathogens_missed=list(missed_pathogens),
        pathogens_extra=list(extra_pathogens),
        pathogen_precision=pathogen_precision,
        pathogen_recall=pathogen_recall,
        pathogen_f1=pathogen_f1,
        facilities_ai=ai_facilities,
        facilities_reference=ref_facilities if isinstance(ref_facilities, list) else [],
        facilities_matched=list(matched_facilities),
        facilities_missed=list(missed_facilities),
        facilities_extra=list(extra_facilities),
        facility_precision=facility_precision,
        facility_recall=facility_recall,
        facility_f1=facility_f1,
        bsl_ai=ai_bsl,
        bsl_reference=ref_bsl,
        bsl_match=bsl_match,
    )


def _calculate_aggregate(comparisons: List[ComparisonResult]) -> AggregateMetrics:
    """Calculate aggregate metrics from individual comparisons."""
    if not comparisons:
        return AggregateMetrics(
            num_papers=0,
            mean_absolute_error={"overall": 0, "pathogen": 0, "gof": 0, "containment": 0, "dual_use": 0},
            mean_signed_error={"overall": 0, "pathogen": 0, "gof": 0, "containment": 0, "dual_use": 0},
            score_correlation={"overall": 0, "pathogen": 0, "gof": 0, "containment": 0, "dual_use": 0},
            avg_pathogen_precision=0,
            avg_pathogen_recall=0,
            avg_pathogen_f1=0,
            avg_facility_precision=0,
            avg_facility_recall=0,
            avg_facility_f1=0,
            bsl_accuracy=0,
        )
    
    n = len(comparisons)
    
    # Score metrics
    categories = ["overall", "pathogen", "gof", "containment", "dual_use"]
    mae = {}
    mse = {}
    for cat in categories:
        errors = [getattr(c, cat).absolute_error for c in comparisons]
        signed_errors = [getattr(c, cat).difference for c in comparisons]
        mae[cat] = round(sum(errors) / n, 3)
        mse[cat] = round(sum(signed_errors) / n, 3)
    
    # Correlation (simplified - just Pearson if we have enough data)
    correlations = {}
    for cat in categories:
        ai_scores = [getattr(c, cat).ai_score for c in comparisons]
        ref_scores = [getattr(c, cat).reference_score for c in comparisons]
        if n > 1:
            # Calculate Pearson correlation
            ai_mean = sum(ai_scores) / n
            ref_mean = sum(ref_scores) / n
            numerator = sum((a - ai_mean) * (r - ref_mean) for a, r in zip(ai_scores, ref_scores))
            ai_std = (sum((a - ai_mean) ** 2 for a in ai_scores)) ** 0.5
            ref_std = (sum((r - ref_mean) ** 2 for r in ref_scores)) ** 0.5
            if ai_std > 0 and ref_std > 0:
                correlations[cat] = round(numerator / (ai_std * ref_std), 3)
            else:
                correlations[cat] = 0.0
        else:
            correlations[cat] = 0.0
    
    # Pathogen metrics
    avg_pathogen_precision = sum(c.pathogen_precision for c in comparisons) / n
    avg_pathogen_recall = sum(c.pathogen_recall for c in comparisons) / n
    avg_pathogen_f1 = sum(c.pathogen_f1 for c in comparisons) / n
    
    # Facility metrics
    avg_facility_precision = sum(c.facility_precision for c in comparisons) / n
    avg_facility_recall = sum(c.facility_recall for c in comparisons) / n
    avg_facility_f1 = sum(c.facility_f1 for c in comparisons) / n
    
    # BSL accuracy
    bsl_matches = sum(1 for c in comparisons if c.bsl_match)
    bsl_accuracy = bsl_matches / n
    
    return AggregateMetrics(
        num_papers=n,
        mean_absolute_error=mae,
        mean_signed_error=mse,
        score_correlation=correlations,
        avg_pathogen_precision=round(avg_pathogen_precision, 3),
        avg_pathogen_recall=round(avg_pathogen_recall, 3),
        avg_pathogen_f1=round(avg_pathogen_f1, 3),
        avg_facility_precision=round(avg_facility_precision, 3),
        avg_facility_recall=round(avg_facility_recall, 3),
        avg_facility_f1=round(avg_facility_f1, 3),
        bsl_accuracy=round(bsl_accuracy, 3),
    )


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/", response_model=ReferenceAssessmentResponse)
async def create_reference_assessment(
    data: ReferenceAssessmentCreate,
    db: Session = Depends(get_db),
):
    """Create a new reference (gold standard) assessment for a paper."""
    # Check paper exists
    paper = db.query(Paper).filter(Paper.id == data.paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # Check if reference already exists for this paper
    existing = db.query(ReferenceAssessment).filter(
        ReferenceAssessment.paper_id == data.paper_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"Reference assessment already exists for paper {data.paper_id}. Use PUT to update."
        )
    
    ref = ReferenceAssessment(
        paper_id=data.paper_id,
        created_by=data.created_by,
        overall_score=data.overall_score,
        pathogen_score=data.pathogen_score,
        gof_score=data.gof_score,
        containment_score=data.containment_score,
        dual_use_score=data.dual_use_score,
        pathogens_identified=json.dumps(data.pathogens_identified) if data.pathogens_identified else None,
        research_facilities=json.dumps([f.model_dump() for f in data.research_facilities]) if data.research_facilities else None,
        stated_bsl=data.stated_bsl,
        notes=data.notes,
    )
    
    db.add(ref)
    db.commit()
    db.refresh(ref)
    
    return ReferenceAssessmentResponse(
        id=ref.id,
        paper_id=ref.paper_id,
        created_by=ref.created_by,
        overall_score=ref.overall_score,
        pathogen_score=ref.pathogen_score,
        gof_score=ref.gof_score,
        containment_score=ref.containment_score,
        dual_use_score=ref.dual_use_score,
        pathogens_identified=_parse_json_field(ref.pathogens_identified),
        research_facilities=_parse_json_field(ref.research_facilities),
        stated_bsl=ref.stated_bsl,
        notes=ref.notes,
        created_at=ref.created_at,
        updated_at=ref.updated_at,
        paper_title=paper.title,
        paper_source=paper.source,
        paper_external_id=paper.external_id,
    )


@router.get("/", response_model=List[ReferenceAssessmentResponse])
async def list_reference_assessments(db: Session = Depends(get_db)):
    """List all reference assessments."""
    refs = db.query(ReferenceAssessment).join(Paper).all()
    
    return [
        ReferenceAssessmentResponse(
            id=ref.id,
            paper_id=ref.paper_id,
            created_by=ref.created_by,
            overall_score=ref.overall_score,
            pathogen_score=ref.pathogen_score,
            gof_score=ref.gof_score,
            containment_score=ref.containment_score,
            dual_use_score=ref.dual_use_score,
            pathogens_identified=_parse_json_field(ref.pathogens_identified),
            research_facilities=_parse_json_field(ref.research_facilities),
            stated_bsl=ref.stated_bsl,
            notes=ref.notes,
            created_at=ref.created_at,
            updated_at=ref.updated_at,
            paper_title=ref.paper.title,
            paper_source=ref.paper.source,
            paper_external_id=ref.paper.external_id,
        )
        for ref in refs
    ]


@router.get("/paper/{paper_id}", response_model=ReferenceAssessmentResponse)
async def get_reference_for_paper(paper_id: int, db: Session = Depends(get_db)):
    """Get the reference assessment for a specific paper."""
    ref = db.query(ReferenceAssessment).filter(
        ReferenceAssessment.paper_id == paper_id
    ).first()
    
    if not ref:
        raise HTTPException(status_code=404, detail="No reference assessment for this paper")
    
    paper = ref.paper
    
    return ReferenceAssessmentResponse(
        id=ref.id,
        paper_id=ref.paper_id,
        created_by=ref.created_by,
        overall_score=ref.overall_score,
        pathogen_score=ref.pathogen_score,
        gof_score=ref.gof_score,
        containment_score=ref.containment_score,
        dual_use_score=ref.dual_use_score,
        pathogens_identified=_parse_json_field(ref.pathogens_identified),
        research_facilities=_parse_json_field(ref.research_facilities),
        stated_bsl=ref.stated_bsl,
        notes=ref.notes,
        created_at=ref.created_at,
        updated_at=ref.updated_at,
        paper_title=paper.title,
        paper_source=paper.source,
        paper_external_id=paper.external_id,
    )


@router.put("/paper/{paper_id}", response_model=ReferenceAssessmentResponse)
async def update_reference_assessment(
    paper_id: int,
    data: ReferenceAssessmentUpdate,
    db: Session = Depends(get_db),
):
    """Update (or create) a reference assessment for a paper."""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    ref = db.query(ReferenceAssessment).filter(
        ReferenceAssessment.paper_id == paper_id
    ).first()
    
    if not ref:
        # Create new if doesn't exist
        ref = ReferenceAssessment(paper_id=paper_id)
        db.add(ref)
    
    # Update fields if provided
    if data.created_by is not None:
        ref.created_by = data.created_by
    if data.overall_score is not None:
        ref.overall_score = data.overall_score
    if data.pathogen_score is not None:
        ref.pathogen_score = data.pathogen_score
    if data.gof_score is not None:
        ref.gof_score = data.gof_score
    if data.containment_score is not None:
        ref.containment_score = data.containment_score
    if data.dual_use_score is not None:
        ref.dual_use_score = data.dual_use_score
    if data.pathogens_identified is not None:
        ref.pathogens_identified = json.dumps(data.pathogens_identified)
    if data.research_facilities is not None:
        ref.research_facilities = json.dumps([f.model_dump() for f in data.research_facilities])
    if data.stated_bsl is not None:
        ref.stated_bsl = data.stated_bsl
    if data.notes is not None:
        ref.notes = data.notes
    
    db.commit()
    db.refresh(ref)
    
    return ReferenceAssessmentResponse(
        id=ref.id,
        paper_id=ref.paper_id,
        created_by=ref.created_by,
        overall_score=ref.overall_score,
        pathogen_score=ref.pathogen_score,
        gof_score=ref.gof_score,
        containment_score=ref.containment_score,
        dual_use_score=ref.dual_use_score,
        pathogens_identified=_parse_json_field(ref.pathogens_identified),
        research_facilities=_parse_json_field(ref.research_facilities),
        stated_bsl=ref.stated_bsl,
        notes=ref.notes,
        created_at=ref.created_at,
        updated_at=ref.updated_at,
        paper_title=paper.title,
        paper_source=paper.source,
        paper_external_id=paper.external_id,
    )


@router.delete("/paper/{paper_id}")
async def delete_reference_assessment(paper_id: int, db: Session = Depends(get_db)):
    """Delete the reference assessment for a paper."""
    ref = db.query(ReferenceAssessment).filter(
        ReferenceAssessment.paper_id == paper_id
    ).first()
    
    if not ref:
        raise HTTPException(status_code=404, detail="No reference assessment for this paper")
    
    db.delete(ref)
    db.commit()
    
    return {"message": f"Reference assessment deleted for paper {paper_id}"}


@router.get("/compare", response_model=FullComparisonResponse)
async def compare_assessments(db: Session = Depends(get_db)):
    """Compare all AI assessments against their reference assessments."""
    # Get all papers with both AI and reference assessments
    refs = db.query(ReferenceAssessment).all()
    
    comparisons = []
    for ref in refs:
        # Get the latest AI assessment for this paper
        ai_assessment = db.query(Assessment).filter(
            Assessment.paper_id == ref.paper_id
        ).order_by(Assessment.assessed_at.desc()).first()
        
        if not ai_assessment:
            continue  # Skip papers without AI assessment
        
        paper = ref.paper
        comparison = _compare_single(ai_assessment, ref, paper)
        comparisons.append(comparison)
    
    aggregate = _calculate_aggregate(comparisons)
    
    return FullComparisonResponse(
        comparisons=comparisons,
        aggregate=aggregate,
    )


@router.get("/compare/paper/{paper_id}", response_model=ComparisonResult)
async def compare_single_paper(paper_id: int, db: Session = Depends(get_db)):
    """Compare AI assessment against reference for a single paper."""
    ref = db.query(ReferenceAssessment).filter(
        ReferenceAssessment.paper_id == paper_id
    ).first()
    
    if not ref:
        raise HTTPException(status_code=404, detail="No reference assessment for this paper")
    
    ai_assessment = db.query(Assessment).filter(
        Assessment.paper_id == paper_id
    ).order_by(Assessment.assessed_at.desc()).first()
    
    if not ai_assessment:
        raise HTTPException(status_code=404, detail="No AI assessment for this paper")
    
    paper = ref.paper
    return _compare_single(ai_assessment, ref, paper)

