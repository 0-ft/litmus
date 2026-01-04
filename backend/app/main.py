"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .api import papers, assessments, facilities, scan, reference_assessments

# Create FastAPI app
app = FastAPI(
    title="Litmus",
    description="Biosecurity Research Paper Risk Scanner - AI-powered screening of biology papers for biosecurity concerns",
    version="0.1.0",
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(papers.router, prefix="/api/papers", tags=["papers"])
app.include_router(assessments.router, prefix="/api/assessments", tags=["assessments"])
app.include_router(facilities.router, prefix="/api/facilities", tags=["facilities"])
app.include_router(scan.router, prefix="/api/scan", tags=["scan"])
app.include_router(reference_assessments.router, prefix="/api/reference", tags=["reference"])


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()
    
    # Optionally start scheduler (set ENABLE_SCHEDULER=true)
    import os
    if os.getenv("ENABLE_SCHEDULER", "false").lower() == "true":
        from .scheduler import start_scheduler
        start_scheduler()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    import os
    if os.getenv("ENABLE_SCHEDULER", "false").lower() == "true":
        from .scheduler import stop_scheduler
        stop_scheduler()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Litmus",
        "description": "Biosecurity Research Paper Risk Scanner",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

