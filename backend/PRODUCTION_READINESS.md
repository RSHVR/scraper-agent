# Production Readiness Plan

## Overview
This document outlines the complete plan for making the Scraper Agent application production-ready with Docker containerization, comprehensive documentation, and cleanup of development artifacts.

---

## Phase 1: Cleanup & Organization

### 1.1 Remove Temporary Test Files (7 files)

**Files to Delete:**
1. `backend/rag_query_results.txt` - Test query output from vector search debugging
2. `backend/rag_query_results_cleaned.txt` - Cleaned test query output with warnings
3. `backend/rag_query_results_final.txt` - Final test query output with error traces
4. `backend/debug_playwright.py` - Development-only debugging utility
5. `backend/test_pilates_search.py` - Ad-hoc test script (not pytest-compatible)
6. `backend/test_search.py` - Ad-hoc test script for vector search
7. `backend/test_webfetch.py` - Ad-hoc test script for web fetch testing

**Reason:** These are temporary development artifacts that should not be in production deployment.

### 1.2 Move RAG Test Results to Root

**Action:** Copy `/tmp/claude_rag_test_results.txt` → `backend/claude_rag_test_results.txt`

**Reason:** This contains valuable RAG testing documentation that should be preserved with the codebase.

### 1.3 Fix Code Inconsistencies

**File:** `backend/src/routes/__init__.py`

**Current State:**
```python
"""API routes for the application."""
from . import scrape, sessions

__all__ = ["scrape", "sessions"]
```

**Issue:** Missing `query` route in exports, but it's imported directly in `main.py`.

**Fix:** Update to include all routes:
```python
"""API routes for the application."""
from . import scrape, sessions, query

__all__ = ["scrape", "sessions", "query"]
```

---

## Phase 2: Docker Configuration

### 2.1 Create Dockerfile

**File:** `backend/Dockerfile`

**Requirements:**
- Base image: `python:3.11-slim`
- System dependencies for Playwright (Chromium)
- System dependencies for lxml (libxml2, libxslt1)
- Python packages from `requirements.txt`
- Playwright browser installation: `playwright install --with-deps chromium`
- Working directory: `/app`
- Exposed port: `8000`
- Default command: `uvicorn src.main:app --host 0.0.0.0 --port 8000`

**Dockerfile Structure:**
```dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install Playwright and Chromium browser
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p /app/data /app/models /app/milvus_data

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2.2 Create docker-compose.yml

**File:** `backend/docker-compose.yml`

**Purpose:** Orchestrate the application with proper volume mounts and environment configuration.

**Structure:**
```yaml
version: '3.8'

services:
  scraper-agent:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: scraper-agent
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - HOST=0.0.0.0
      - PORT=8000
      - DEBUG=${DEBUG:-False}
      - STORAGE_BASE_PATH=/app/data
    volumes:
      # Persistent storage for scraped data and sessions
      - ./data:/app/data
      # Cache for BGE-M3 model (prevents re-downloading)
      - ./models:/root/.cache/huggingface
      # Milvus Lite database storage
      - ./milvus_data:/root/milvus
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  default:
    name: scraper-agent-network
```

### 2.3 Create .dockerignore

**File:** `backend/.dockerignore`

**Purpose:** Exclude unnecessary files from Docker build context to reduce image size and build time.

**Contents:**
```
# Virtual environments
venv/
env/
ENV/

# Python cache
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Environment files
.env
.env.*

# Data directories (mounted as volumes)
data/
models/
milvus_data/

# Git
.git/
.gitignore
.gitattributes

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Documentation (except README)
*.md
!README.md

# Development files
debug_*.py
test_*.py
rag_query_results*.txt

# macOS
.DS_Store

# Logs
*.log
```

---

## Phase 3: Comprehensive Documentation

### 3.1 Create README.md

**File:** `backend/README.md`

**Structure:**

#### 1. Project Title & Overview
- **Title:** Scraper Agent: Claude-Powered Web Scraper with RAG
- **Description:** Intelligent web scraping system with vector embeddings and semantic search
- **Key Features:**
  - AI-powered content extraction using Claude Sonnet 4
  - Whole-site crawling with automatic sitemap discovery
  - Vector embeddings using BGE-M3 model (1024-dimensional)
  - Semantic search with Milvus Lite vector database
  - 3-stage RAG pipeline for natural language Q&A
  - Real-time WebSocket updates during scraping

#### 2. Architecture Diagram (Text-based)
```
┌─────────────────────────────────────────────────────────────┐
│                    SCRAPER AGENT ARCHITECTURE                │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Web Scraper│─────▶│  Storage     │─────▶│  Embeddings  │
│   (Playwright)│      │  (Sessions)  │      │  (BGE-M3)    │
└──────────────┘      └──────────────┘      └──────────────┘
       │                                             │
       ▼                                             ▼
┌──────────────┐                            ┌──────────────┐
│   Claude API │                            │   Milvus     │
│   (Extract)  │                            │   (Vectors)  │
└──────────────┘                            └──────────────┘
                                                    │
                                                    ▼
                                            ┌──────────────┐
                                            │   RAG Query  │
                                            │   (3-Stage)  │
                                            └──────────────┘
                                                    │
                                                    ▼
                                            ┌──────────────┐
                                            │   Claude API │
                                            │   (Synthesis)│
                                            └──────────────┘
```

#### 3. Prerequisites
- Docker (20.10+)
- Docker Compose (1.29+)
- Anthropic API key (https://console.anthropic.com/)
- Minimum: 2 CPU cores, 4GB RAM, 10GB disk
- Recommended: 4 CPU cores, 8GB RAM, 20GB disk

#### 4. Quick Start

**Step 1: Clone Repository**
```bash
git clone <repository-url>
cd scraper-agent/backend
```

**Step 2: Configure Environment**
```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your Anthropic API key
nano .env
# Set: ANTHROPIC_API_KEY=your_api_key_here
```

**Step 3: Start with Docker**
```bash
# Build and start the container
docker-compose up -d

# Check logs
docker-compose logs -f

# Verify service is running
curl http://localhost:8000/health
```

**Step 4: Access API Documentation**
Open in browser: http://localhost:8000/docs

#### 5. Usage Examples

##### A. Scrape a Gym Website
```bash
curl -X POST http://localhost:8000/api/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://fitfactoryfitness.com",
    "mode": "whole-site"
  }'

# Response includes session_id for tracking
```

##### B. Check Scraping Session Status
```bash
# List all sessions
curl http://localhost:8000/api/sessions

# Get specific session details
curl http://localhost:8000/api/sessions/{session_id}
```

##### C. Embed Scraped Data into Vector Database
```bash
# List available files to embed
docker exec scraper-agent python -m src.cli.embed_sites --list

# Embed all scraped sites
docker exec scraper-agent python -m src.cli.embed_sites --all

# Embed specific file
docker exec scraper-agent python -m src.cli.embed_sites \
  --file fitfactoryfitness.com__20251125_120000.json

# Recreate collection (deletes existing vectors)
docker exec scraper-agent python -m src.cli.embed_sites \
  --all --recreate
```

##### D. Query with Natural Language (Claude-Powered RAG)
```bash
# Ask about class types
curl -X POST http://localhost:8000/api/query/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What types of classes do you offer?",
    "top_k": 10
  }'

# Ask about location
curl -X POST http://localhost:8000/api/query/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Where are you located?",
    "top_k": 5
  }'

# Ask about amenities
curl -X POST http://localhost:8000/api/query/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Do you have showers?",
    "top_k": 10
  }'

# Ask about pricing
curl -X POST http://localhost:8000/api/query/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How much does a membership cost?",
    "top_k": 10
  }'

# Filter by specific gym
curl -X POST http://localhost:8000/api/query/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are your hours?",
    "filter_gym": "Fit Factory Fitness",
    "top_k": 5
  }'

# Filter by domain
curl -X POST http://localhost:8000/api/query/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Tell me about your trainers",
    "filter_domain": "fitfactoryfitness.com",
    "top_k": 8
  }'
```

##### E. Basic Vector Search (Without Claude Synthesis)
```bash
# Direct vector similarity search
curl -X POST http://localhost:8000/api/query/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "boxing classes heavy bag training",
    "top_k": 5
  }'

# With filters
curl -X POST http://localhost:8000/api/query/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "yoga pilates stretching",
    "top_k": 10,
    "filter_gym": "Pilates in Pink Studio"
  }'
```

#### 6. API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information and version |
| GET | `/health` | Health check endpoint |
| GET | `/docs` | Interactive API documentation (Swagger UI) |
| GET | `/redoc` | Alternative API documentation (ReDoc) |
| POST | `/api/scrape` | Scrape website with generic schema |
| GET | `/api/sessions` | List all scraping sessions |
| GET | `/api/sessions/{session_id}` | Get session details and results |
| POST | `/api/query/search` | Vector similarity search (returns raw chunks) |
| POST | `/api/query/ask` | Natural language Q&A with Claude RAG |
| GET | `/api/query/health` | Check vector database health |
| WS | `/ws/{session_id}` | WebSocket for real-time scraping updates |

#### 7. 3-Stage RAG Pipeline

The `/api/query/ask` endpoint implements an intelligent 3-stage RAG pipeline:

**Stage 1: Query Rewriting (Claude Haiku)**
- Takes user's natural language question
- Extracts key concepts and adds relevant synonyms
- Optimizes query for semantic search
- Example: "Do you have showers?" → "gym facilities amenities showers locker room"

**Stage 2: Vector Search (BGE-M3 + Milvus)**
- Embeds optimized query using BGE-M3 model
- Searches vector database for semantically similar chunks
- Returns top-k most relevant content chunks
- Includes metadata: gym name, page name, URL, similarity score

**Stage 3: Answer Synthesis (Claude Sonnet)**
- Receives retrieved chunks as context
- Generates natural, conversational answer
- Cites sources and organizes information clearly
- Acknowledges when information is unavailable

**Performance:**
- Query rewriting: ~800ms (Claude Haiku)
- Vector search: ~200ms (BGE-M3 + Milvus)
- Answer synthesis: ~2-3s (Claude Sonnet)
- Total latency: ~3-4 seconds per query
- Cost per query: ~$0.015

#### 8. Data Flow & Storage

**Scraping → Storage:**
```
1. Web Scraper (Playwright) fetches HTML
2. Claude extracts structured data
3. Storage service saves:
   - Raw HTML: data/{session_id}/raw_html.json
   - Extracted data: data/{session_id}/extracted_data.json
   - Cleaned markdown: data/cleaned_markdown/{domain}_{timestamp}.json
```

**Embedding → Querying:**
```
1. CLI tool loads cleaned markdown
2. Chunks content (4000 chars with heading-aware splitting)
3. BGE-M3 generates embeddings (1024-dim vectors)
4. Milvus stores vectors with metadata
5. Query endpoint searches vectors and synthesizes answers
```

**Persistent Data Volumes:**
- `./data` → `/app/data` - Sessions and cleaned markdown
- `./models` → `/root/.cache/huggingface` - BGE-M3 model cache (~650MB)
- `./milvus_data` → `/root/milvus` - Vector database storage

#### 9. Development Setup (Without Docker)

For local development without Docker:

```bash
# 1. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Playwright browser
playwright install chromium

# 4. Set up environment
cp .env.example .env
# Edit .env and add ANTHROPIC_API_KEY

# 5. Run development server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 6. Run tests
pytest
```

#### 10. Configuration

See `.env.example` for all configuration options:

**Core Settings:**
- `ANTHROPIC_API_KEY` - Required for Claude API access
- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 8000)
- `DEBUG` - Debug mode (default: False)
- `STORAGE_BASE_PATH` - Base path for data storage

**Browser Settings:**
- `BROWSER_TIMEOUT` - Page load timeout in seconds (default: 60)
- `BROWSER_WAIT_FOR` - Wait strategy: networkidle, load, domcontentloaded
- `MAX_CONCURRENT_BROWSERS` - Max parallel browser instances (default: 3)

**Agent Settings:**
- `MAX_PARALLEL_EXTRACTIONS` - Max parallel Claude extractions (default: 3)
- `MAX_CONCURRENT_EXTRACTIONS` - Max concurrent extraction tasks (default: 5)
- `DEFAULT_TIMEOUT` - Default operation timeout (default: 30)

**Crawling Settings:**
- `MAX_PAGES_PER_SITE` - Maximum pages to scrape per site (default: 1000)
- `MAX_CRAWL_DEPTH` - Maximum crawl depth (default: 3)
- `ENABLE_SITEMAP_CRAWL` - Enable sitemap-based crawling (default: True)

#### 11. Performance & Scaling

**Resource Requirements:**
- Minimum: 2 CPU cores, 4GB RAM, 10GB disk
- Recommended: 4 CPU cores, 8GB RAM, 20GB disk
- With GPU: Significantly faster embeddings

**Optimization Tips:**
- Cache frequent queries (70% reduction in API calls possible)
- Use streaming for real-time answer generation
- Batch multiple embeddings for efficiency
- Mount GPU for 5-10x faster embedding generation

**Scaling Considerations:**
- Horizontal scaling: Run multiple containers behind load balancer
- Separate vector DB: Use managed Milvus for multi-instance deployments
- Redis caching: Add Redis for query result caching
- Queue system: Add Celery for async scraping tasks

#### 12. Troubleshooting

**Problem: Browser timeout errors**
```bash
# Solution: Increase timeout in .env
BROWSER_TIMEOUT=120
```

**Problem: Out of memory during scraping**
```bash
# Solution: Reduce concurrent operations
MAX_CONCURRENT_BROWSERS=1
MAX_PARALLEL_EXTRACTIONS=1
```

**Problem: Slow embeddings**
```bash
# Solution 1: Mount GPU (requires nvidia-docker)
# Solution 2: Increase RAM allocation
# Solution 3: Use smaller batch sizes
```

**Problem: Container won't start**
```bash
# Check logs
docker-compose logs scraper-agent

# Verify API key is set
docker-compose exec scraper-agent env | grep ANTHROPIC

# Restart container
docker-compose restart scraper-agent
```

**Problem: Vector search returns no results**
```bash
# Check if data is embedded
docker exec scraper-agent python -m src.cli.embed_sites --list

# Verify Milvus health
curl http://localhost:8000/api/query/health

# Re-embed data
docker exec scraper-agent python -m src.cli.embed_sites --all --recreate
```

#### 13. Testing

Run the test suite:

```bash
# Inside container
docker exec scraper-agent pytest

# Or locally
source venv/bin/activate
pytest

# With coverage
pytest --cov=src --cov-report=html
```

**Test Results:** See `claude_rag_test_results.txt` for comprehensive RAG pipeline testing results.

#### 14. Project Structure

```
backend/
├── src/
│   ├── agents/           # Claude-powered extraction agents
│   ├── cli/             # Command-line tools (embed_sites.py)
│   ├── models/          # Pydantic models
│   ├── routes/          # API endpoints
│   ├── services/        # Core services (scraping, storage, vectors)
│   ├── utils/           # Utilities and helpers
│   ├── config.py        # Configuration settings
│   └── main.py          # FastAPI application entry point
├── tests/               # Test suite
├── data/                # Persistent data (mounted volume)
├── models/              # Model cache (mounted volume)
├── milvus_data/         # Vector DB storage (mounted volume)
├── Dockerfile           # Docker image definition
├── docker-compose.yml   # Docker orchestration
├── requirements.txt     # Python dependencies
├── .env.example         # Example environment variables
└── README.md           # This file
```

#### 15. License

[Specify your license here]

#### 16. Credits & Technologies

- **Anthropic Claude API** - AI-powered content extraction and synthesis
- **BGE-M3** (BAAI) - State-of-the-art embedding model
- **Milvus** - High-performance vector database
- **Playwright** - Browser automation framework
- **FastAPI** - Modern Python web framework

---

## End of README.md Content

---

## Phase 4: Implementation Checklist

### Phase 1: Cleanup
- [ ] Delete 7 temporary/debug files
- [ ] Copy claude_rag_test_results.txt from /tmp to backend/
- [ ] Update src/routes/__init__.py with all route exports

### Phase 2: Docker
- [ ] Create Dockerfile
- [ ] Create docker-compose.yml
- [ ] Create .dockerignore

### Phase 3: Documentation
- [ ] Create README.md with all sections
- [ ] Verify all curl examples work
- [ ] Test Docker build and run

### Phase 4: Validation
- [ ] Build Docker image successfully
- [ ] Start container with docker-compose
- [ ] Test health endpoint
- [ ] Test scraping endpoint
- [ ] Test embedding CLI
- [ ] Test query endpoints
- [ ] Verify persistent volumes work

---

## Expected Outcomes

1. **Clean Codebase:** No temporary or debug files in production
2. **Docker Ready:** One-command deployment with docker-compose up
3. **Well Documented:** Comprehensive README with examples
4. **Production Grade:** Proper health checks, volume mounts, restart policies
5. **User Friendly:** Clear instructions for setup and usage

---

## Notes

- First Docker build will take 30-45 minutes (Playwright + model download)
- BGE-M3 model will download on first embedding (~650MB)
- Subsequent builds use Docker cache and are much faster
- All data persists in mounted volumes even if container is removed
