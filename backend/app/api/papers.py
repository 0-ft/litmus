"""Papers API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from ..database import get_db
from ..models import Paper

router = APIRouter()


class PaperResponse(BaseModel):
    """Paper response schema."""
    id: int
    source: str
    external_id: str
    title: str
    authors: str
    abstract: Optional[str]
    url: Optional[str]
    published_date: Optional[datetime]
    fetched_at: datetime
    processed: bool
    categories: Optional[str]

    class Config:
        from_attributes = True


class PaperListResponse(BaseModel):
    """Paginated paper list response."""
    papers: List[PaperResponse]
    total: int
    page: int
    page_size: int


@router.get("/", response_model=PaperListResponse)
async def list_papers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source: Optional[str] = None,
    processed: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """List all papers with pagination."""
    query = db.query(Paper)
    
    if source:
        query = query.filter(Paper.source == source)
    if processed is not None:
        query = query.filter(Paper.processed == processed)
    
    total = query.count()
    papers = query.order_by(Paper.fetched_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return PaperListResponse(
        papers=papers,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(paper_id: int, db: Session = Depends(get_db)):
    """Get a single paper by ID."""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@router.delete("/{paper_id}")
async def delete_paper(paper_id: int, db: Session = Depends(get_db)):
    """Delete a paper."""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    db.delete(paper)
    db.commit()
    return {"message": "Paper deleted"}


@router.get("/stats/summary")
async def get_paper_stats(db: Session = Depends(get_db)):
    """Get paper statistics."""
    total = db.query(Paper).count()
    processed = db.query(Paper).filter(Paper.processed == True).count()
    unprocessed = db.query(Paper).filter(Paper.processed == False).count()
    
    # Count by source
    by_source = {}
    for source in ["arxiv", "biorxiv", "medrxiv", "pubmed"]:
        count = db.query(Paper).filter(Paper.source == source).count()
        if count > 0:
            by_source[source] = count
    
    return {
        "total": total,
        "processed": processed,
        "unprocessed": unprocessed,
        "by_source": by_source,
    }

