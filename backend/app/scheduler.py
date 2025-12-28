"""Background job scheduler for automated paper scanning and assessment."""
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .database import SessionLocal
from .scrapers import ArxivScraper, BiorxivScraper, PubmedScraper
from .analysis import BiosecurityAssessor
from .config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def scan_all_sources():
    """Scan all paper sources for new papers."""
    logger.info(f"[{datetime.now()}] Starting scheduled paper scan...")
    
    db = SessionLocal()
    total_papers = 0
    
    try:
        # arXiv
        try:
            arxiv_scraper = ArxivScraper(db)
            count = arxiv_scraper.fetch_and_store(max_results=50)
            total_papers += count
            logger.info(f"  arXiv: fetched {count} papers")
        except Exception as e:
            logger.error(f"  arXiv scan error: {e}")
        
        # bioRxiv
        try:
            biorxiv_scraper = BiorxivScraper(db)
            count = biorxiv_scraper.fetch_and_store(max_results=50, days_back=7)
            total_papers += count
            logger.info(f"  bioRxiv: fetched {count} papers")
        except Exception as e:
            logger.error(f"  bioRxiv scan error: {e}")
        
        # PubMed
        try:
            pubmed_scraper = PubmedScraper(db)
            count = pubmed_scraper.fetch_and_store(max_results=50, days_back=7)
            total_papers += count
            logger.info(f"  PubMed: fetched {count} papers")
        except Exception as e:
            logger.error(f"  PubMed scan error: {e}")
        
        logger.info(f"Scan complete. Total new papers: {total_papers}")
        
    finally:
        db.close()
    
    return total_papers


def assess_pending_papers():
    """Assess unprocessed papers using Claude."""
    logger.info(f"[{datetime.now()}] Starting scheduled assessment...")
    
    if not settings.anthropic_api_key:
        logger.warning("Skipping assessment: Anthropic API key not configured")
        return 0
    
    db = SessionLocal()
    
    try:
        assessor = BiosecurityAssessor(db)
        assessments = assessor.assess_unprocessed_papers(limit=10)
        
        flagged_count = sum(1 for a in assessments if a.flagged)
        logger.info(f"Assessment complete. Processed: {len(assessments)}, Flagged: {flagged_count}")
        
        # Log any flagged papers
        for assessment in assessments:
            if assessment.flagged:
                logger.warning(
                    f"FLAGGED PAPER: ID={assessment.paper_id}, "
                    f"Grade={assessment.risk_grade}, Score={assessment.overall_score:.1f}"
                )
        
        return len(assessments)
        
    finally:
        db.close()


def run_full_pipeline():
    """Run both scanning and assessment."""
    logger.info("=" * 50)
    logger.info("Running full biosecurity monitoring pipeline")
    logger.info("=" * 50)
    
    # Scan for new papers
    new_papers = scan_all_sources()
    
    # Assess pending papers
    if new_papers > 0 or True:  # Always try to assess any pending
        assess_pending_papers()
    
    logger.info("Pipeline complete")
    logger.info("=" * 50)


# Global scheduler instance
scheduler = BackgroundScheduler()


def start_scheduler():
    """Start the background scheduler."""
    # Add jobs
    scheduler.add_job(
        run_full_pipeline,
        trigger=IntervalTrigger(hours=settings.scan_interval_hours),
        id="full_pipeline",
        name="Full biosecurity monitoring pipeline",
        replace_existing=True,
    )
    
    # Start the scheduler
    scheduler.start()
    logger.info(f"Scheduler started. Running every {settings.scan_interval_hours} hours.")


def stop_scheduler():
    """Stop the background scheduler."""
    scheduler.shutdown()
    logger.info("Scheduler stopped.")


# CLI entry point
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Biomon scheduler commands")
    parser.add_argument("command", choices=["scan", "assess", "full", "daemon"],
                       help="Command to run")
    
    args = parser.parse_args()
    
    if args.command == "scan":
        scan_all_sources()
    elif args.command == "assess":
        assess_pending_papers()
    elif args.command == "full":
        run_full_pipeline()
    elif args.command == "daemon":
        print("Starting scheduler daemon...")
        start_scheduler()
        try:
            # Keep running
            import time
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            stop_scheduler()

