"""Application configuration using pydantic-settings."""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys
    anthropic_api_key: str = ""
    ncbi_api_key: str = ""  # For PubMed higher rate limits
    tavily_api_key: str = ""  # For web search (facility research)
    
    # Database
    database_url: str = "sqlite:///data/litmus.db"
    
    # Scanning settings
    scan_interval_hours: int = 24
    max_papers_per_scan: int = 100
    
    # Risk thresholds
    high_risk_threshold: int = 70  # Papers scoring above this get flagged
    
    # Claude model
    claude_model: str = "claude-sonnet-4-20250514"
    
    # Facility research
    auto_research_facilities: bool = True  # Auto-research facilities mentioned in papers
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()

# Ensure data directory exists
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

