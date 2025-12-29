"""bioRxiv paper scraper for biology research papers."""
import httpx
import json
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

from ..models import Paper
from ..config import settings


class BiorxivScraper:
    """Scraper for fetching papers from bioRxiv and medRxiv.
    
    DESIGN: Biased toward RECALL (false positives OK).
    We fetch ALL papers and let the LLM assessment filter relevance.
    """
    
    BASE_URL = "https://api.biorxiv.org"
    
    # Note: We DON'T filter by subject anymore - grab everything
    # LLM assessment will determine relevance
    # This list is kept for reference/logging only
    HIGH_PRIORITY_SUBJECTS = [
        "microbiology",
        "infectious diseases", 
        "synthetic biology",
        "genomics",
        "pathology",
        "immunology",
        "epidemiology",
        "virology",
    ]
    
    def __init__(self, db: Session):
        """Initialize scraper with database session."""
        self.db = db
        self.client = httpx.Client(timeout=30.0)
    
    def _paper_exists(self, doi: str) -> bool:
        """Check if paper already exists in database."""
        return self.db.query(Paper).filter(
            Paper.source.in_(["biorxiv", "medrxiv"]),
            Paper.external_id == doi
        ).first() is not None
    
    def _result_to_paper(self, result: dict, source: str) -> Paper:
        """Convert bioRxiv API result to Paper model."""
        # Parse date
        published_date = None
        if result.get("date"):
            try:
                published_date = datetime.strptime(result["date"], "%Y-%m-%d")
            except:
                pass
        
        # Build authors string
        authors = result.get("authors", "")
        if authors:
            authors = json.dumps([a.strip() for a in authors.split(";")])
        else:
            authors = "[]"
        
        # Build URL
        doi = result.get("doi", "")
        url = f"https://doi.org/{doi}" if doi else None
        
        return Paper(
            source=source,
            external_id=doi,
            title=result.get("title", ""),
            authors=authors,
            abstract=result.get("abstract", ""),
            url=url,
            pdf_url=None,  # bioRxiv doesn't provide direct PDF URLs in API
            published_date=published_date,
            categories=json.dumps([result.get("category", "")]),
            processed=False,
        )
    
    def fetch_recent(
        self,
        server: str = "biorxiv",
        days_back: int = 7,
        max_results: int = 100,
    ) -> List[Paper]:
        """
        Fetch recent papers from bioRxiv or medRxiv.
        
        Args:
            server: "biorxiv" or "medrxiv"
            days_back: How many days back to search
            max_results: Maximum number of papers to fetch
            
        Returns:
            List of Paper objects (not yet committed to DB)
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        papers = []
        cursor = 0
        
        while len(papers) < max_results:
            # Construct API URL
            # Format: /details/{server}/{interval}/{cursor}
            url = f"{self.BASE_URL}/details/{server}/{start_str}/{end_str}/{cursor}"
            
            try:
                response = self.client.get(url)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                print(f"Error fetching from {server}: {e}")
                break
            
            collection = data.get("collection", [])
            if not collection:
                break
            
            for result in collection:
                doi = result.get("doi", "")
                
                # Skip if already in database
                if self._paper_exists(doi):
                    continue
                
                # NO FILTERING - grab ALL papers
                # Biased toward recall - LLM assessment will filter relevance
                papers.append(self._result_to_paper(result, server))
                
                if len(papers) >= max_results:
                    break
            
            # Move to next page
            cursor += len(collection)
            
            # Check if there are more results
            messages = data.get("messages", [])
            if messages and messages[0].get("status") == "no papers found":
                break
        
        return papers
    
    def search_by_terms(
        self,
        server: str = "biorxiv",
        max_results: int = 50,
    ) -> List[Paper]:
        """
        Search for papers using biosecurity-relevant terms.
        Note: bioRxiv API doesn't support search, so this fetches recent and filters.
        
        Args:
            server: "biorxiv" or "medrxiv"
            max_results: Maximum number of papers to return
            
        Returns:
            List of Paper objects (not yet committed to DB)
        """
        # bioRxiv API doesn't support text search, so we fetch recent and could
        # filter client-side, but for now just return recent from relevant categories
        return self.fetch_recent(server=server, days_back=14, max_results=max_results)
    
    def fetch_and_store(
        self,
        max_results: int = None,
        days_back: int = 7,
    ) -> int:
        """
        Fetch papers from bioRxiv and medRxiv and store in database.
        
        Args:
            max_results: Maximum papers to fetch per server (defaults to config)
            days_back: How many days back to search
            
        Returns:
            Number of new papers stored
        """
        if max_results is None:
            max_results = settings.max_papers_per_scan // 2
        
        all_papers = []
        
        # Fetch from bioRxiv
        try:
            biorxiv_papers = self.fetch_recent(
                server="biorxiv",
                days_back=days_back,
                max_results=max_results,
            )
            all_papers.extend(biorxiv_papers)
        except Exception as e:
            print(f"Error fetching from bioRxiv: {e}")
        
        # Fetch from medRxiv
        try:
            medrxiv_papers = self.fetch_recent(
                server="medrxiv",
                days_back=days_back,
                max_results=max_results,
            )
            all_papers.extend(medrxiv_papers)
        except Exception as e:
            print(f"Error fetching from medRxiv: {e}")
        
        # Store in database
        for paper in all_papers:
            self.db.add(paper)
        
        self.db.commit()
        
        return len(all_papers)

