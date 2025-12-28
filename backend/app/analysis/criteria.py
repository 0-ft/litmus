"""Biosecurity risk assessment criteria definitions."""
from dataclasses import dataclass
from typing import List


@dataclass
class RiskCriteria:
    """Biosecurity risk assessment criteria and reference data."""
    
    # WHO Priority Pathogens (examples from WHO priority pathogen list)
    WHO_PRIORITY_PATHOGENS = [
        # Bacteria
        "Acinetobacter baumannii",
        "Pseudomonas aeruginosa",
        "Enterobacteriaceae",
        "Enterococcus faecium",
        "Staphylococcus aureus",
        "Helicobacter pylori",
        "Campylobacter",
        "Salmonella",
        "Neisseria gonorrhoeae",
        "Streptococcus pneumoniae",
        "Haemophilus influenzae",
        "Shigella",
        "Mycobacterium tuberculosis",
        "Yersinia pestis",
        "Bacillus anthracis",
        "Francisella tularensis",
        "Brucella",
        "Burkholderia mallei",
        "Burkholderia pseudomallei",
        "Clostridium botulinum",
        "Vibrio cholerae",
        
        # Viruses
        "Ebola virus",
        "Marburg virus",
        "Lassa virus",
        "SARS-CoV",
        "SARS-CoV-2",
        "MERS-CoV",
        "Nipah virus",
        "Hendra virus",
        "Influenza H5N1",
        "Influenza H7N9",
        "Crimean-Congo hemorrhagic fever virus",
        "Rift Valley fever virus",
        "Hantavirus",
        "Variola virus",
        "Monkeypox virus",
        "Junin virus",
        "Machupo virus",
        "Dengue virus",
        "Zika virus",
        "Yellow fever virus",
        "Japanese encephalitis virus",
        "West Nile virus",
        "Chikungunya virus",
        "Rabies virus",
        "HIV",
        "Hepatitis B virus",
        "Hepatitis C virus",
    ]
    
    # CDC Select Agents (Tier 1 - highest concern)
    CDC_SELECT_AGENTS_TIER1 = [
        "Bacillus anthracis",
        "Clostridium botulinum",
        "Francisella tularensis",
        "Yersinia pestis",
        "Ebola virus",
        "Marburg virus",
        "Variola virus",
        "Foot-and-mouth disease virus",
        "Rinderpest virus",
    ]
    
    # Gain-of-function indicators (keywords)
    GOF_INDICATORS = [
        "enhanced transmissibility",
        "increased transmissibility",
        "airborne transmission",
        "aerosol transmission",
        "enhanced virulence",
        "increased virulence",
        "enhanced pathogenicity",
        "host range expansion",
        "host adaptation",
        "immune evasion",
        "antibody escape",
        "vaccine escape",
        "antiviral resistance",
        "drug resistance",
        "serial passage",
        "directed evolution",
        "gain of function",
        "gain-of-function",
        "GOF research",
        "enhanced pandemic potential",
        "pandemic potential",
        "chimeric virus",
        "recombinant virus",
        "reverse genetics",
    ]
    
    # Dual-use research indicators
    DUAL_USE_INDICATORS = [
        "detailed protocol",
        "step-by-step",
        "synthesis",
        "de novo synthesis",
        "genome synthesis",
        "reconstruction",
        "reconstitution",
        "enhancement",
        "weaponization",
        "aerosolization",
        "delivery mechanism",
        "dissemination",
        "mass production",
        "scale up",
        "stability enhancement",
    ]
    
    # BSL requirements for select pathogens
    PATHOGEN_BSL_REQUIREMENTS = {
        # BSL-4 required
        "Ebola virus": 4,
        "Marburg virus": 4,
        "Lassa virus": 4,
        "Variola virus": 4,
        "Crimean-Congo hemorrhagic fever virus": 4,
        "Nipah virus": 4,
        "Hendra virus": 4,
        "Junin virus": 4,
        "Machupo virus": 4,
        
        # BSL-3 required
        "SARS-CoV": 3,
        "SARS-CoV-2": 3,
        "MERS-CoV": 3,
        "Mycobacterium tuberculosis": 3,
        "Yersinia pestis": 3,
        "Bacillus anthracis": 3,
        "Francisella tularensis": 3,
        "Brucella": 3,
        "HIV": 3,
        "Influenza H5N1": 3,
        "Influenza H7N9": 3,
        "Yellow fever virus": 3,
        "West Nile virus": 3,
        "Japanese encephalitis virus": 3,
        "Rabies virus": 3,
        "Rift Valley fever virus": 3,
        "Hantavirus": 3,
        
        # BSL-2 required
        "Salmonella": 2,
        "Hepatitis B virus": 2,
        "Hepatitis C virus": 2,
        "Dengue virus": 2,
        "Zika virus": 2,
        "Chikungunya virus": 2,
        "Staphylococcus aureus": 2,
        "Vibrio cholerae": 2,
    }
    
    @classmethod
    def get_pathogen_risk_level(cls, pathogen: str) -> int:
        """
        Get risk level for a pathogen (1-5).
        
        5 = Tier 1 Select Agent
        4 = BSL-4 required
        3 = BSL-3 required / WHO priority
        2 = BSL-2 required
        1 = Lower risk
        """
        pathogen_lower = pathogen.lower()
        
        # Check Tier 1 select agents
        for agent in cls.CDC_SELECT_AGENTS_TIER1:
            if agent.lower() in pathogen_lower or pathogen_lower in agent.lower():
                return 5
        
        # Check BSL requirements
        for known_pathogen, bsl in cls.PATHOGEN_BSL_REQUIREMENTS.items():
            if known_pathogen.lower() in pathogen_lower or pathogen_lower in known_pathogen.lower():
                if bsl == 4:
                    return 4
                elif bsl == 3:
                    return 3
                else:
                    return 2
        
        # Check WHO priority list
        for who_pathogen in cls.WHO_PRIORITY_PATHOGENS:
            if who_pathogen.lower() in pathogen_lower or pathogen_lower in who_pathogen.lower():
                return 3
        
        return 1
    
    @classmethod
    def get_required_bsl(cls, pathogen: str) -> int:
        """Get required BSL level for a pathogen."""
        pathogen_lower = pathogen.lower()
        
        for known_pathogen, bsl in cls.PATHOGEN_BSL_REQUIREMENTS.items():
            if known_pathogen.lower() in pathogen_lower or pathogen_lower in known_pathogen.lower():
                return bsl
        
        # Default to BSL-2 for unknown pathogens mentioned in research
        return 2

