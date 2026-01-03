"""Claude-based biosecurity risk assessor."""
import json
import logging
import sys
from typing import Optional, Dict, Any, List
from datetime import datetime
from anthropic import Anthropic
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Paper, Assessment, Facility, ExtractedEntity
from .criteria import RiskCriteria
from ..research import FacilityResearcher

# Configure logging to flush immediately
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


ASSESSMENT_SYSTEM_PROMPT = """You are an expert biosecurity analyst evaluating research papers for potential biosecurity risks. Your role is to identify and assess risks related to:

1. **Pathogen Risk**: Identify dangerous pathogens mentioned (WHO priority pathogens, CDC Select Agents, novel/engineered organisms)
2. **Gain-of-Function (GoF)**: Identify research that enhances pathogen capabilities (transmissibility, virulence, host range, immune evasion)
3. **Containment Adequacy**: Assess if the research appears to be conducted at appropriate biosafety levels
4. **Dual-Use Concern**: Evaluate if methodology could be misused by bad actors

Be thorough but balanced. Not all pathogen research is concerning - focus on genuinely risky elements.

Score interpretation:
- 0-20: Minimal concern
- 21-40: Low concern  
- 41-60: Moderate concern
- 61-80: High concern
- 81-100: Critical concern"""


ASSESSMENT_USER_PROMPT = """Analyze this research paper for biosecurity concerns:

**Title**: {title}

**Authors**: {authors}

**Abstract**: {abstract}

{full_text_section}

{facility_context}

Provide your biosecurity risk analysis."""


# JSON Schema for structured output
ASSESSMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "pathogen_analysis": {
            "type": "object",
            "properties": {
                "score": {"type": "integer", "minimum": 0, "maximum": 100},
                "pathogens_identified": {"type": "array", "items": {"type": "string"}},
                "rationale": {"type": "string"}
            },
            "required": ["score", "pathogens_identified", "rationale"]
        },
        "gof_analysis": {
            "type": "object",
            "properties": {
                "score": {"type": "integer", "minimum": 0, "maximum": 100},
                "indicators_found": {"type": "array", "items": {"type": "string"}},
                "rationale": {"type": "string"}
            },
            "required": ["score", "indicators_found", "rationale"]
        },
        "containment_analysis": {
            "type": "object",
            "properties": {
                "score": {"type": "integer", "minimum": 0, "maximum": 100},
                "concerns": {"type": "array", "items": {"type": "string"}},
                "rationale": {"type": "string"}
            },
            "required": ["score", "concerns", "rationale"]
        },
        "dual_use_analysis": {
            "type": "object",
            "properties": {
                "score": {"type": "integer", "minimum": 0, "maximum": 100},
                "concerns": {"type": "array", "items": {"type": "string"}},
                "rationale": {"type": "string"}
            },
            "required": ["score", "concerns", "rationale"]
        },
        "overall_assessment": {
            "type": "object",
            "properties": {
                "risk_summary": {"type": "string"},
                "key_concerns": {"type": "array", "items": {"type": "string"}},
                "recommended_action": {"type": "string", "enum": ["flag_for_review", "monitor", "no_action"]}
            },
            "required": ["risk_summary", "key_concerns", "recommended_action"]
        },
        "extracted_entities": {
            "type": "object",
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
    """Assesses research papers for biosecurity risks using Claude."""
    
    def __init__(self, db: Session):
        """Initialize assessor with database session."""
        self.db = db
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.facility_researcher = FacilityResearcher(db) if settings.auto_research_facilities else None
    
    def _get_facility_context(self, paper: Paper) -> str:
        """Get facility context if available from entities."""
        entities = self.db.query(ExtractedEntity).filter(
            ExtractedEntity.paper_id == paper.id,
            ExtractedEntity.entity_type == "facility"
        ).all()
        
        if not entities:
            return ""
        
        context_parts = ["**Known Facility Information**:"]
        for entity in entities:
            if entity.facility:
                facility = entity.facility
                context_parts.append(
                    f"- {facility.name}: BSL-{facility.bsl_level or 'Unknown'}, "
                    f"{facility.country or 'Unknown location'}"
                )
            else:
                context_parts.append(f"- {entity.entity_value} (unverified)")
        
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
    
    def assess_paper(self, paper: Paper) -> Optional[Assessment]:
        """
        Assess a paper for biosecurity risks using Claude.
        
        Args:
            paper: Paper model instance to assess
            
        Returns:
            Assessment model instance (committed to DB), or None if assessment fails
        """
        # Auto-research facilities mentioned in the paper
        if self.facility_researcher and paper.abstract:
            try:
                self.facility_researcher.research_facilities_from_text(paper.abstract)
            except Exception as e:
                print(f"Facility research error for paper {paper.id}: {e}")
        
        # Build prompt
        authors = self._parse_authors(paper.authors)
        
        full_text_section = ""
        if paper.full_text:
            # Truncate if too long
            text = paper.full_text[:15000] if len(paper.full_text) > 15000 else paper.full_text
            full_text_section = f"**Full Text (excerpt)**:\n{text}"
        
        facility_context = self._get_facility_context(paper)
        
        user_prompt = ASSESSMENT_USER_PROMPT.format(
            title=paper.title,
            authors=authors,
            abstract=paper.abstract or "No abstract available",
            full_text_section=full_text_section,
            facility_context=facility_context,
        )
        
        try:
            # Call Claude with structured output
            logger.info(f"Calling Claude for paper {paper.id}: {paper.title[:50]}...")
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=ASSESSMENT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                extra_headers={
                    "anthropic-beta": "structured-outputs-2025-11-13"
                },
                extra_body={
                    "output_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "biosecurity_assessment",
                            "schema": ASSESSMENT_SCHEMA,
                            "strict": True
                        }
                    }
                }
            )
            
            # Parse response - guaranteed valid JSON with structured outputs
            response_text = response.content[0].text
            logger.info(f"Claude response received for paper {paper.id}, parsing JSON...")
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
            
            # Create assessment
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
                model_version=self.model,
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

