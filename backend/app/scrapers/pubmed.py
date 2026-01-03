"""PubMed paper scraper for biology research papers."""
import json
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from sqlalchemy.orm import Session

try:
    from Bio import Entrez
    BIOPYTHON_AVAILABLE = True
except ImportError:
    BIOPYTHON_AVAILABLE = False

from ..models import Paper
from ..config import settings


def _clean_xml_text(text: str) -> str:
    """Remove XML tags and normalize whitespace."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _extract_section(xml_content: str, section_titles: List[str], max_chars: int = 3000) -> Optional[str]:
    """Extract a section from PMC XML by title patterns."""
    for title in section_titles:
        # Look for section with matching title
        pattern = rf'<sec[^>]*>.*?<title[^>]*>.*?{title}.*?</title>(.*?)</sec>'
        match = re.search(pattern, xml_content, re.IGNORECASE | re.DOTALL)
        if match:
            content = _clean_xml_text(match.group(1))
            if len(content) > max_chars:
                content = content[:max_chars] + "..."
            return content
    return None


def fetch_pmc_content(pmid: str) -> Optional[Dict[str, str]]:
    """
    Fetch relevant content sections from PubMed Central.
    
    Args:
        pmid: PubMed ID
        
    Returns:
        Dict with extracted sections (methods, ethics, acknowledgments, etc.)
        or None if PMC full text not available
    """
    if not BIOPYTHON_AVAILABLE:
        return None
    
    try:
        # First get PMC ID via elink
        Entrez.email = "litmus@example.com"
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
        xml_content = pmc_handle.read().decode('utf-8')
        pmc_handle.close()
        
        # Extract relevant sections
        sections = {}
        
        # Methods section - often contains BSL/containment info
        methods = _extract_section(xml_content, [
            r'Materials?\s+and\s+Methods?',
            r'Methods?',
            r'Experimental\s+Procedures?',
            r'Study\s+Design',
        ], max_chars=5000)
        if methods:
            sections['methods'] = methods
        
        # Ethics/Biosafety section - contains ethics approvals and biosafety statements
        ethics = _extract_section(xml_content, [
            r'Ethics',
            r'Biosafety',
            r'Ethical\s+Statement',
            r'Ethics\s+Approval',
            r'Institutional\s+Review',
        ], max_chars=2000)
        if ethics:
            sections['ethics'] = ethics
        
        # Acknowledgments - often mentions funding and facilities
        ack = _extract_section(xml_content, [
            r'Acknowledgments?',
            r'Funding',
        ], max_chars=1500)
        if ack:
            sections['acknowledgments'] = ack
        
        # Author contributions/affiliations often in a notes section
        author_notes = _extract_section(xml_content, [
            r'Author\s+Contributions?',
            r'Author\s+Notes?',
            r'Competing\s+Interests?',
        ], max_chars=1000)
        if author_notes:
            sections['author_notes'] = author_notes
        
        return sections if sections else None
        
    except Exception as e:
        print(f"Error fetching PMC content for {pmid}: {e}")
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

