# Litmus - Biosecurity Research Paper Risk Scanner

AI-powered screening of biology research papers for biosecurity risks. Like a litmus test for dangerous research.

## Features

- **Multi-source paper ingestion**: Fetches papers from arXiv, bioRxiv, medRxiv, and PubMed
- **AI-powered risk assessment**: Uses Claude to evaluate papers against biosecurity criteria:
  - Pathogen risk (WHO priority pathogens, CDC Select Agents)
  - Gain-of-function indicators
  - Containment adequacy
  - Dual-use research concerns
- **Facility research**: Automatically researches BSL containment levels using web search
- **Risk grading**: Papers graded A-F with detailed score breakdowns
- **Alert system**: Automatic flagging of high-risk papers for human review
- **Dashboard**: Modern React dashboard for monitoring and analysis

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Anthropic API key (for risk assessment)

### Backend Setup

```bash
cd backend

# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies and create virtual environment
uv sync

# Set environment variables
export ANTHROPIC_API_KEY=your-api-key-here

# Run the server
uv run uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

The dashboard will be available at http://localhost:3000

## Usage

1. **Scan for Papers**: Click "Scan All Sources" or individual source buttons to fetch recent papers

2. **Assess Papers**: Click "Assess Papers" to run AI biosecurity analysis on unprocessed papers. Facilities mentioned in papers are automatically researched if Tavily API is configured.

3. **Research Facilities**: Manually research specific facilities by name to find their BSL levels

4. **Review Results**: Check the Dashboard for an overview, or the Flagged page for high-risk papers

**Note**: All facility data is populated through actual web searches, not pre-loaded data. Facility information requires human verification before being marked as verified.

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude | Required |
| `TAVILY_API_KEY` | Tavily API key for facility research | Optional |
| `NCBI_API_KEY` | NCBI API key for higher PubMed rate limits | Optional |
| `SCAN_INTERVAL_HOURS` | Hours between automated scans | 24 |
| `MAX_PAPERS_PER_SCAN` | Maximum papers to fetch per scan | 100 |
| `HIGH_RISK_THRESHOLD` | Score threshold for flagging papers | 70 |
| `ENABLE_SCHEDULER` | Enable background scanning | false |
| `AUTO_RESEARCH_FACILITIES` | Auto-research facilities during assessment | true |

To get API keys:
- Anthropic: https://console.anthropic.com/
- Tavily (for web search): https://tavily.com/
- NCBI: https://www.ncbi.nlm.nih.gov/account/settings/

## API Endpoints

### Papers
- `GET /api/papers/` - List papers
- `GET /api/papers/{id}` - Get paper details
- `GET /api/papers/stats/summary` - Paper statistics

### Assessments
- `GET /api/assessments/` - List assessments
- `GET /api/assessments/{id}` - Get assessment details
- `GET /api/assessments/flagged` - Get flagged papers
- `GET /api/assessments/stats/summary` - Assessment statistics

### Facilities
- `GET /api/facilities/` - List facilities
- `POST /api/facilities/` - Add facility
- `GET /api/facilities/search/name?name=...` - Search facilities

### Scanning
- `POST /api/scan/arxiv` - Scan arXiv
- `POST /api/scan/biorxiv` - Scan bioRxiv/medRxiv
- `POST /api/scan/pubmed` - Scan PubMed
- `POST /api/scan/all` - Scan all sources
- `POST /api/scan/assess` - Assess unprocessed papers
- `POST /api/scan/research-facility?facility_name=...` - Research a facility

## Docker Deployment

```bash
# Set your API key
export ANTHROPIC_API_KEY=your-api-key

# Run with Docker Compose
docker-compose up -d
```

## Project Structure

```
biomon/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── config.py         # Configuration
│   │   ├── database.py       # SQLite setup
│   │   ├── models/           # SQLAlchemy models
│   │   ├── scrapers/         # Paper source integrations
│   │   ├── analysis/         # AI assessment pipeline
│   │   ├── research/         # Web search for facility info
│   │   ├── api/              # REST endpoints
│   │   └── scheduler.py      # Background jobs
│   └── pyproject.toml        # uv/Python dependencies
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js pages
│   │   ├── components/       # React components
│   │   └── lib/              # API client, utilities
│   └── package.json
├── data/
│   └── litmus.db             # SQLite database
└── docker-compose.yml
```

## Risk Assessment Criteria

Papers are evaluated on four dimensions (0-100 each):

1. **Pathogen Risk**: Identifies dangerous pathogens from WHO priority lists and CDC Select Agents
2. **Gain-of-Function**: Detects research enhancing transmissibility, virulence, or host range
3. **Containment**: Assesses if research is conducted at appropriate biosafety levels
4. **Dual-Use**: Evaluates potential for methodology misuse

The overall score is a weighted average, converted to letter grades:
- A (0-19): Minimal concern
- B (20-39): Low concern
- C (40-59): Moderate concern
- D (60-79): High concern
- F (80-100): Critical concern

Papers scoring above the threshold (default 70) are automatically flagged for human review.

## Facility Research

Unlike static databases, Biomon researches facility information dynamically using web search:

1. **Automatic Research**: During paper assessment, facilities mentioned in abstracts are automatically researched
2. **Manual Research**: Use the Scan page to research specific facilities by name
3. **Verification Required**: All facility data starts as "unverified" and requires human confirmation
4. **Web Search**: Uses Tavily API to search for BSL level information from authoritative sources

This approach ensures:
- No fabricated or outdated facility data
- Traceable sources for all information
- Human verification in the loop
- Dynamic updates as facilities change

## Command Line Interface

Run the scheduler manually:

```bash
cd backend

# Scan all sources
uv run python -m app.scheduler scan

# Assess pending papers
uv run python -m app.scheduler assess

# Run full pipeline
uv run python -m app.scheduler full

# Run as daemon (continuous)
uv run python -m app.scheduler daemon
```

## License

MIT

