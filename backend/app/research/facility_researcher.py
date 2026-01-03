"""Research facility information using web search and LLM analysis."""
import json
import httpx
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from ..config import settings
from ..llm import get_llm_client
from ..models import Facility


FACILITY_RESEARCH_PROMPT = """You are researching biosafety information about a research facility.

Based on the search results provided, extract factual information about this facility:

Facility name mentioned in paper: {facility_name}

Search results:
{search_results}

Extract ONLY factual information that is clearly stated in the search results. 
IMPORTANT: Only report BSL levels that are explicitly stated in search results. Do not guess or infer BSL levels."""


# JSON Schema for facility research structured output
FACILITY_RESEARCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "found": {"type": "boolean"},
        "official_name": {"type": "string"},
        "aliases": {"type": "array", "items": {"type": "string"}},
        "country": {"type": "string"},
        "city": {"type": "string"},
        "bsl_level": {"type": "integer"},
        "notes": {"type": "string"},
        "source_urls": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
    },
    "required": ["found", "official_name", "aliases", "country", "city", "bsl_level", "notes", "source_urls", "confidence"]
}


class FacilityResearcher:
    """Researches facility information using web search."""
    
    def __init__(self, db: Session):
        """Initialize researcher with database session."""
        self.db = db
        self.llm = get_llm_client()
        self.http_client = httpx.Client(timeout=30.0)
    
    def search_web(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search the web for information using Tavily API.
        
        Requires TAVILY_API_KEY environment variable.
        Get an API key at https://tavily.com
        """
        if not settings.tavily_api_key:
            print(f"[FacilityResearcher] Web search not configured (set TAVILY_API_KEY). Query: {query}")
            return []
        
        try:
            response = self.http_client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.tavily_api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": num_results,
                    "include_raw_content": False,
                }
            )
            response.raise_for_status()
            return response.json().get("results", [])
        except Exception as e:
            print(f"[FacilityResearcher] Search error: {e}")
            return []
    
    def research_facility(self, facility_name: str) -> Optional[Dict[str, Any]]:
        """
        Research a facility by name using web search and LLM analysis.
        
        Args:
            facility_name: Name of facility to research
            
        Returns:
            Dict with facility information, or None if not found
        """
        # Check if we already have this facility
        existing = self.db.query(Facility).filter(
            Facility.name.ilike(f"%{facility_name}%")
        ).first()
        
        if existing:
            return {
                "facility_id": existing.id,
                "name": existing.name,
                "bsl_level": existing.bsl_level,
                "country": existing.country,
                "verified": existing.verified,
                "from_cache": True,
            }
        
        # Search for facility information
        search_queries = [
            f'"{facility_name}" biosafety level BSL',
            f'"{facility_name}" research laboratory containment',
        ]
        
        all_results = []
        for query in search_queries:
            results = self.search_web(query)
            all_results.extend(results)
        
        if not all_results:
            # No search results - can't verify facility
            return None
        
        # Format search results for LLM
        formatted_results = []
        for i, result in enumerate(all_results[:10]):  # Limit to top 10
            formatted_results.append(
                f"[{i+1}] {result.get('title', 'No title')}\n"
                f"URL: {result.get('url', 'No URL')}\n"
                f"Content: {result.get('content', result.get('snippet', 'No content'))}\n"
            )
        
        search_text = "\n---\n".join(formatted_results)
        
        # Use LLM with structured output to extract facility information
        try:
            response = self.llm.complete(
                messages=[{
                    "role": "user",
                    "content": FACILITY_RESEARCH_PROMPT.format(
                        facility_name=facility_name,
                        search_results=search_text,
                    )
                }],
                max_tokens=1024,
                json_schema=FACILITY_RESEARCH_SCHEMA,
            )
            
            # Handle potential refusals
            if not response["text"] or response["stop_reason"] == "refusal":
                print(f"Model refused or returned empty response for facility: {facility_name}")
                return None
            
            result = json.loads(response["text"])
            
            if not result.get("found"):
                return None
            
            # Create or update facility record
            facility = Facility(
                name=result.get("official_name") or facility_name,
                aliases=json.dumps(result.get("aliases", [])),
                country=result.get("country"),
                city=result.get("city"),
                bsl_level=result.get("bsl_level"),
                notes=result.get("notes"),
                source_url=result.get("source_urls", [None])[0],
                verified=False,  # Always requires human verification
            )
            
            self.db.add(facility)
            self.db.commit()
            self.db.refresh(facility)
            
            return {
                "facility_id": facility.id,
                "name": facility.name,
                "bsl_level": facility.bsl_level,
                "country": facility.country,
                "confidence": result.get("confidence"),
                "verified": False,
                "from_cache": False,
            }
            
        except Exception as e:
            print(f"Error researching facility {facility_name}: {e}")
            return None
    
    def research_facilities_from_paper(self, paper) -> List[Dict[str, Any]]:
        """
        Extract and research facility names from paper metadata.
        
        Looks in (priority order):
        1. Author affiliations (most reliable)
        2. Abstract text
        3. Full text if available
        
        Args:
            paper: Paper model instance
            
        Returns:
            List of researched facility information
        """
        # Build combined text from all sources
        text_parts = []
        
        # Priority 1: Affiliations (most reliable source)
        if paper.affiliations:
            try:
                affiliations = json.loads(paper.affiliations)
                if affiliations:
                    text_parts.append("Author Affiliations:\n" + "\n".join(affiliations))
            except:
                pass
        
        # Priority 2: Abstract
        if paper.abstract:
            text_parts.append("Abstract:\n" + paper.abstract)
        
        # Priority 3: Full text (first 5000 chars)
        if paper.full_text:
            text_parts.append("Full text excerpt:\n" + paper.full_text[:5000])
        
        if not text_parts:
            return []
        
        combined_text = "\n\n".join(text_parts)
        return self.research_facilities_from_text(combined_text)
    
    def research_facilities_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract and research facility names from text.
        
        Args:
            text: Combined paper text (affiliations, abstract, etc.)
            
        Returns:
            List of researched facility information
        """
        # Use LLM with structured output to extract facility names
        try:
            facility_extraction_schema = {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "facilities": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["facilities"]
            }
            
            response = self.llm.complete(
                system="""You are helping a biosecurity monitoring system identify research facilities for containment verification purposes. 
This is legitimate defensive work to help ensure proper biosafety practices in published research.
Your task is simply to extract organization names from text - this helps biosecurity professionals verify appropriate containment levels.""",
                messages=[{
                    "role": "user",
                    "content": f"""Extract the names of research institutions, universities, or laboratories from this text.
We need to identify facilities to verify they have appropriate biosafety containment for the research described.

Text from a published research paper:
{text[:5000]}

List the organization/institution names found."""
                }],
                max_tokens=1024,
                json_schema=facility_extraction_schema,
            )
            
            # Handle potential refusals
            if not response["text"] or response["stop_reason"] == "refusal":
                print(f"Model refused or returned empty response for facility extraction")
                return []
            
            result = json.loads(response["text"])
            facility_names = result.get("facilities", [])
            
            # Research each facility
            results = []
            for name in facility_names[:5]:  # Limit to 5 facilities
                info = self.research_facility(name)
                if info:
                    results.append(info)
            
            return results
            
        except Exception as e:
            print(f"Error extracting facilities from text: {e}")
            return []

