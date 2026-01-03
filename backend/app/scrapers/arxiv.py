"""arXiv paper scraper for biology research papers."""
import arxiv
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

from ..models import Paper
from ..config import settings

logger = logging.getLogger(__name__)


class ArxivScraper:
    """Scraper for fetching biology papers from arXiv."""
    
    # BROAD category list - biased toward recall (false positives OK)
    # LLM assessment will filter out irrelevant papers
    BIOLOGY_CATEGORIES = [
        # Core biology
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
    
    # Adjacent categories that may contain biosecurity-relevant work
    ADJACENT_CATEGORIES = [
        "cs.LG",      # Machine Learning (protein design, etc.)
        "cs.AI",      # AI (dual-use AI/bio)
        "cs.CL",      # Computation and Language (LLM + bio)
        "physics.bio-ph",  # Biological Physics
        "physics.soc-ph",  # Social Physics (epidemiology models)
        "stat.ML",    # Machine Learning
        "cond-mat.soft",   # Soft matter (virus structure)
    ]
    
    # BROAD search terms - err on side of catching too much
    # Better to have false positives than miss something
    BIOSECURITY_TERMS = [
        # Direct biosecurity terms
        "pathogen", "virus", "viral", "bacterial", "bacteria",
        "infectious disease", "infection", "contagious",
        "gain of function", "gain-of-function",
        "transmissibility", "transmission", "airborne", "aerosol",
        "virulence", "pathogenicity", "lethality",
        "biosafety", "biosecurity", "biodefense",
        "pandemic", "epidemic", "outbreak", "endemic",
        "bioweapon", "biological weapon", "dual use", "dual-use",
        "select agent", "BSL", "containment", "quarantine",
        # Techniques that could be dual-use
        "synthetic biology", "genome editing", "gene editing",
        "CRISPR", "cas9", "cas12", "cas13",
        "directed evolution", "serial passage", "adaptation",
        "reverse genetics", "recombinant", "chimeric",
        "protein engineering", "enzyme engineering",
        # Specific pathogens/threats
        "influenza", "coronavirus", "SARS", "MERS", "COVID",
        "ebola", "marburg", "smallpox", "variola", "anthrax",
        "plague", "yersinia", "botulinum", "ricin",
        "H5N1", "H7N9", "avian flu", "bird flu",
        "hemorrhagic fever", "encephalitis",
        # Enhancement-related
        "enhanced", "enhancement", "increased", "improved",
        "fitness", "replication", "host range", "tropism",
        "immune evasion", "antibody escape", "vaccine escape",
        # Lab/research context
        "laboratory", "lab-acquired", "biosafety level",
        "high containment", "maximum containment",
        # AI + bio intersection
        "protein design", "de novo protein", "protein generation",
        "sequence generation", "generative model",
        "AlphaFold", "ESM", "language model",
    ]
    
    def __init__(self, db: Session):
        """Initialize scraper with database session."""
        self.db = db
        self.client = arxiv.Client(
            page_size=50,
            delay_seconds=1.0,
            num_retries=2,
        )
    
    def _paper_exists(self, arxiv_id: str) -> bool:
        """Check if paper already exists in database."""
        return self.db.query(Paper).filter(
            Paper.source == "arxiv",
            Paper.external_id == arxiv_id
        ).first() is not None
    
    def _result_to_paper(self, result: arxiv.Result) -> Paper:
        """Convert arXiv result to Paper model."""
        # Extract author names
        authors = [str(a) for a in result.authors]
        
        # Try to extract affiliations (arxiv Author objects may have these)
        affiliations = set()
        for author in result.authors:
            # Check if author object has affiliation attribute
            if hasattr(author, 'affiliation') and author.affiliation:
                affiliations.add(author.affiliation)
        
        return Paper(
            source="arxiv",
            external_id=result.entry_id.split("/")[-1],  # Extract arXiv ID
            title=result.title,
            authors=json.dumps(authors),
            affiliations=json.dumps(list(affiliations)) if affiliations else None,
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
        include_adjacent: bool = True,
    ) -> List[Paper]:
        """
        Search for papers in biology + adjacent categories.
        Biased toward RECALL - better to catch too much than miss something.
        
        Args:
            max_results: Maximum number of papers to fetch
            days_back: How many days back to search
            include_adjacent: Also search CS/physics categories
            
        Returns:
            List of Paper objects (not yet committed to DB)
        """
        # Build category query - include all relevant categories
        categories = self.BIOLOGY_CATEGORIES.copy()
        if include_adjacent:
            categories.extend(self.ADJACENT_CATEGORIES)
        
        category_query = " OR ".join([f"cat:{cat}" for cat in categories])
        logger.info(f"arXiv search: querying {len(categories)} categories, max_results={max_results}")
        
        search = arxiv.Search(
            query=category_query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        
        papers = []
        count = 0
        logger.info("arXiv: starting to fetch results...")
        for result in self.client.results(search):
            count += 1
            if count % 10 == 0:
                logger.info(f"arXiv: processed {count} results, {len(papers)} new papers so far")
            
            # Skip if already in database
            arxiv_id = result.entry_id.split("/")[-1]
            if self._paper_exists(arxiv_id):
                continue
            
            papers.append(self._result_to_paper(result))
        
        logger.info(f"arXiv: finished with {len(papers)} new papers from {count} results")
        return papers
    
    def search_by_terms(
        self,
        terms: Optional[List[str]] = None,
        max_results: int = 50,
        restrict_to_categories: bool = False,  # Default: search ALL of arXiv
    ) -> List[Paper]:
        """
        Search for papers using biosecurity-relevant terms.
        Biased toward RECALL - searches across ALL arXiv by default.
        
        Args:
            terms: Search terms (defaults to BIOSECURITY_TERMS)
            max_results: Maximum number of papers per term
            restrict_to_categories: If False, search all of arXiv (more recall)
            
        Returns:
            List of Paper objects (not yet committed to DB)
        """
        if terms is None:
            terms = self.BIOSECURITY_TERMS
        
        papers = []
        seen_ids = set()
        
        for term in terms:
            # By default, DON'T restrict to categories - cast wide net
            # The LLM assessment will filter out irrelevant papers
            if restrict_to_categories:
                all_cats = self.BIOLOGY_CATEGORIES + self.ADJACENT_CATEGORIES
                category_filter = " OR ".join([f"cat:{cat}" for cat in all_cats])
                query = f"({term}) AND ({category_filter})"
            else:
                # Search ALL of arXiv for this term
                query = term
            
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
        use_terms: bool = False,  # Disabled by default - too slow
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
        
        logger.info(f"arXiv fetch_and_store: max_results={max_results}, use_terms={use_terms}")
        
        all_papers = []
        
        # Fetch by categories
        logger.info("arXiv: fetching by categories...")
        category_papers = self.search_by_categories(max_results=max_results)
        all_papers.extend(category_papers)
        logger.info(f"arXiv: got {len(category_papers)} papers from categories")
        
        # Optionally fetch by terms (disabled by default - very slow)
        if use_terms:
            logger.info("arXiv: fetching by terms (this may be slow)...")
            term_papers = self.search_by_terms(max_results=max_results // 2)
            # Deduplicate
            seen_ids = {p.external_id for p in all_papers}
            for paper in term_papers:
                if paper.external_id not in seen_ids:
                    all_papers.append(paper)
                    seen_ids.add(paper.external_id)
            logger.info(f"arXiv: got {len(term_papers)} papers from term search")
        
        # Store in database
        logger.info(f"arXiv: storing {len(all_papers)} papers in database...")
        for paper in all_papers:
            self.db.add(paper)
        
        self.db.commit()
        logger.info(f"arXiv: committed {len(all_papers)} papers to database")
        
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

