"""arXiv paper scraper for biology research papers."""
import arxiv
import json
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

from ..models import Paper
from ..config import settings


class ArxivScraper:
    """Scraper for fetching biology papers from arXiv."""
    
    # Biology-related arXiv categories
    BIOLOGY_CATEGORIES = [
        "q-bio.BM",  # Biomolecules
        "q-bio.CB",  # Cell Behavior
        "q-bio.GN",  # Genomics
        "q-bio.MN",  # Molecular Networks
        "q-bio.NC",  # Neurons and Cognition
        "q-bio.OT",  # Other Quantitative Biology
        "q-bio.PE",  # Populations and Evolution
        "q-bio.QM",  # Quantitative Methods
        "q-bio.SC",  # Subcellular Processes
        "q-bio.TO",  # Tissues and Organs
    ]
    
    # Biosecurity-relevant search terms
    BIOSECURITY_TERMS = [
        "pathogen",
        "virus",
        "bacterial",
        "infectious disease",
        "gain of function",
        "transmissibility",
        "virulence",
        "biosafety",
        "synthetic biology",
        "genome editing",
        "CRISPR",
        "pandemic",
        "outbreak",
        "bioweapon",
        "dual use",
        "select agent",
        "BSL",
        "containment",
    ]
    
    def __init__(self, db: Session):
        """Initialize scraper with database session."""
        self.db = db
        self.client = arxiv.Client()
    
    def _paper_exists(self, arxiv_id: str) -> bool:
        """Check if paper already exists in database."""
        return self.db.query(Paper).filter(
            Paper.source == "arxiv",
            Paper.external_id == arxiv_id
        ).first() is not None
    
    def _result_to_paper(self, result: arxiv.Result) -> Paper:
        """Convert arXiv result to Paper model."""
        return Paper(
            source="arxiv",
            external_id=result.entry_id.split("/")[-1],  # Extract arXiv ID
            title=result.title,
            authors=json.dumps([str(a) for a in result.authors]),
            abstract=result.summary,
            url=result.entry_id,
            pdf_url=result.pdf_url,
            published_date=result.published,
            categories=json.dumps(result.categories),
            processed=False,
        )
    
    def search_by_categories(
        self,
        max_results: int = 100,
        days_back: int = 7,
    ) -> List[Paper]:
        """
        Search for papers in biology categories.
        
        Args:
            max_results: Maximum number of papers to fetch
            days_back: How many days back to search
            
        Returns:
            List of Paper objects (not yet committed to DB)
        """
        # Build category query
        category_query = " OR ".join([f"cat:{cat}" for cat in self.BIOLOGY_CATEGORIES])
        
        search = arxiv.Search(
            query=category_query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        
        papers = []
        for result in self.client.results(search):
            # Skip if already in database
            arxiv_id = result.entry_id.split("/")[-1]
            if self._paper_exists(arxiv_id):
                continue
            
            papers.append(self._result_to_paper(result))
        
        return papers
    
    def search_by_terms(
        self,
        terms: Optional[List[str]] = None,
        max_results: int = 50,
    ) -> List[Paper]:
        """
        Search for papers using biosecurity-relevant terms.
        
        Args:
            terms: Search terms (defaults to BIOSECURITY_TERMS)
            max_results: Maximum number of papers per term
            
        Returns:
            List of Paper objects (not yet committed to DB)
        """
        if terms is None:
            terms = self.BIOSECURITY_TERMS
        
        papers = []
        seen_ids = set()
        
        for term in terms:
            # Combine term with biology categories
            category_filter = " OR ".join([f"cat:{cat}" for cat in self.BIOLOGY_CATEGORIES])
            query = f"({term}) AND ({category_filter})"
            
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance,
            )
            
            for result in self.client.results(search):
                arxiv_id = result.entry_id.split("/")[-1]
                
                # Skip duplicates
                if arxiv_id in seen_ids:
                    continue
                seen_ids.add(arxiv_id)
                
                # Skip if already in database
                if self._paper_exists(arxiv_id):
                    continue
                
                papers.append(self._result_to_paper(result))
        
        return papers
    
    def fetch_and_store(
        self,
        max_results: int = None,
        use_terms: bool = True,
    ) -> int:
        """
        Fetch papers and store in database.
        
        Args:
            max_results: Maximum papers to fetch (defaults to config)
            use_terms: Whether to also search by biosecurity terms
            
        Returns:
            Number of new papers stored
        """
        if max_results is None:
            max_results = settings.max_papers_per_scan
        
        all_papers = []
        
        # Fetch by categories
        category_papers = self.search_by_categories(max_results=max_results)
        all_papers.extend(category_papers)
        
        # Optionally fetch by terms
        if use_terms:
            term_papers = self.search_by_terms(max_results=max_results // 2)
            # Deduplicate
            seen_ids = {p.external_id for p in all_papers}
            for paper in term_papers:
                if paper.external_id not in seen_ids:
                    all_papers.append(paper)
                    seen_ids.add(paper.external_id)
        
        # Store in database
        for paper in all_papers:
            self.db.add(paper)
        
        self.db.commit()
        
        return len(all_papers)
    
    def get_paper_full_text(self, arxiv_id: str) -> Optional[str]:
        """
        Attempt to get full text for a paper.
        Note: arXiv doesn't provide full text via API, only abstracts.
        This is a placeholder for potential PDF parsing.
        
        Args:
            arxiv_id: The arXiv paper ID
            
        Returns:
            Full text if available, None otherwise
        """
        # For now, we only have abstracts from arXiv
        # Full text would require PDF download and parsing
        # which is a more complex task
        return None

