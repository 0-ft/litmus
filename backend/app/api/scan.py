"""Scan and assessment API endpoints."""
import json
import asyncio
import logging
from typing import Optional, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import not_
from pydantic import BaseModel

from ..database import get_db, SessionLocal
from ..scrapers import ArxivScraper, BiorxivScraper, PubmedScraper
from ..analysis import BiosecurityAssessor
from ..research import FacilityResearcher
from ..config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    use_terms: bool = False,  # Disable term search by default - too slow
    db: Session = Depends(get_db),
):
    """Scan arXiv for new biology papers."""
    logger.info(f"Starting arXiv scan: max_results={max_results}, use_terms={use_terms}")
    try:
        scraper = ArxivScraper(db)
        logger.info("ArxivScraper initialized, starting fetch...")
        count = scraper.fetch_and_store(max_results=max_results, use_terms=use_terms)
        logger.info(f"arXiv scan complete: {count} papers fetched")
        
        return ScanResponse(
            message=f"Scanned arXiv, fetched {count} new papers",
            papers_fetched=count,
            source="arxiv",
        )
    except Exception as e:
        logger.error(f"arXiv scan error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"arXiv scan failed: {str(e)}")


@router.post("/biorxiv", response_model=ScanResponse)
async def scan_biorxiv(
    max_results: int = 100,
    days_back: int = 7,
    db: Session = Depends(get_db),
):
    """Scan bioRxiv for new biology papers."""
    logger.info(f"Starting bioRxiv scan: max_results={max_results}, days_back={days_back}")
    try:
        scraper = BiorxivScraper(db)
        count = scraper.fetch_and_store(max_results=max_results, days_back=days_back)
        logger.info(f"bioRxiv scan complete: {count} papers fetched")
        
        return ScanResponse(
            message=f"Scanned bioRxiv, fetched {count} new papers",
            papers_fetched=count,
            source="biorxiv",
        )
    except Exception as e:
        logger.error(f"bioRxiv scan error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"bioRxiv scan failed: {str(e)}")


@router.post("/pubmed", response_model=ScanResponse)
async def scan_pubmed(
    max_results: int = 100,
    days_back: int = 7,
    db: Session = Depends(get_db),
):
    """Scan PubMed for new biology papers."""
    logger.info(f"Starting PubMed scan: max_results={max_results}, days_back={days_back}")
    try:
        scraper = PubmedScraper(db)
        count = scraper.fetch_and_store(max_results=max_results, days_back=days_back)
        logger.info(f"PubMed scan complete: {count} papers fetched")
        
        return ScanResponse(
            message=f"Scanned PubMed, fetched {count} new papers",
            papers_fetched=count,
            source="pubmed",
        )
    except Exception as e:
        logger.error(f"PubMed scan error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PubMed scan failed: {str(e)}")


def _run_scan_all(max_results_per_source: int):
    """Background task to scan all sources."""
    from ..database import SessionLocal
    db = SessionLocal()
    total = 0
    
    try:
        # arXiv
        try:
            print("Scanning arXiv...")
            arxiv_scraper = ArxivScraper(db)
            count = arxiv_scraper.fetch_and_store(max_results=max_results_per_source)
            total += count
            print(f"arXiv: fetched {count} papers")
        except Exception as e:
            print(f"arXiv scan error: {e}")
        
        # bioRxiv
        try:
            print("Scanning bioRxiv...")
            biorxiv_scraper = BiorxivScraper(db)
            count = biorxiv_scraper.fetch_and_store(max_results=max_results_per_source)
            total += count
            print(f"bioRxiv: fetched {count} papers")
        except Exception as e:
            print(f"bioRxiv scan error: {e}")
        
        # PubMed
        try:
            print("Scanning PubMed...")
            pubmed_scraper = PubmedScraper(db)
            count = pubmed_scraper.fetch_and_store(max_results=max_results_per_source)
            total += count
            print(f"PubMed: fetched {count} papers")
        except Exception as e:
            print(f"PubMed scan error: {e}")
        
        print(f"Scan complete: {total} total papers fetched")
    finally:
        db.close()


@router.post("/all", response_model=ScanResponse)
async def scan_all_sources(
    max_results_per_source: int = 50,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """Scan all paper sources (runs in background)."""
    if background_tasks:
        background_tasks.add_task(_run_scan_all, max_results_per_source)
        return ScanResponse(
            message="Scan started in background. Check logs for progress.",
            papers_fetched=0,
            source="all",
        )
    
    # Fallback to sync if no background_tasks
    _run_scan_all(max_results_per_source)
    return ScanResponse(
        message="Scan complete",
        papers_fetched=0,
        source="all",
    )


async def _scan_all_streaming(max_results_per_source: int) -> AsyncGenerator[str, None]:
    """Generator that yields SSE events during scan."""
    db = SessionLocal()
    total = 0
    
    def send_event(event_type: str, data: dict) -> str:
        """Format SSE event."""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    
    try:
        yield send_event("start", {"message": "Starting scan of all sources...", "sources": ["arxiv", "biorxiv", "medrxiv", "pubmed"]})
        await asyncio.sleep(0.1)  # Allow event to flush
        
        # arXiv
        yield send_event("source_start", {"source": "arxiv", "message": "Scanning arXiv for biology papers..."})
        await asyncio.sleep(0.1)
        try:
            arxiv_scraper = ArxivScraper(db)
            # Fetch papers without term search for speed
            papers = arxiv_scraper.search_by_categories(max_results=max_results_per_source)
            for paper in papers:
                db.add(paper)
            db.commit()
            count = len(papers)
            total += count
            yield send_event("source_complete", {
                "source": "arxiv", 
                "papers_fetched": count,
                "sample_titles": [p.title[:80] + "..." if len(p.title) > 80 else p.title for p in papers[:3]]
            })
        except Exception as e:
            yield send_event("source_error", {"source": "arxiv", "error": str(e)})
        await asyncio.sleep(0.1)
        
        # bioRxiv
        yield send_event("source_start", {"source": "biorxiv", "message": "Scanning bioRxiv..."})
        await asyncio.sleep(0.1)
        try:
            biorxiv_scraper = BiorxivScraper(db)
            papers = biorxiv_scraper.fetch_recent(server="biorxiv", max_results=max_results_per_source)
            for paper in papers:
                db.add(paper)
            db.commit()
            count = len(papers)
            total += count
            yield send_event("source_complete", {
                "source": "biorxiv",
                "papers_fetched": count,
                "sample_titles": [p.title[:80] + "..." if len(p.title) > 80 else p.title for p in papers[:3]]
            })
        except Exception as e:
            yield send_event("source_error", {"source": "biorxiv", "error": str(e)})
        await asyncio.sleep(0.1)
        
        # medRxiv
        yield send_event("source_start", {"source": "medrxiv", "message": "Scanning medRxiv..."})
        await asyncio.sleep(0.1)
        try:
            medrxiv_scraper = BiorxivScraper(db)
            papers = medrxiv_scraper.fetch_recent(server="medrxiv", max_results=max_results_per_source)
            for paper in papers:
                db.add(paper)
            db.commit()
            count = len(papers)
            total += count
            yield send_event("source_complete", {
                "source": "medrxiv",
                "papers_fetched": count,
                "sample_titles": [p.title[:80] + "..." if len(p.title) > 80 else p.title for p in papers[:3]]
            })
        except Exception as e:
            yield send_event("source_error", {"source": "medrxiv", "error": str(e)})
        await asyncio.sleep(0.1)
        
        # PubMed
        yield send_event("source_start", {"source": "pubmed", "message": "Scanning PubMed..."})
        await asyncio.sleep(0.1)
        try:
            pubmed_scraper = PubmedScraper(db)
            count = pubmed_scraper.fetch_and_store(max_results=max_results_per_source)
            total += count
            yield send_event("source_complete", {
                "source": "pubmed",
                "papers_fetched": count,
                "sample_titles": []  # PubMed doesn't return papers list easily
            })
        except Exception as e:
            yield send_event("source_error", {"source": "pubmed", "error": str(e)})
        await asyncio.sleep(0.1)
        
        yield send_event("complete", {"message": "Scan complete!", "total_papers": total})
        
    except Exception as e:
        yield send_event("error", {"message": f"Scan failed: {str(e)}"})
    finally:
        db.close()


@router.get("/all/stream")
async def scan_all_sources_stream(max_results_per_source: int = 30):
    """Scan all sources with real-time SSE progress updates."""
    return StreamingResponse(
        _scan_all_streaming(max_results_per_source),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
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


async def _assess_streaming(limit: int) -> AsyncGenerator[str, None]:
    """Generator that yields SSE events during assessment."""
    from ..models import Paper
    
    db = SessionLocal()
    
    def send_event(event_type: str, data: dict) -> str:
        """Format SSE event."""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    
    try:
        # Check API key
        if not settings.anthropic_api_key:
            yield send_event("error", {"message": "Anthropic API key not configured"})
            return
        
        # Get unprocessed papers
        papers = db.query(Paper).filter(not_(Paper.processed)).limit(limit).all()
        total_papers = len(papers)
        
        if total_papers == 0:
            yield send_event("complete", {
                "message": "No unprocessed papers to assess",
                "assessed": 0,
                "flagged": 0
            })
            return
        
        yield send_event("start", {
            "message": f"Starting assessment of {total_papers} papers...",
            "total_papers": total_papers
        })
        await asyncio.sleep(0.1)
        
        assessor = BiosecurityAssessor(db)
        assessed_count = 0
        flagged_count = 0
        
        for i, paper in enumerate(papers):
            # Send progress update before each paper
            yield send_event("paper_start", {
                "paper_id": paper.id,
                "title": paper.title[:100] + "..." if len(paper.title) > 100 else paper.title,
                "source": paper.source,
                "progress": f"{i + 1}/{total_papers}"
            })
            await asyncio.sleep(0.1)
            
            try:
                # Assess the paper
                assessment = assessor.assess_paper(paper)
                
                if assessment:
                    assessed_count += 1
                    is_flagged = assessment.flagged
                    if is_flagged:
                        flagged_count += 1
                    
                    yield send_event("paper_complete", {
                        "paper_id": paper.id,
                        "title": paper.title[:100] + "..." if len(paper.title) > 100 else paper.title,
                        "risk_grade": assessment.risk_grade,
                        "overall_score": assessment.overall_score,
                        "flagged": is_flagged,
                        "flag_reason": assessment.flag_reason if is_flagged else None,
                        "concerns_summary": assessment.concerns_summary[:200] if assessment.concerns_summary else None,
                        "pathogens": json.loads(assessment.pathogens_identified) if assessment.pathogens_identified else [],
                        "progress": f"{i + 1}/{total_papers}",
                        "assessed_so_far": assessed_count,
                        "flagged_so_far": flagged_count
                    })
                else:
                    yield send_event("paper_error", {
                        "paper_id": paper.id,
                        "title": paper.title[:100] + "..." if len(paper.title) > 100 else paper.title,
                        "error": "Assessment failed - check logs for details"
                    })
            except Exception as e:
                yield send_event("paper_error", {
                    "paper_id": paper.id,
                    "title": paper.title[:100] + "..." if len(paper.title) > 100 else paper.title,
                    "error": str(e)
                })
            
            await asyncio.sleep(0.1)
        
        yield send_event("complete", {
            "message": f"Assessment complete! Processed {assessed_count} papers, {flagged_count} flagged for review.",
            "assessed": assessed_count,
            "flagged": flagged_count
        })
        
    except Exception as e:
        yield send_event("error", {"message": f"Assessment failed: {str(e)}"})
    finally:
        db.close()


@router.get("/assess/stream")
async def assess_papers_stream(limit: int = 10):
    """Assess papers with real-time SSE progress updates."""
    return StreamingResponse(
        _assess_streaming(limit),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
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

