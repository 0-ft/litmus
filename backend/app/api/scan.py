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


class FetchPaperRequest(BaseModel):
    """Request to fetch a single paper by URL."""
    url: str


class FetchPaperResponse(BaseModel):
    """Response for single paper fetch."""
    success: bool
    message: str
    paper_id: Optional[int] = None
    title: Optional[str] = None
    source: Optional[str] = None
    already_exists: bool = False


def _parse_paper_url(url: str) -> tuple[str, str]:
    """
    Parse a paper URL to extract source and ID.
    
    Returns:
        Tuple of (source, paper_id)
    
    Raises:
        ValueError if URL format not recognized
    """
    import re
    
    url = url.strip()
    
    # arXiv URLs
    # https://arxiv.org/abs/2401.12345
    # https://arxiv.org/pdf/2401.12345.pdf
    # arxiv:2401.12345
    arxiv_patterns = [
        r'arxiv\.org/abs/([0-9]+\.[0-9]+(?:v\d+)?)',
        r'arxiv\.org/pdf/([0-9]+\.[0-9]+(?:v\d+)?)',
        r'^arxiv:([0-9]+\.[0-9]+(?:v\d+)?)',
        r'arxiv\.org/abs/([\w-]+/[0-9]+)',  # Old format like hep-th/9901001
    ]
    for pattern in arxiv_patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return ("arxiv", match.group(1).replace('.pdf', ''))
    
    # bioRxiv URLs
    # https://www.biorxiv.org/content/10.1101/2024.01.12.345678v1
    # https://doi.org/10.1101/2024.01.12.345678
    biorxiv_patterns = [
        r'biorxiv\.org/content/(10\.1101/[0-9.]+)',
        r'doi\.org/(10\.1101/[0-9.]+)',
    ]
    for pattern in biorxiv_patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            doi = match.group(1)
            # Remove version suffix if present
            doi = re.sub(r'v\d+$', '', doi)
            return ("biorxiv", doi)
    
    # medRxiv URLs
    # https://www.medrxiv.org/content/10.1101/2024.01.12.345678v1
    medrxiv_patterns = [
        r'medrxiv\.org/content/(10\.1101/[0-9.]+)',
    ]
    for pattern in medrxiv_patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            doi = match.group(1)
            doi = re.sub(r'v\d+$', '', doi)
            return ("medrxiv", doi)
    
    # PubMed URLs
    # https://pubmed.ncbi.nlm.nih.gov/12345678/
    # https://www.ncbi.nlm.nih.gov/pubmed/12345678
    # PMID: 12345678
    pubmed_patterns = [
        r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)',
        r'ncbi\.nlm\.nih\.gov/pubmed/(\d+)',
        r'^PMID:\s*(\d+)',
        r'^(\d{7,8})$',  # Just a PMID number
    ]
    for pattern in pubmed_patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return ("pubmed", match.group(1))
    
    # DOI that might be from other sources
    # https://doi.org/10.xxxx/xxxxx
    doi_pattern = r'doi\.org/(10\.\d+/[^\s]+)'
    match = re.search(doi_pattern, url)
    if match:
        doi = match.group(1)
        # Check if it's a biorxiv/medrxiv DOI
        if doi.startswith('10.1101/'):
            return ("biorxiv", doi)
        # For other DOIs, try to look them up (would need CrossRef API)
        raise ValueError(f"DOI {doi} is not from a supported source (arxiv, biorxiv, medrxiv, pubmed)")
    
    raise ValueError("Could not parse URL. Supported formats: arXiv, bioRxiv, medRxiv, PubMed")


@router.post("/fetch-paper", response_model=FetchPaperResponse)
async def fetch_single_paper(
    request: FetchPaperRequest,
    db: Session = Depends(get_db),
):
    """
    Fetch a single paper by URL.
    
    Supports:
    - arXiv: https://arxiv.org/abs/2401.12345
    - bioRxiv: https://www.biorxiv.org/content/10.1101/...
    - medRxiv: https://www.medrxiv.org/content/10.1101/...
    - PubMed: https://pubmed.ncbi.nlm.nih.gov/12345678/
    """
    try:
        source, paper_id = _parse_paper_url(request.url)
        logger.info(f"Parsed URL: source={source}, id={paper_id}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Check if paper already exists
    from ..models import Paper
    existing = db.query(Paper).filter(
        Paper.source == source,
        Paper.external_id == paper_id
    ).first()
    
    if existing:
        return FetchPaperResponse(
            success=True,
            message="Paper already exists in database",
            paper_id=existing.id,
            title=existing.title,
            source=source,
            already_exists=True,
        )
    
    # Fetch based on source
    try:
        if source == "arxiv":
            import arxiv
            search = arxiv.Search(id_list=[paper_id])
            client = arxiv.Client()
            results = list(client.results(search))
            
            if not results:
                raise HTTPException(status_code=404, detail=f"Paper not found on arXiv: {paper_id}")
            
            result = results[0]
            paper = Paper(
                source="arxiv",
                external_id=result.entry_id.split("/")[-1],
                title=result.title,
                authors=json.dumps([str(a) for a in result.authors]),
                abstract=result.summary,
                url=result.entry_id,
                pdf_url=result.pdf_url,
                published_date=result.published,
                categories=json.dumps(result.categories),
                processed=False,
            )
            
        elif source in ["biorxiv", "medrxiv"]:
            import httpx
            # Use bioRxiv API to fetch by DOI
            api_url = f"https://api.biorxiv.org/details/{source}/{paper_id}"
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(api_url)
                response.raise_for_status()
                data = response.json()
            
            if not data.get("collection") or len(data["collection"]) == 0:
                raise HTTPException(status_code=404, detail=f"Paper not found on {source}: {paper_id}")
            
            result = data["collection"][0]
            from datetime import datetime
            published_date = None
            if result.get("date"):
                try:
                    published_date = datetime.strptime(result["date"], "%Y-%m-%d")
                except ValueError:
                    pass
            
            authors = result.get("authors", "")
            if authors:
                authors = json.dumps([a.strip() for a in authors.split(";")])
            else:
                authors = "[]"
            
            paper = Paper(
                source=source,
                external_id=paper_id,
                title=result.get("title", ""),
                authors=authors,
                abstract=result.get("abstract", ""),
                url=f"https://doi.org/{paper_id}",
                pdf_url=None,
                published_date=published_date,
                categories=json.dumps([result.get("category", "")]),
                processed=False,
            )
            
        elif source == "pubmed":
            try:
                from Bio import Entrez
            except ImportError:
                raise HTTPException(status_code=500, detail="PubMed support requires Biopython")
            
            Entrez.email = "litmus@example.com"
            if settings.ncbi_api_key:
                Entrez.api_key = settings.ncbi_api_key
            
            # Fetch paper details using Entrez.read() for proper StringElement handling
            handle = Entrez.efetch(db="pubmed", id=paper_id, rettype="xml", retmode="xml")
            records = Entrez.read(handle)
            handle.close()
            
            if not records.get("PubmedArticle"):
                raise HTTPException(status_code=404, detail=f"Paper not found on PubMed: {paper_id}")
            
            record = records["PubmedArticle"][0]
            article = record.get("MedlineCitation", {}).get("Article", {})
            
            # Extract title
            title = article.get("ArticleTitle", "Unknown Title")
            
            # Extract abstract - use str() to handle StringElement properly
            abstract_parts = article.get("Abstract", {}).get("AbstractText", [])
            if abstract_parts:
                if isinstance(abstract_parts, list):
                    abstract = " ".join(str(p) for p in abstract_parts)
                else:
                    abstract = str(abstract_parts)
            else:
                abstract = None
            
            # Extract authors and affiliations
            author_list = article.get("AuthorList", [])
            authors = []
            affiliations = set()
            for author in author_list:
                last = author.get("LastName", "")
                first = author.get("ForeName", "")
                if last:
                    authors.append(f"{first} {last}".strip())
                
                # Extract affiliations
                for aff in author.get("AffiliationInfo", []):
                    aff_text = aff.get("Affiliation", "")
                    if aff_text:
                        affiliations.add(aff_text)
            
            affiliations_json = json.dumps(list(affiliations)) if affiliations else None
            
            # Extract date
            from datetime import datetime
            pub_date = None
            date_info = article.get("ArticleDate", [])
            if date_info:
                date_info = date_info[0]
                try:
                    year = int(date_info.get("Year", 0))
                    month = int(date_info.get("Month", 1))
                    day = int(date_info.get("Day", 1))
                    pub_date = datetime(year, month, day)
                except (ValueError, TypeError):
                    pass
            
            if not pub_date:
                journal_info = article.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {})
                try:
                    year = int(journal_info.get("Year", 0))
                    if year:
                        pub_date = datetime(year, 1, 1)
                except (ValueError, TypeError):
                    pass
            
            # Extract categories from MeSH terms
            mesh_list = record.get("MedlineCitation", {}).get("MeshHeadingList", [])
            categories = [str(mesh.get("DescriptorName", "")) for mesh in mesh_list[:10] if mesh.get("DescriptorName")]
            
            paper = Paper(
                source="pubmed",
                external_id=paper_id,
                title=title,
                authors=json.dumps(authors),
                affiliations=affiliations_json,
                abstract=abstract,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{paper_id}/",
                pdf_url=None,
                published_date=pub_date,
                categories=json.dumps(categories),
                processed=False,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported source: {source}")
        
        # Save to database
        db.add(paper)
        db.commit()
        db.refresh(paper)
        
        return FetchPaperResponse(
            success=True,
            message=f"Successfully fetched paper from {source}",
            paper_id=paper.id,
            title=paper.title,
            source=source,
            already_exists=False,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching paper: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch paper: {str(e)}")


class AssessPaperResponse(BaseModel):
    """Response for single paper assessment."""
    success: bool
    message: str
    paper_id: int
    risk_grade: Optional[str] = None
    overall_score: Optional[float] = None
    flagged: bool = False
    flag_reason: Optional[str] = None
    concerns_summary: Optional[str] = None
    pathogens: Optional[list] = None
    already_assessed: bool = False


@router.post("/assess-paper/{paper_id}", response_model=AssessPaperResponse)
async def assess_single_paper(
    paper_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
):
    """
    Assess a single paper by ID.
    
    Args:
        paper_id: Database ID of the paper to assess
        force: If True, re-assess even if already processed
    """
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=400,
            detail="Anthropic API key not configured. Set ANTHROPIC_API_KEY environment variable."
        )
    
    from ..models import Paper, Assessment
    
    # Get the paper
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper not found: {paper_id}")
    
    # Check if already assessed
    if paper.processed and not force:
        # Get existing assessment
        existing = db.query(Assessment).filter(
            Assessment.paper_id == paper_id
        ).order_by(Assessment.assessed_at.desc()).first()
        
        if existing:
            pathogens = []
            if existing.pathogens_identified:
                try:
                    pathogens = json.loads(existing.pathogens_identified)
                except:
                    pass
            
            return AssessPaperResponse(
                success=True,
                message="Paper already assessed",
                paper_id=paper_id,
                risk_grade=existing.risk_grade,
                overall_score=existing.overall_score,
                flagged=existing.flagged,
                flag_reason=existing.flag_reason,
                concerns_summary=existing.concerns_summary,
                pathogens=pathogens,
                already_assessed=True,
            )
    
    # If forcing re-assessment, reset processed status
    if force and paper.processed:
        paper.processed = False
        db.commit()
    
    # Assess the paper
    try:
        logger.info(f"Starting assessment for paper {paper_id}: {paper.title[:50]}...")
        assessor = BiosecurityAssessor(db)
        assessment = assessor.assess_paper(paper)
        
        if not assessment:
            raise HTTPException(
                status_code=500,
                detail="Assessment failed - Claude may have returned invalid response"
            )
        
        pathogens = []
        if assessment.pathogens_identified:
            try:
                pathogens = json.loads(assessment.pathogens_identified)
            except:
                pass
        
        return AssessPaperResponse(
            success=True,
            message=f"Assessment complete - Grade: {assessment.risk_grade}",
            paper_id=paper_id,
            risk_grade=assessment.risk_grade,
            overall_score=assessment.overall_score,
            flagged=assessment.flagged,
            flag_reason=assessment.flag_reason,
            concerns_summary=assessment.concerns_summary,
            pathogens=pathogens,
            already_assessed=False,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assessing paper {paper_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Assessment failed: {str(e)}")


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

