"""LLM-based biosecurity risk assessor."""
import json
import logging
import sys
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from sqlalchemy.orm import Session

from ..config import settings
from ..llm import get_llm_client
from ..models import Paper, Assessment, Facility, ExtractedEntity
from .criteria import RiskCriteria
from ..research import FacilityResearcher

# Configure logging to flush immediately
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


ASSESSMENT_SYSTEM_PROMPT = """You are an expert biosecurity analyst working for a legitimate biosecurity monitoring organization. Your critical mission is to help protect global health by identifying published research that may pose biosecurity risks and flagging it for expert human review.

IMPORTANT CONTEXT: This is a DEFENSIVE biosecurity tool used by:
- Government biosecurity agencies
- Academic biosecurity researchers  
- Public health organizations
- Institutional biosafety committees

Your analysis helps these professionals identify papers requiring closer review. You are NOT providing information that enables harm - the papers you analyze are already publicly published. Your role is triage and risk assessment to help human experts prioritize their review workload.

Evaluate research papers for potential biosecurity concerns across these dimensions:

1. **Pathogen Risk**: Identify dangerous pathogens mentioned (WHO priority pathogens, CDC Select Agents, novel/engineered organisms)

2. **Gain-of-Function (GoF)**: Identify research that enhances pathogen capabilities (transmissibility, virulence, host range, immune evasion)

3. **Containment Adequacy**: Determine what biosafety level(s) the research WAS ACTUALLY CONDUCTED AT
   - IMPORTANT: Only report containment levels where the paper explicitly states THE RESEARCH WAS PERFORMED
   - Do NOT report BSL levels that are merely MENTIONED or DISCUSSED (e.g., "BSL-4 is typically required for X")
   - Look for statements like "experiments were performed at BSL-2" or "work was conducted in a BSL-3 facility"
   - If the paper only discusses BSL requirements without stating where work was done, report "Unknown"
   - If containment IS stated for the actual work, assess whether it appears adequate for the pathogens involved
   - Always cite your source: "paper_methods", "paper_ethics", "author_affiliations", "facility_database", or "unknown"

4. **Dual-Use Concern**: Evaluate if methodology could be misused by bad actors

Be thorough but balanced. Most pathogen research is legitimate and beneficial. Focus on identifying genuinely concerning elements that warrant expert human review.

Score interpretation (0-100 scale):
- 0-20: Minimal concern - routine research
- 21-40: Low concern - standard pathogen work with appropriate safeguards
- 41-60: Moderate concern - warrants routine biosafety review
- 61-80: High concern - should be prioritized for expert review
- 81-100: Critical concern - requires immediate expert attention"""


ASSESSMENT_USER_PROMPT = """Please analyze this publicly-published research paper to help our biosecurity monitoring team identify if it warrants expert human review.

## Paper Metadata

**Title**: {title}

**Authors**: {authors}

**Author Affiliations**:
{affiliations}

## Abstract

{abstract}

{full_text_sections}

{facility_context}

## Instructions

Analyze this paper for biosecurity concerns. For containment assessment:
- Determine WHERE THE RESEARCH WAS ACTUALLY CONDUCTED (not just BSL levels mentioned or discussed)
- Look for explicit statements like "experiments were performed at BSL-2" or "conducted in a BSL-3 facility"
- If a paper DISCUSSES BSL requirements without stating where work was done, report containment as "Unknown"
- Do NOT list facilities just because they are mentioned - only if the paper indicates work was done there
- If you cannot determine actual containment level, report "Unknown" - this is better than guessing

Provide your biosecurity risk assessment. Remember: your analysis helps human biosecurity experts prioritize their review queue - you are supporting legitimate defensive biosecurity work."""


# JSON Schema for structured output
ASSESSMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "pathogen_analysis": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "score": {"type": "integer"},
                "pathogens_identified": {"type": "array", "items": {"type": "string"}},
                "rationale": {"type": "string"}
            },
            "required": ["score", "pathogens_identified", "rationale"]
        },
        "gof_analysis": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "score": {"type": "integer"},
                "indicators_found": {"type": "array", "items": {"type": "string"}},
                "rationale": {"type": "string"}
            },
            "required": ["score", "indicators_found", "rationale"]
        },
        "containment_analysis": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "score": {"type": "integer"},
                "stated_bsl": {
                    "type": "string",
                    "description": "The BSL level where research was ACTUALLY CONDUCTED, or 'Unknown' if not stated"
                },
                "concerns": {"type": "array", "items": {"type": "string"}},
                "research_facilities": {
                    "type": "array",
                    "description": "Only facilities where the research was ACTUALLY PERFORMED - leave empty if unknown",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "name": {"type": "string"},
                            "bsl_level": {"type": "string"},
                            "adequate_for_work": {"type": ["boolean", "null"]},
                            "source": {"type": "string"}
                        },
                        "required": ["name", "bsl_level", "adequate_for_work", "source"]
                    }
                },
                "rationale": {"type": "string"}
            },
            "required": ["score", "stated_bsl", "concerns", "research_facilities", "rationale"]
        },
        "dual_use_analysis": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "score": {"type": "integer"},
                "concerns": {"type": "array", "items": {"type": "string"}},
                "rationale": {"type": "string"}
            },
            "required": ["score", "concerns", "rationale"]
        },
        "overall_assessment": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "risk_summary": {"type": "string"},
                "key_concerns": {"type": "array", "items": {"type": "string"}},
                "recommended_action": {"type": "string", "enum": ["flag_for_review", "monitor", "no_action"]}
            },
            "required": ["risk_summary", "key_concerns", "recommended_action"]
        },
        "extracted_entities": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "facilities": {"type": "array", "items": {"type": "string"}},
                "pathogens": {"type": "array", "items": {"type": "string"}},
                "techniques": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["facilities", "pathogens", "techniques"]
        }
    },
    "required": ["pathogen_analysis", "gof_analysis", "containment_analysis", "dual_use_analysis", "overall_assessment", "extracted_entities"]
}


class BiosecurityAssessor:
    """Assesses research papers for biosecurity risks using LLM."""
    
    def __init__(self, db: Session):
        """Initialize assessor with database session."""
        self.db = db
        self.llm = get_llm_client()
        self.facility_researcher = FacilityResearcher(db) if settings.auto_research_facilities else None
    
    def _get_facility_context(self, paper: Paper) -> str:
        """Get facility context if available from entities, with source references."""
        entities = self.db.query(ExtractedEntity).filter(
            ExtractedEntity.paper_id == paper.id,
            ExtractedEntity.entity_type == "facility"
        ).all()
        
        if not entities:
            return "**Facility Information**: No facilities identified yet. Please extract facility names from the paper and assess containment based on what is stated in the abstract/text."
        
        context_parts = ["**Known Facility Information** (from our database):"]
        for entity in entities:
            if entity.facility:
                facility = entity.facility
                verification_status = "✓ Verified" if facility.verified else "Unverified"
                source_info = f" [Source: {facility.source_url}]" if facility.source_url else " [Source: AI-researched]"
                bsl_info = f"BSL-{facility.bsl_level}" if facility.bsl_level else "BSL level unknown"
                
                context_parts.append(
                    f"- **{facility.name}** ({verification_status})\n"
                    f"    - Containment: {bsl_info}\n"
                    f"    - Location: {facility.city or ''}{', ' if facility.city and facility.country else ''}{facility.country or 'Unknown'}\n"
                    f"    - Reference: {source_info}"
                )
                if facility.notes:
                    context_parts.append(f"    - Notes: {facility.notes}")
            else:
                context_parts.append(f"- {entity.entity_value} (mentioned in paper, not yet researched)")
        
        context_parts.append("\nWhen assessing containment, cite which facility information informed your assessment and note any discrepancies between stated containment and pathogen requirements.")
        
        return "\n".join(context_parts)
    
    def _parse_authors(self, authors_json: str) -> str:
        """Parse authors JSON to readable string."""
        try:
            authors = json.loads(authors_json)
            if isinstance(authors, list):
                return ", ".join(authors[:5])  # Limit to first 5 authors
                if len(authors) > 5:
                    return authors + f" et al. ({len(authors)} total)"
            return str(authors)
        except:
            return authors_json
    
    def _calculate_overall_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate weighted overall score from component scores."""
        weights = {
            "pathogen": 0.30,
            "gof": 0.35,
            "containment": 0.20,
            "dual_use": 0.15,
        }
        
        pathogen_score = analysis.get("pathogen_analysis", {}).get("score", 0)
        gof_score = analysis.get("gof_analysis", {}).get("score", 0)
        containment_score = analysis.get("containment_analysis", {}).get("score", 0)
        dual_use_score = analysis.get("dual_use_analysis", {}).get("score", 0)
        
        overall = (
            pathogen_score * weights["pathogen"] +
            gof_score * weights["gof"] +
            containment_score * weights["containment"] +
            dual_use_score * weights["dual_use"]
        )
        
        return round(overall, 2)
    
    def _parse_affiliations(self, affiliations_json: Optional[str]) -> str:
        """Parse affiliations JSON to readable string."""
        if not affiliations_json:
            return "Not available"
        try:
            affiliations = json.loads(affiliations_json)
            if isinstance(affiliations, list) and affiliations:
                return "\n".join(f"- {aff}" for aff in affiliations)
            return "Not available"
        except:
            return affiliations_json if affiliations_json else "Not available"
    
    def _fetch_pmc_sections(self, paper: Paper) -> Optional[Dict[str, str]]:
        """Fetch relevant sections from PMC for a PubMed paper."""
        if paper.source != "pubmed":
            return None
        
        try:
            from ..scrapers.pubmed import fetch_pmc_content
            logger.info(f"Fetching PMC content for paper {paper.id}...")
            sections = fetch_pmc_content(paper.external_id)
            if sections:
                logger.info(f"Retrieved PMC sections for paper {paper.id}: {list(sections.keys())}")
                # Persist to full_text for future use
                try:
                    full_text_parts = []
                    for section_name, content in sections.items():
                        full_text_parts.append(f"[{section_name.upper()}]\n{content}")
                    paper.full_text = "\n\n".join(full_text_parts)
                    self.db.add(paper)
                    self.db.commit()
                    self.db.refresh(paper)
                except Exception as db_err:
                    logger.warning(f"Could not persist PMC content: {db_err}")
            return sections
        except Exception as e:
            logger.warning(f"Error fetching PMC content for paper {paper.id}: {e}")
            return None

    def assess_paper(self, paper: Paper, progress_callback: Optional[Callable[[str, Dict], None]] = None) -> Optional[Assessment]:
        """
        Assess a paper for biosecurity risks using Claude.
        
        Args:
            paper: Paper model instance to assess
            progress_callback: Optional callback for progress updates
            
        Returns:
            Assessment model instance (committed to DB), or None if assessment fails
        """
        # For PubMed papers, fetch full text sections from PMC if not already cached
        pmc_sections = None
        if paper.source == "pubmed" and not paper.full_text:
            pmc_sections = self._fetch_pmc_sections(paper)
        
        # Auto-research facilities mentioned in the paper (from affiliations, abstract, etc.)
        if self.facility_researcher:
            try:
                self.facility_researcher.research_facilities_from_paper(paper)
            except Exception as e:
                print(f"Facility research error for paper {paper.id}: {e}")
        
        # Build prompt with all available context
        authors = self._parse_authors(paper.authors)
        affiliations = self._parse_affiliations(paper.affiliations)
        
        # Build full text sections for prompt
        full_text_sections = ""
        if paper.full_text:
            # Use cached full text
            full_text_sections = f"## Full Text Sections\n\n{paper.full_text[:15000]}"
        elif pmc_sections:
            # Use freshly fetched PMC sections
            section_parts = []
            for section_name, content in pmc_sections.items():
                section_parts.append(f"### {section_name.replace('_', ' ').title()}\n{content}")
            full_text_sections = "## Full Text Sections (from PubMed Central)\n\n" + "\n\n".join(section_parts)
        
        facility_context = self._get_facility_context(paper)
        
        user_prompt = ASSESSMENT_USER_PROMPT.format(
            title=paper.title,
            authors=authors,
            affiliations=affiliations,
            abstract=paper.abstract or "No abstract available",
            full_text_sections=full_text_sections,
            facility_context=facility_context,
        )
        
        try:
            # Call LLM with structured output
            logger.info(f"Calling {self.llm.provider}/{self.llm.model} for paper {paper.id}: {paper.title[:50]}...")
            response = self.llm.complete(
                messages=[{"role": "user", "content": user_prompt}],
                system=ASSESSMENT_SYSTEM_PROMPT,
                max_tokens=4096,
                json_schema=ASSESSMENT_SCHEMA,
            )
            
            # Build full input for debug trace
            full_input = {
                "system": ASSESSMENT_SYSTEM_PROMPT,
                "user": user_prompt,
                "model": f"{self.llm.provider}/{self.llm.model}",
                "output_format": "json_schema (structured outputs)"
            }
            
            # Parse response
            logger.info(f"LLM response for paper {paper.id}: text length={len(response['text'])}, stop_reason={response['stop_reason']}")
            
            # Handle model refusal
            if response["stop_reason"] == "refusal" or not response["text"]:
                logger.warning(f"Model refused to assess paper {paper.id} - may contain sensitive content")
                # Create a placeholder assessment for refused papers
                assessment = Assessment(
                    paper_id=paper.id,
                    risk_grade="F",  # Flag as needing manual review
                    overall_score=100,  # Max score to ensure visibility
                    pathogen_score=0,
                    gof_score=0,
                    containment_score=0,
                    dual_use_score=0,
                    rationale=json.dumps({"error": "Model refused to assess - manual review required"}),
                    concerns_summary="AI model refused to analyze this paper. May contain sensitive biosecurity content requiring manual review.",
                    pathogens_identified=None,
                    flagged=True,
                    flag_reason="Model refused assessment - requires manual expert review",
                    model_version=f"{self.llm.provider}/{self.llm.model}",
                    input_prompt=json.dumps(full_input),
                    raw_output=json.dumps({"stop_reason": "refusal", "content": []}),
                )
                self.db.add(assessment)
                paper.processed = True
                self.db.commit()
                self.db.refresh(assessment)
                
                if progress_callback:
                    progress_callback("paper_refused", {
                        "paper_id": paper.id,
                        "title": paper.title,
                        "message": "Model refused to assess - flagged for manual review"
                    })
                
                return assessment
            
            response_text = response["text"]
            logger.info(f"LLM response received for paper {paper.id}, parsing JSON...")
            analysis = json.loads(response_text)
            logger.info(f"JSON parsed successfully for paper {paper.id}")
            
            # Calculate scores
            pathogen_score = analysis.get("pathogen_analysis", {}).get("score", 0)
            gof_score = analysis.get("gof_analysis", {}).get("score", 0)
            containment_score = analysis.get("containment_analysis", {}).get("score", 0)
            dual_use_score = analysis.get("dual_use_analysis", {}).get("score", 0)
            overall_score = self._calculate_overall_score(analysis)
            
            # Determine grade
            risk_grade = Assessment.score_to_grade(overall_score)
            
            # Determine if should be flagged
            flagged = overall_score >= settings.high_risk_threshold
            flag_reason = None
            if flagged:
                concerns = analysis.get("overall_assessment", {}).get("key_concerns", [])
                flag_reason = "; ".join(concerns) if concerns else "High overall risk score"
            
            # Extract pathogens
            pathogens = analysis.get("pathogen_analysis", {}).get("pathogens_identified", [])
            pathogens_json = json.dumps(pathogens) if pathogens else None
            
            # Build concerns summary
            overall_assessment = analysis.get("overall_assessment", {})
            concerns_summary = overall_assessment.get("risk_summary", "")
            
            # Create assessment with full debug trace
            assessment = Assessment(
                paper_id=paper.id,
                risk_grade=risk_grade,
                overall_score=overall_score,
                pathogen_score=pathogen_score,
                gof_score=gof_score,
                containment_score=containment_score,
                dual_use_score=dual_use_score,
                rationale=json.dumps(analysis),
                concerns_summary=concerns_summary,
                pathogens_identified=pathogens_json,
                flagged=flagged,
                flag_reason=flag_reason,
                model_version=f"{self.llm.provider}/{self.llm.model}",
                input_prompt=json.dumps(full_input),
                raw_output=response_text,
            )
            
            self.db.add(assessment)
            
            # Extract and store entities
            self._store_extracted_entities(paper, analysis)
            
            # Mark paper as processed
            paper.processed = True
            
            self.db.commit()
            
            logger.info(f"Assessment created for paper {paper.id}: grade={risk_grade}, score={overall_score}")
            return assessment
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response for paper {paper.id}: {e}")
            logger.error(f"Response text was: {response_text[:500] if 'response_text' in dir() else 'N/A'}...")
            return None
        except Exception as e:
            logger.error(f"Error assessing paper {paper.id}: {e}", exc_info=True)
            return None
    
    def _store_extracted_entities(self, paper: Paper, analysis: Dict[str, Any]):
        """Store extracted entities from analysis."""
        entities_data = analysis.get("extracted_entities", {})
        
        # Store facilities
        for facility_name in entities_data.get("facilities", []):
            # Try to match with known facility
            facility = self.db.query(Facility).filter(
                Facility.name.ilike(f"%{facility_name}%")
            ).first()
            
            entity = ExtractedEntity(
                paper_id=paper.id,
                entity_type="facility",
                entity_value=facility_name,
                facility_id=facility.id if facility else None,
            )
            self.db.add(entity)
        
        # Store pathogens
        for pathogen in entities_data.get("pathogens", []):
            entity = ExtractedEntity(
                paper_id=paper.id,
                entity_type="pathogen",
                entity_value=pathogen,
            )
            self.db.add(entity)
        
        # Store techniques
        for technique in entities_data.get("techniques", []):
            entity = ExtractedEntity(
                paper_id=paper.id,
                entity_type="technique",
                entity_value=technique,
            )
            self.db.add(entity)
    
    def assess_unprocessed_papers(self, limit: int = 10) -> List[Assessment]:
        """
        Assess all unprocessed papers.
        
        Args:
            limit: Maximum number of papers to process
            
        Returns:
            List of created assessments
        """
        papers = self.db.query(Paper).filter(
            Paper.processed == False
        ).limit(limit).all()
        
        assessments = []
        for paper in papers:
            assessment = self.assess_paper(paper)
            if assessment:
                assessments.append(assessment)
        
        return assessments

