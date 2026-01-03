"""PubMed paper scraper for biology research papers."""
import json
import re
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

try:
    from Bio import Entrez
    BIOPYTHON_AVAILABLE = True
except ImportError:
    BIOPYTHON_AVAILABLE = False

from ..models import Paper
from ..config import settings


def extract_bsl_from_text(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract BSL (Biosafety Level) information from text.
    
    Returns:
        Tuple of (bsl_level, context_snippet)
        bsl_level: "BSL-1", "BSL-2", "BSL-3", "BSL-4", or None
        context_snippet: The sentence/context where BSL was mentioned
    """
    if not text:
        return None, None
    
    # Patterns to match BSL levels
    patterns = [
        # "biosafety level 2" or "biosafety level-2"
        (r'biosafety\s+level[-\s]?(\d)', 'biosafety level'),
        # "BSL-2" or "BSL2" or "BSL 2"
        (r'BSL[-\s]?(\d)', 'BSL'),
        # "ABSL-2" (Animal BSL)
        (r'ABSL[-\s]?(\d)', 'ABSL'),
    ]
    
    highest_bsl = None
    best_context = None
    
    for pattern, label in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            level = int(match.group(1))
            bsl_str = f"BSL-{level}"
            
            # Keep track of highest BSL found
            if highest_bsl is None or level > int(highest_bsl.split('-')[1]):
                highest_bsl = bsl_str
                
                # Extract context (surrounding text)
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end]
                # Clean up XML tags
                context = re.sub(r'<[^>]+>', '', context)
                context = re.sub(r'\s+', ' ', context).strip()
                best_context = f"...{context}..."
    
    return highest_bsl, best_context


def fetch_pmc_fulltext(pmid: str) -> Optional[str]:
    """
    Fetch full text from PubMed Central if available.
    
    Args:
        pmid: PubMed ID
        
    Returns:
        Full text XML content or None if not available
    """
    if not BIOPYTHON_AVAILABLE:
        return None
    
    try:
        # First get PMC ID via elink
        handle = Entrez.elink(dbfrom='pubmed', db='pmc', id=pmid)
        record = Entrez.read(handle)
        handle.close()
        
        links = record[0].get('LinkSetDb', [])
        if not links:
            return None
        
        pmc_ids = [link['Id'] for link in links[0].get('Link', [])]
        if not pmc_ids:
            return None
        
        # Fetch full text from PMC
        pmc_handle = Entrez.efetch(db='pmc', id=pmc_ids[0], rettype='xml')
        content = pmc_handle.read().decode('utf-8')
        pmc_handle.close()
        
        return content
        
    except Exception as e:
        print(f"Error fetching PMC full text for {pmid}: {e}")
        return None


class PubmedScraper:
    """Scraper for fetching papers from PubMed via NCBI Entrez.
    
    DESIGN: Biased toward RECALL (false positives OK).
    Broad search terms to catch anything potentially relevant.
    LLM assessment filters out irrelevant papers.
    """
    
    # BROAD search queries - err on side of catching too much
    SEARCH_QUERIES = [
        # Direct biosecurity
        "pathogen research",
        "gain of function",
        "gain-of-function",
        "viral transmissibility",
        "infectious disease laboratory",
        "biosafety level",
        "select agent",
        "pandemic preparedness",
        "biodefense",
        "biosecurity",
        "dual use research",
        # Specific pathogens
        "influenza transmission",
        "coronavirus research",
        "bat coronavirus",
        "SARS-CoV",
        "MERS-CoV",
        "avian influenza",
        "H5N1",
        "H7N9",
        "Ebola virus",
        "hemorrhagic fever",
        "smallpox variola",
        "anthrax bacillus",
        # Techniques
        "synthetic biology",
        "genome editing pathogen",
        "CRISPR virus",
        "directed evolution virus",
        "serial passage",
        "reverse genetics virus",
        "recombinant virus",
        "chimeric virus",
        # Enhancement-related
        "viral evolution",
        "host adaptation virus",
        "immune evasion",
        "antibody escape",
        "drug resistance pathogen",
        # Broad catches
        "virology laboratory",
        "high containment",
        "BSL-3",
        "BSL-4",
        # AI + bio
        "machine learning protein design",
        "deep learning virus",
        "generative model protein",
    ]
    
    def __init__(self, db: Session):
        """Initialize scraper with database session."""
        self.db = db
        
        if not BIOPYTHON_AVAILABLE:
            raise ImportError("Biopython is required for PubMed scraping. Install with: pip install biopython")
        
        # Set up Entrez
        Entrez.email = "litmus@example.com"  # Required by NCBI
        if settings.ncbi_api_key:
            Entrez.api_key = settings.ncbi_api_key
    
    def _paper_exists(self, pmid: str) -> bool:
        """Check if paper already exists in database."""
        return self.db.query(Paper).filter(
            Paper.source == "pubmed",
            Paper.external_id == pmid
        ).first() is not None
    
    def _fetch_details(self, pmids: List[str]) -> List[dict]:
        """Fetch detailed information for a list of PMIDs."""
        if not pmids:
            return []
        
        try:
            handle = Entrez.efetch(
                db="pubmed",
                id=",".join(pmids),
                rettype="xml",
                retmode="xml"
            )
            records = Entrez.read(handle)
            handle.close()
            return records.get("PubmedArticle", [])
        except Exception as e:
            print(f"Error fetching PubMed details: {e}")
            return []
    
    def _record_to_paper(self, record: dict) -> Optional[Paper]:
        """Convert PubMed record to Paper model."""
        try:
            article = record.get("MedlineCitation", {}).get("Article", {})
            
            # Get PMID
            pmid = str(record.get("MedlineCitation", {}).get("PMID", ""))
            if not pmid:
                return None
            
            # Get title
            title = article.get("ArticleTitle", "")
            if not title:
                return None
            
            # Get authors and affiliations
            author_list = article.get("AuthorList", [])
            authors = []
            affiliations = set()  # Use set to deduplicate
            for author in author_list:
                last = author.get("LastName", "")
                first = author.get("ForeName", "")
                if last:
                    authors.append(f"{first} {last}".strip())
                
                # Extract affiliations
                affiliation_info = author.get("AffiliationInfo", [])
                for aff in affiliation_info:
                    aff_text = aff.get("Affiliation", "")
                    if aff_text:
                        affiliations.add(aff_text)
            
            authors_json = json.dumps(authors)
            affiliations_json = json.dumps(list(affiliations)) if affiliations else None
            
            # Get abstract
            abstract_parts = article.get("Abstract", {}).get("AbstractText", [])
            if abstract_parts:
                if isinstance(abstract_parts, list):
                    abstract = " ".join(str(p) for p in abstract_parts)
                else:
                    abstract = str(abstract_parts)
            else:
                abstract = None
            
            # Get publication date
            pub_date = None
            date_info = article.get("ArticleDate", [])
            if date_info:
                date_info = date_info[0]
                try:
                    year = int(date_info.get("Year", 0))
                    month = int(date_info.get("Month", 1))
                    day = int(date_info.get("Day", 1))
                    pub_date = datetime(year, month, day)
                except:
                    pass
            
            if not pub_date:
                # Try PubDate
                journal_info = article.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {})
                try:
                    year = int(journal_info.get("Year", 0))
                    month_str = journal_info.get("Month", "Jan")
                    month_map = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                                "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
                    month = month_map.get(month_str, 1)
                    pub_date = datetime(year, month, 1)
                except:
                    pass
            
            # Get URL
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            
            # Get MeSH terms as categories
            mesh_list = record.get("MedlineCitation", {}).get("MeshHeadingList", [])
            categories = []
            for mesh in mesh_list:
                descriptor = mesh.get("DescriptorName", "")
                if descriptor:
                    categories.append(str(descriptor))
            categories_json = json.dumps(categories[:10])  # Limit to first 10
            
            return Paper(
                source="pubmed",
                external_id=pmid,
                title=title,
                authors=authors_json,
                affiliations=affiliations_json,
                abstract=abstract,
                url=url,
                pdf_url=None,
                published_date=pub_date,
                categories=categories_json,
                processed=False,
            )
        except Exception as e:
            print(f"Error parsing PubMed record: {e}")
            return None
    
    def search(
        self,
        query: str,
        max_results: int = 50,
        days_back: int = 30,
    ) -> List[Paper]:
        """
        Search PubMed for papers matching query.
        
        Args:
            query: Search query
            max_results: Maximum number of papers to fetch
            days_back: How many days back to search
            
        Returns:
            List of Paper objects (not yet committed to DB)
        """
        # Build date filter
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        date_filter = f'("{start_date.strftime("%Y/%m/%d")}"[Date - Publication] : "{end_date.strftime("%Y/%m/%d")}"[Date - Publication])'
        
        full_query = f"({query}) AND {date_filter}"
        
        try:
            # Search for PMIDs
            handle = Entrez.esearch(
                db="pubmed",
                term=full_query,
                retmax=max_results,
                sort="date"
            )
            search_results = Entrez.read(handle)
            handle.close()
            
            pmids = search_results.get("IdList", [])
            
            # Filter out existing papers
            new_pmids = [pmid for pmid in pmids if not self._paper_exists(pmid)]
            
            if not new_pmids:
                return []
            
            # Fetch details
            records = self._fetch_details(new_pmids)
            
            # Convert to papers
            papers = []
            for record in records:
                paper = self._record_to_paper(record)
                if paper:
                    papers.append(paper)
            
            return papers
            
        except Exception as e:
            print(f"Error searching PubMed: {e}")
            return []
    
    def enrich_with_pmc(self, paper: Paper) -> bool:
        """
        Enrich a PubMed paper with PMC full text if available.
        Extracts BSL information from the full text.
        
        Args:
            paper: Paper to enrich (must be from PubMed)
            
        Returns:
            True if paper was enriched, False otherwise
        """
        if paper.source != "pubmed":
            return False
        
        # Already has full text?
        if paper.full_text and len(paper.full_text) > 1000:
            return False
        
        pmid = paper.external_id
        pmc_content = fetch_pmc_fulltext(pmid)
        
        if not pmc_content:
            return False
        
        # Extract BSL info
        bsl_level, bsl_context = extract_bsl_from_text(pmc_content)
        
        # Store a summarized version of the full text (too big to store raw XML)
        # Extract just the methods section or relevant parts
        methods_match = re.search(
            r'<sec[^>]*>.*?<title[^>]*>.*?(Materials?\s+and\s+Methods?|Methods?).*?</title>.*?</sec>',
            pmc_content,
            re.IGNORECASE | re.DOTALL
        )
        
        full_text_parts = []
        if methods_match:
            methods_text = re.sub(r'<[^>]+>', ' ', methods_match.group())
            methods_text = re.sub(r'\s+', ' ', methods_text).strip()
            full_text_parts.append(f"METHODS: {methods_text[:5000]}")
        
        if bsl_level:
            full_text_parts.append(f"BSL_DETECTED: {bsl_level}")
            if bsl_context:
                full_text_parts.append(f"BSL_CONTEXT: {bsl_context}")
        
        if full_text_parts:
            paper.full_text = "\n\n".join(full_text_parts)
            self.db.commit()
            return True
        
        return False

    def fetch_and_store(
        self,
        max_results: int = None,
        days_back: int = 7,
    ) -> int:
        """
        Fetch papers from PubMed and store in database.
        
        Args:
            max_results: Maximum papers to fetch per query (defaults to config)
            days_back: How many days back to search
            
        Returns:
            Number of new papers stored
        """
        if max_results is None:
            max_results = settings.max_papers_per_scan
        
        per_query_limit = max(10, max_results // len(self.SEARCH_QUERIES))
        
        all_papers = []
        seen_ids = set()
        
        for query in self.SEARCH_QUERIES:
            try:
                papers = self.search(
                    query=query,
                    max_results=per_query_limit,
                    days_back=days_back,
                )
                
                # Deduplicate
                for paper in papers:
                    if paper.external_id not in seen_ids:
                        all_papers.append(paper)
                        seen_ids.add(paper.external_id)
                        
            except Exception as e:
                print(f"Error searching PubMed for '{query}': {e}")
                continue
            
            if len(all_papers) >= max_results:
                break
        
        # Limit to max_results
        all_papers = all_papers[:max_results]
        
        # Store in database
        for paper in all_papers:
            self.db.add(paper)
        
        self.db.commit()
        
        return len(all_papers)

