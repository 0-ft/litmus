"""Scan and assessment API endpoints."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..scrapers import ArxivScraper, BiorxivScraper, PubmedScraper
from ..analysis import BiosecurityAssessor
from ..research import FacilityResearcher
from ..config import settings

router = APIRouter()


class ScanResponse(BaseModel):
    """Response for scan operations."""
    message: str
    papers_fetched: int = 0
    source: str = ""


class AssessResponse(BaseModel):
    """Response for assessment operations."""
    message: str
    papers_assessed: int = 0
    flagged: int = 0


class FacilityResearchResponse(BaseModel):
    """Response for facility research operations."""
    message: str
    facility_name: str
    found: bool
    facility_id: Optional[int] = None
    bsl_level: Optional[int] = None
    confidence: Optional[str] = None


@router.post("/arxiv", response_model=ScanResponse)
async def scan_arxiv(
    max_results: int = 100,
    use_terms: bool = True,
    db: Session = Depends(get_db),
):
    """Scan arXiv for new biology papers."""
    scraper = ArxivScraper(db)
    count = scraper.fetch_and_store(max_results=max_results, use_terms=use_terms)
    
    return ScanResponse(
        message=f"Scanned arXiv, fetched {count} new papers",
        papers_fetched=count,
        source="arxiv",
    )


@router.post("/biorxiv", response_model=ScanResponse)
async def scan_biorxiv(
    max_results: int = 100,
    days_back: int = 7,
    db: Session = Depends(get_db),
):
    """Scan bioRxiv for new biology papers."""
    scraper = BiorxivScraper(db)
    count = scraper.fetch_and_store(max_results=max_results, days_back=days_back)
    
    return ScanResponse(
        message=f"Scanned bioRxiv, fetched {count} new papers",
        papers_fetched=count,
        source="biorxiv",
    )


@router.post("/pubmed", response_model=ScanResponse)
async def scan_pubmed(
    max_results: int = 100,
    days_back: int = 7,
    db: Session = Depends(get_db),
):
    """Scan PubMed for new biology papers."""
    scraper = PubmedScraper(db)
    count = scraper.fetch_and_store(max_results=max_results, days_back=days_back)
    
    return ScanResponse(
        message=f"Scanned PubMed, fetched {count} new papers",
        papers_fetched=count,
        source="pubmed",
    )


@router.post("/all", response_model=ScanResponse)
async def scan_all_sources(
    max_results_per_source: int = 50,
    db: Session = Depends(get_db),
):
    """Scan all paper sources."""
    total = 0
    
    # arXiv
    try:
        arxiv_scraper = ArxivScraper(db)
        total += arxiv_scraper.fetch_and_store(max_results=max_results_per_source)
    except Exception as e:
        print(f"arXiv scan error: {e}")
    
    # bioRxiv
    try:
        biorxiv_scraper = BiorxivScraper(db)
        total += biorxiv_scraper.fetch_and_store(max_results=max_results_per_source)
    except Exception as e:
        print(f"bioRxiv scan error: {e}")
    
    # PubMed
    try:
        pubmed_scraper = PubmedScraper(db)
        total += pubmed_scraper.fetch_and_store(max_results=max_results_per_source)
    except Exception as e:
        print(f"PubMed scan error: {e}")
    
    return ScanResponse(
        message=f"Scanned all sources, fetched {total} new papers",
        papers_fetched=total,
        source="all",
    )


@router.post("/assess", response_model=AssessResponse)
async def assess_papers(
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """Assess unprocessed papers for biosecurity risks."""
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=400,
            detail="Anthropic API key not configured. Set ANTHROPIC_API_KEY environment variable."
        )
    
    assessor = BiosecurityAssessor(db)
    assessments = assessor.assess_unprocessed_papers(limit=limit)
    
    flagged_count = sum(1 for a in assessments if a.flagged)
    
    return AssessResponse(
        message=f"Assessed {len(assessments)} papers, {flagged_count} flagged",
        papers_assessed=len(assessments),
        flagged=flagged_count,
    )


@router.post("/research-facility", response_model=FacilityResearchResponse)
async def research_facility_endpoint(
    facility_name: str,
    db: Session = Depends(get_db),
):
    """Research a facility by name using web search."""
    if not settings.tavily_api_key:
        raise HTTPException(
            status_code=400,
            detail="Tavily API key not configured. Set TAVILY_API_KEY environment variable."
        )
    
    researcher = FacilityResearcher(db)
    result = researcher.research_facility(facility_name)
    
    if result:
        return FacilityResearchResponse(
            message=f"Found information for {facility_name}",
            facility_name=facility_name,
            found=True,
            facility_id=result.get("facility_id"),
            bsl_level=result.get("bsl_level"),
            confidence=result.get("confidence"),
        )
    else:
        return FacilityResearchResponse(
            message=f"Could not find verified information for {facility_name}",
            facility_name=facility_name,
            found=False,
        )

