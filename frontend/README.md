# Scraper Agent - Frontend

Gradio-based web interface for the Scraper Agent with automatic scraping, embedding, and AI-powered Q&A capabilities.

## Table of Contents

- [Overview](#overview)
- [Technology Stack](#technology-stack)
- [Quick Start](#quick-start)
- [How to Host It](#how-to-host-it)
- [Making It Publicly Available](#making-it-publicly-available)
- [Data Flow Architecture](#data-flow-architecture)
- [User Flow Paths](#user-flow-paths)
- [Component Architecture](#component-architecture)
- [Configuration](#configuration)
- [Production Deployment Checklist](#production-deployment-checklist)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Scraper Agent frontend is a **Python Gradio application** (not a traditional JavaScript SPA) that provides a web-based interface for:

1. **URL Submission** - Simple textbox to submit websites for scraping
2. **Automated Scraping** - Real-time progress tracking of Playwright-based web scraping
3. **Automatic Embedding** - Seamless transition from scraping to vector embedding generation
4. **AI-Powered Q&A** - Chat interface with RAG (Retrieval Augmented Generation) for querying scraped content

### Key Features

- Real-time progress tracking with animated terminal-style logs
- Automatic workflow (scraping → embedding → chat) without manual steps
- AI-powered answers with source citations and relevance scores
- Server-side rendering (no JavaScript build process required)
- Integration with FastAPI backend and Milvus vector database

---

## Technology Stack

### Core Framework
- **Gradio 6.0+** - Python web UI library with built-in websocket support
- **Python 3.11+** - Runtime environment
- **Server-side rendering** - No client-side JavaScript framework

### Dependencies
```
gradio>=6.0.0          # Web UI framework
httpx>=0.25.0          # Async HTTP client for API calls
python-dotenv>=1.0.0   # Environment variable management
```

### Architecture Type
- **Monolithic Python Application** - Gradio server runs standalone on port 7860
- **HTTP Communication** - Connects to FastAPI backend on port 8000
- **No Build Process** - Pure Python, no npm/webpack/bundling required

### Backend Stack (for context)
- **FastAPI** - REST API server
- **Anthropic Claude** - AI models (Sonnet 4, Haiku)
- **Milvus** - Vector database for embeddings
- **BGE-M3** - Embedding model (1024-dimensional vectors)
- **Playwright** - Browser automation for web scraping

---

## Quick Start

### Prerequisites

1. **Python 3.11+** installed
2. **Backend server** running (see backend/README.md)
3. **Milvus database** running via Docker Compose

### Installation

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp .env.example .env
```

Edit `.env` if needed:
```bash
API_BASE_URL=http://localhost:8000  # Backend API URL
GRADIO_SERVER_PORT=7860             # Frontend port
```

### Running Locally

**Step 1:** Start Milvus (from backend directory)
```bash
cd ../backend
docker-compose up -d
```

**Step 2:** Start Backend (from backend directory)
```bash
cd ../backend
source venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

**Step 3:** Start Frontend
```bash
cd ../frontend
python app.py
```

**Access:**
- Frontend: http://localhost:7860
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## How to Host It

The Scraper Agent requires a hosting platform that supports:
- **Long-running processes** (scraping takes minutes, not seconds)
- **Persistent storage** (for Milvus vector database)
- **Docker support** (for Milvus services: etcd, MinIO, Milvus)
- **Python runtime** (for FastAPI backend and Gradio frontend)

### Option 1: Railway (RECOMMENDED)

**Why Railway:**
- Native Docker Compose support for Milvus stack
- Python runtime for backend and frontend
- Persistent volumes for database storage
- Auto-deployment from Git
- Simple environment variable management
- Good pricing for side projects ($5-20/month)

**Deployment Steps:**

1. **Install Railway CLI:**
```bash
npm install -g railway
railway login
```

2. **Create Railway projects:**
```bash
# In backend directory
cd backend
railway init
railway link  # Link to your Railway project

# In frontend directory
cd ../frontend
railway init
railway link
```

3. **Deploy Milvus services (from backend directory):**
```bash
cd backend
railway up  # Deploys docker-compose.yml
```

4. **Configure environment variables:**

Backend variables:
```bash
railway variables set ANTHROPIC_API_KEY=sk-ant-your-key-here
railway variables set MILVUS_HOST=milvus.railway.internal
railway variables set MILVUS_PORT=19530
railway variables set DEBUG=False
```

Frontend variables:
```bash
railway variables set API_BASE_URL=https://your-backend.railway.app
railway variables set GRADIO_SERVER_PORT=7860
railway variables set GRADIO_SERVER_NAME=0.0.0.0
```

5. **Deploy services:**
```bash
# Backend
cd backend
railway up

# Frontend
cd frontend
railway up
```

6. **Add custom domain (optional):**
```bash
railway domain  # Follow prompts
```

**Railway Configuration File:**

Create `railway.json` in frontend directory:
```json
{
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "pip install -r requirements.txt"
  },
  "deploy": {
    "startCommand": "python app.py",
    "healthcheckPath": "/",
    "restartPolicyType": "ON_FAILURE"
  }
}
```

---

### Option 2: Fly.io

**Why Fly.io:**
- Excellent Docker support
- Global edge deployment
- Persistent volumes for Milvus
- Strong performance and reliability

**Deployment Steps:**

1. **Install Fly CLI:**
```bash
curl -L https://fly.io/install.sh | sh
fly auth login
```

2. **Create apps:**
```bash
# Backend
cd backend
fly launch --no-deploy
fly volumes create milvus_data --size 10  # Persistent storage

# Frontend
cd frontend
fly launch --no-deploy
```

3. **Configure `fly.toml` for frontend:**
```toml
app = "scraper-agent-frontend"

[build]
  builder = "paketobuildpacks/builder:base"

[env]
  API_BASE_URL = "https://scraper-agent-backend.fly.dev"
  GRADIO_SERVER_PORT = "7860"

[[services]]
  internal_port = 7860
  protocol = "tcp"

  [[services.ports]]
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443
```

4. **Set secrets:**
```bash
fly secrets set ANTHROPIC_API_KEY=sk-ant-your-key-here
```

5. **Deploy:**
```bash
fly deploy
```

**Pros:**
- Global CDN
- Excellent performance
- Free tier available
- Strong Docker support

**Cons:**
- Steeper learning curve
- More complex setup than Railway

---

### Option 3: Render

**Why Render:**
- Native Python support
- Docker support for Milvus
- Easy deployment process
- Good free tier with automatic SSL

**Deployment Steps:**

1. **Create account at render.com**

2. **Create services via dashboard:**
   - New Docker Service (for Milvus) with persistent disk
   - New Web Service (for backend) - Python runtime
   - New Web Service (for frontend) - Python runtime

3. **Configure `render.yaml` (optional, for infrastructure-as-code):**
```yaml
services:
  - type: web
    name: scraper-agent-frontend
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python app.py
    envVars:
      - key: API_BASE_URL
        value: https://scraper-agent-backend.onrender.com
      - key: GRADIO_SERVER_PORT
        value: 7860
      - key: GRADIO_SERVER_NAME
        value: 0.0.0.0

  - type: web
    name: scraper-agent-backend
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn src.main:app --host 0.0.0.0 --port 8000
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false  # Mark as secret
      - key: DEBUG
        value: False
```

4. **Connect Git repository** and deploy

**Pros:**
- Easy Python deployment
- Native Docker support
- Good free tier
- Automatic SSL

**Cons:**
- Free tier has cold starts (slow first request after inactivity)
- Limited persistent storage on free tier

---

### Option 4: Hugging Face Spaces (For Demos)

**Why Hugging Face:**
- Native Gradio support (optimized for this framework)
- Free hosting for ML/AI apps
- Simple Git-based deployment
- Great for public demos and prototypes

**Limitations:**
- **Cannot host full stack** (Milvus and backend must be deployed elsewhere)
- CPU-only on free tier
- No persistent storage for vector database

**Deployment Steps:**

1. **Create new Space at huggingface.co/spaces**

2. **Add README.md to repository root:**
```markdown
---
title: Scraper Agent
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 6.0.0
app_file: app.py
pinned: false
---

# Scraper Agent Frontend

AI-powered web scraping and Q&A system.
```

3. **Configure environment:**
```bash
# In Hugging Face Space settings, add secret:
API_BASE_URL=https://your-backend-on-railway.com
```

4. **Push code:**
```bash
git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/scraper-agent
git push hf main
```

**Use Case:**
- Frontend-only deployment for demos
- Backend and Milvus hosted on Railway/Render
- Public sharing and testing

---

### NOT RECOMMENDED: Vercel / Netlify

**Why NOT to use:**

1. **Serverless timeout limits:**
   - Vercel: 10-second timeout (60s on Pro plan)
   - Netlify: 10-second timeout (26s on Pro plan)
   - Scraping takes **minutes**, not seconds

2. **No persistent storage:**
   - Milvus requires persistent volumes
   - Vector database cannot run on serverless

3. **No Docker support:**
   - Cannot run Milvus services (etcd, MinIO, Milvus)

4. **Designed for static sites:**
   - This is a **persistent server application** with long-running processes
   - Not suitable for serverless architecture

**Bottom line:** Vercel/Netlify are excellent for static sites and short serverless functions, but incompatible with this application's architecture.

---

## Making It Publicly Available

### Domain Configuration

**Custom Domain Setup:**

1. **Purchase domain** (e.g., `scraperagent.com`)

2. **Configure DNS records:**
```
Type  | Name | Value
------|------|------
CNAME | app  | your-frontend.railway.app
CNAME | api  | your-backend.railway.app
```

3. **Update environment variables:**

Frontend `.env`:
```bash
API_BASE_URL=https://api.scraperagent.com
GRADIO_SERVER_NAME=0.0.0.0
```

Backend environment (update CORS):
```bash
ALLOWED_ORIGINS=https://app.scraperagent.com,https://scraperagent.com
```

4. **Add domain to hosting platform:**
   - Railway: `railway domain` command
   - Fly.io: `fly certs add app.scraperagent.com`
   - Render: Add custom domain in dashboard

5. **SSL/HTTPS:** Automatically provisioned by all platforms (Let's Encrypt)

---

### CORS Configuration

**Current Setup (INSECURE):**

`backend/src/main.py` currently allows all origins:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # INSECURE - allows all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Production Configuration (SECURE):**

Update `backend/src/main.py`:
```python
from starlette.middleware.cors import CORSMiddleware

# Production domains
ALLOWED_ORIGINS = [
    "https://app.scraperagent.com",
    "https://scraperagent.com",
    "http://localhost:7860",  # Keep for local development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
```

Or use environment variable:
```python
import os

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:7860").split(",")
```

---

### Security Requirements

#### 1. API Key Security

**NEVER expose `ANTHROPIC_API_KEY` in frontend code.**

- Store in backend environment variables only
- Use hosting platform's secret management
- Rotate keys regularly

#### 2. Rate Limiting

**Backend currently has NO rate limiting.**

Add FastAPI rate limiting middleware:

```bash
pip install slowapi
```

Update `backend/src/main.py`:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/scrape")
@limiter.limit("5/minute")  # 5 scrapes per minute per IP
async def create_scrape_session(request: Request, ...):
    ...

@app.post("/api/query/ask")
@limiter.limit("30/minute")  # 30 queries per minute per IP
async def ask_question(request: Request, ...):
    ...
```

#### 3. Input Validation

Currently uses Pydantic models. Add additional validation:

```python
from pydantic import HttpUrl, validator

class ScrapeRequest(BaseModel):
    url: HttpUrl  # Validates URL format
    mode: str = "whole-site"

    @validator('url')
    def validate_url(cls, v):
        # Block localhost, private IPs
        if 'localhost' in str(v) or '127.0.0.1' in str(v):
            raise ValueError('Cannot scrape localhost')
        return v
```

#### 4. Authentication (Optional)

For private/internal use, add API key auth:

```python
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key != os.getenv("API_KEY"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key"
        )
    return api_key

# Apply to endpoints
@app.post("/api/scrape")
async def create_scrape_session(
    request: ScrapeRequest,
    api_key: str = Depends(verify_api_key)
):
    ...
```

Frontend would pass key:
```python
headers = {"X-API-Key": os.getenv("API_KEY")}
response = await client.post(f"{API_URL}/api/scrape", json=data, headers=headers)
```

#### 5. Data Persistence & Backups

**Milvus Data:**
- Use persistent volumes on hosting platform
- Configure automatic backups (Railway/Render/Fly.io all support this)
- Consider PostgreSQL for session metadata (more reliable than JSON files)

**Session Files:**
- Current setup stores in `backend/data/` directory
- Ensure this directory is on persistent volume
- Set up regular backups to cloud storage (S3, GCS)

---

### Monitoring & Logging

#### Health Check Endpoints

Already implemented in backend:
- `GET /health` - Backend status
- `GET /api/query/health` - Milvus connection status

Configure platform health checks:
```bash
# Railway
railway settings --healthcheck-path=/health

# Fly.io (in fly.toml)
[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  [http_service.health_check]
    path = "/health"
    interval = "30s"
    timeout = "10s"
```

#### Logging

Current setup logs to stdout. For production:

1. **Configure structured logging:**
```python
import logging
import json_logging

json_logging.init_fastapi(enable_json=True)
json_logging.init_request_instrument(app)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
```

2. **Use log aggregation service:**
   - Logtail
   - Papertrail
   - Railway Logs (built-in)
   - Fly.io Logs (built-in)

3. **Set up alerts:**
   - Error rate thresholds
   - Scraping failures
   - API latency spikes

#### Metrics & Monitoring

Add FastAPI middleware for metrics:

```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

Access metrics at `/metrics` endpoint.

Track:
- Request count and latency
- Scraping success/failure rates
- Embedding generation times
- Query response times
- Error rates by endpoint

---

## Data Flow Architecture

### Overview

The application uses a **three-stage workflow**:
1. **Scraping** - Fetch and convert web pages to markdown
2. **Embedding** - Generate vector embeddings and store in Milvus
3. **Q&A** - RAG pipeline for question answering

### Flow 1: Web Scraping Process

```
User Input → Frontend → Backend API → Playwright → Markdown → Storage → Polling Loop
```

**Step-by-Step:**

1. **User submits URL:**
```
User enters: https://fitfactoryfitness.com
Clicks: "Start Scraping"
```

2. **Frontend makes API call:**
```python
# app.py:68-75
async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{API_URL}/api/scrape",
        json={"url": url, "mode": "whole-site", "purpose": "..."},
        timeout=30.0
    )
    data = response.json()
    session_id = data["session_id"]  # e.g., "20251128_140530_abc123"
```

**Request:**
```json
POST http://localhost:8000/api/scrape
{
  "url": "https://fitfactoryfitness.com",
  "mode": "whole-site",
  "purpose": "Web scraping for Q&A"
}
```

**Response:**
```json
{
  "session_id": "20251128_140530_abc123",
  "status": "pending",
  "message": "Scraping started"
}
```

3. **Backend creates session:**
```python
# backend/src/routes/scrape.py
session_id = generate_session_id()  # timestamp-based
session_dir = f"data/{session_id}/"
os.makedirs(session_dir)

# Save initial metadata
metadata = {
    "session_id": session_id,
    "url": url,
    "status": "pending",
    "pages_scraped": 0,
    "total_pages": 0,
    "created_at": datetime.now().isoformat()
}
save_json(f"{session_dir}/metadata.json", metadata)

# Launch background task
background_tasks.add_task(execute_scrape_task, session_id, url)
```

4. **Background scraping (Orchestrator Agent):**
```python
# backend/src/agents/orchestrator.py
1. Discover sitemap URLs via robots.txt
2. Parse sitemap XML to extract all page URLs
3. For each URL:
   - Fetch raw HTML using Playwright (headless browser)
   - Extract main content using BeautifulSoup
   - Convert HTML to clean markdown
4. Save to: data/{session_id}/cleaned_markdown/all_pages.json
5. Update metadata: pages_scraped++, total_pages=N, status="in_progress"
```

5. **Frontend polls for progress:**
```python
# app.py:93-140 (polling loop)
while True:
    response = await client.get(f"{API_URL}/api/sessions/{session_id}")
    session_data = response.json()

    status = session_data["status"]
    pages_scraped = session_data.get("pages_scraped", 0)
    total_pages = session_data.get("total_pages", 0)

    # Update UI
    logs.append(f"Status: {status} | Pages: {pages_scraped}/{total_pages}")
    yield session_id, format_logs(logs)

    if status == "completed":
        break

    await asyncio.sleep(1)  # Poll every 1 second
```

**Progress Updates:**
```json
GET /api/sessions/20251128_140530_abc123

{
  "session_id": "20251128_140530_abc123",
  "url": "https://fitfactoryfitness.com",
  "status": "in_progress",
  "pages_scraped": 7,
  "total_pages": 15,
  "created_at": "2025-11-28T14:05:30",
  "updated_at": "2025-11-28T14:06:15"
}
```

6. **State management:**
```python
# Gradio State component stores session ID
session_id_state = gr.State(None)

# Generator yields updates to UI
def start_scraping(url):
    for update in scraping_generator(url):
        yield update  # Gradio automatically updates components
```

---

### Flow 2: Embedding Generation

```
Scraping Complete → Auto-trigger → Read Markdown → Chunk Text → BGE-M3 → Milvus
```

**Step-by-Step:**

1. **Automatic trigger (via Gradio .then() chain):**
```python
# app.py:326-329
scrape_btn.click(
    start_scraping, inputs=url_input, outputs=[session_id_state, scrape_progress]
).then(  # Automatically runs after scraping completes
    start_embedding, inputs=session_id_state, outputs=embed_progress
)
```

2. **Frontend calls embedding API:**
```python
# app.py:165-214
async with httpx.AsyncClient(timeout=300.0) as client:  # 5-minute timeout
    response = await client.post(
        f"{API_URL}/api/embed/",
        json={"session_id": session_id}
    )
    result = response.json()
```

**Request:**
```json
POST http://localhost:8000/api/embed/
{
  "session_id": "20251128_140530_abc123"
}
```

3. **Backend embedding process:**
```python
# backend/src/routes/embed.py
1. Locate cleaned markdown file:
   path = f"data/{session_id}/cleaned_markdown/all_pages.json"

2. Load all pages:
   pages = json.load(open(path))
   # [{"page_name": "Home", "content": "...", "url": "..."}, ...]

3. Chunk each page:
   chunks = chunk_text(page["content"], chunk_size=4000, overlap=200)

4. Generate embeddings:
   model = FlagModel("BAAI/bge-m3")  # 1024-dimensional vectors
   embeddings = model.encode(chunks)  # Returns numpy array

5. Insert into Milvus:
   for chunk, embedding in zip(chunks, embeddings):
       collection.insert([{
           "chunk_id": generate_id(),
           "domain": "fitfactoryfitness.com",
           "gym_name": "Fit Factory Fitness",
           "page_name": "Home",
           "page_url": "https://fitfactoryfitness.com",
           "chunk_text": chunk,
           "dense_vector": embedding.tolist()
       }])
```

4. **Backend returns completion:**
```json
{
  "status": "completed",
  "message": "Successfully embedded 15 pages with 127 total chunks",
  "session_id": "20251128_140530_abc123",
  "total_pages": 15,
  "total_chunks": 127
}
```

5. **Frontend enables chat:**
```python
# app.py:343-349
embed_progress.change(
    enable_chat,  # Function that updates component properties
    outputs=[chatbot, chat_input, send_btn, clear_btn]
)

def enable_chat():
    return (
        gr.Chatbot(interactive=True),  # Enable chatbot
        gr.Textbox(interactive=True, placeholder="Ask a question..."),
        gr.Button(interactive=True),  # Enable send button
        gr.Button(interactive=True)   # Enable clear button
    )
```

---

### Flow 3: Q&A Chat System

```
User Question → RAG Pipeline → [Query Rewriting → Vector Search → Answer Synthesis] → Response with Citations
```

**Step-by-Step:**

1. **User asks question:**
```
User types: "What are the business hours?"
Clicks: "Send" (or presses Enter)
```

2. **Frontend prepares request:**
```python
# app.py:216-271
def chat_fn(message, history):
    # Build conversation history
    conversation_history = []
    for user_msg, assistant_msg in history:
        conversation_history.append({"role": "user", "content": user_msg})
        conversation_history.append({"role": "assistant", "content": assistant_msg})

    # Call API
    response = await client.post(
        f"{API_URL}/api/query/ask",
        json={
            "question": message,
            "conversation_history": conversation_history,
            "top_k": 10
        },
        timeout=60.0
    )
```

**Request:**
```json
POST http://localhost:8000/api/query/ask
{
  "question": "What are the business hours?",
  "conversation_history": [
    {"role": "user", "content": "What classes do you offer?"},
    {"role": "assistant", "content": "We offer yoga, boxing, and HIIT..."}
  ],
  "top_k": 10
}
```

3. **Backend RAG Pipeline (3 stages):**

**Stage 1: Query Rewriting (Claude 3.5 Haiku)**
```python
# backend/src/routes/query.py
optimized_query = await query_rewriter.optimize(
    question="What are the business hours?",
    conversation_history=[...]
)
# Result: "business hours operating schedule open close times"
```

**Stage 2: Vector Search (Milvus)**
```python
# Embed optimized query
query_vector = embedding_model.encode([optimized_query])[0]

# Search Milvus
results = collection.search(
    data=[query_vector],
    anns_field="dense_vector",
    param={"metric_type": "COSINE", "params": {"nprobe": 10}},
    limit=10,
    output_fields=["chunk_text", "page_name", "page_url", "gym_name"]
)

# Returns top-k chunks with similarity scores
```

**Stage 3: Answer Synthesis (Claude Sonnet 4)**
```python
# Build context from retrieved chunks
context = "\n\n".join([
    f"Source: {hit.entity.get('page_name')}\n{hit.entity.get('chunk_text')}"
    for hit in results[0]
])

# Generate answer
answer = await claude_client.generate(
    system_prompt="Answer based ONLY on provided information. Cite sources.",
    user_message=f"Context:\n{context}\n\nQuestion: {question}",
    conversation_history=[...]
)
```

4. **Backend response:**
```json
{
  "question": "What are the business hours?",
  "answer": "Fit Factory Fitness is open Monday-Friday 5am-10pm, Saturday-Sunday 7am-8pm.",
  "optimized_query": "business hours operating schedule open close times",
  "sources_used": 3,
  "sources": [
    {
      "gym_name": "Fit Factory Fitness",
      "page_name": "Contact",
      "page_url": "https://fitfactoryfitness.com/contact",
      "score": 0.92
    },
    {
      "gym_name": "Fit Factory Fitness",
      "page_name": "Home",
      "page_url": "https://fitfactoryfitness.com",
      "score": 0.87
    },
    {
      "gym_name": "Fit Factory Fitness",
      "page_name": "FAQ",
      "page_url": "https://fitfactoryfitness.com/faq",
      "score": 0.76
    }
  ]
}
```

5. **Frontend formats and displays:**
```python
# app.py:251-265
# Format sources
sources_text = "\n\n**Sources:**\n"
for i, source in enumerate(sources, 1):
    sources_text += f"{i}. {source['gym_name']} - {source['page_name']} "
    sources_text += f"(relevance: {source['score']:.2f})\n"

# Append to chat history
history.append((message, answer + sources_text))
return history
```

### Primary Flow: Complete Workflow

**Step-by-Step Navigation:**

1. **Landing Screen**
   - User sees: Title "Reppin' Assistant"
   - Subtitle: "Register your gym, or find new ones through our agent"
   - Empty URL input field
   - Disabled chat interface (grayed out)

2. **Enter URL**
   - User types URL: `https://fitfactoryfitness.com`
   - Clicks "Start Scraping" button

3. **Scraping Phase** (Real-time Updates - Polls every 1 second)
   - Progress section displays animated logs:
     ```
     [2025-11-28 14:05:30] Starting scrape of https://fitfactoryfitness.com
     [2025-11-28 14:05:31] Session created: 20251128_140530_abc123
     [2025-11-28 14:05:32] Status: in_progress | Pages: 0/15
     [2025-11-28 14:05:45] Status: in_progress | Pages: 3/15
     [2025-11-28 14:06:02] Status: in_progress | Pages: 7/15
     [2025-11-28 14:06:18] Status: in_progress | Pages: 12/15
     [2025-11-28 14:06:25] Status: completed | Pages: 15/15
     [2025-11-28 14:06:25] Scraping complete!
     ```
   - Terminal-style logs with green text on dark background
   - Progress bar fills: 0% → 20% → 47% → 80% → 100%
   - Updates every 1 second via polling

4. **Scraping Complete → Automatic Transition**
   - Final log: "Scraping complete!"
   - Progress bar: 100%
   - Gradio `.then()` chain automatically triggers embedding

5. **Embedding Phase** (Automatic - No user action required)
   - New section appears with embedding logs:
     ```
     [2025-11-28 14:06:26] Starting embedding process...
     [2025-11-28 14:06:26] Session ID: 20251128_140530_abc123
     [2025-11-28 14:06:27] Calling embedding API...
     [2025-11-28 14:06:45] Loading BGE-M3 model...
     [2025-11-28 14:07:10] Processing 15 pages...
     [2025-11-28 14:07:42] Generated 127 chunks
     [2025-11-28 14:08:15] Inserting vectors into Milvus...
     [2025-11-28 14:08:20] Status: completed
     [2025-11-28 14:08:20] Embedded 15 pages with 127 chunks
     [2025-11-28 14:08:20] Embedding complete!
     ```
   - Shows: Page count, chunk count, completion status
   - No user interaction required

6. **Chat Interface Enabled**
   - Chat components become interactive:
     - Input field activates (no longer grayed out)
     - Placeholder text: "Ask a question about the scraped content..."
     - "Send" button becomes clickable (blue)
     - "Clear Chat" button becomes visible

7. **Ask First Question**
   - User types: "What classes do you offer?"
   - Presses Enter or clicks "Send"
   - Loading indicator appears briefly
   - Answer appears in chat:
     ```
     Assistant: We offer a variety of fitness classes including:
     - Yoga (Vinyasa, Hatha, Power)
     - Boxing and kickboxing
     - HIIT (High-Intensity Interval Training)
     - Strength training
     - Spin classes

     **Sources:**
     1. Fit Factory - Classes (relevance: 0.95)
     2. Fit Factory - Schedule (relevance: 0.87)
     3. Fit Factory - About (relevance: 0.76)
     ```

8. **Continue Conversation** (Contextual)
   - User asks follow-up: "What about pricing?"
   - System maintains context from previous question
   - Provides answer with new sources:
     ```
     Assistant: Our pricing options include:
     - Monthly membership: $89/month
     - Annual membership: $799/year (save 25%)
     - Drop-in class: $25 per class
     - 10-class pack: $200

     We also offer student and military discounts.

     **Sources:**
     1. Fit Factory - Pricing (relevance: 0.98)
     2. Fit Factory - Membership (relevance: 0.91)
     ```

9. **Clear Chat** (Optional)
   - User clicks "Clear Chat" button
   - All messages removed from interface
   - Conversation history reset
   - Can ask new questions without previous context

10. **Scrape Another Site** (Start Over)
    - User enters new URL in top input field
    - Clicks "Start Scraping" again
    - Process repeats from step 3

---

### Error Flow Paths

#### Error 1: Invalid or Empty URL

**Trigger:** User submits empty field or invalid URL format

**Flow:**
1. User clicks "Start Scraping" without entering URL
2. Log displays: `[Error] URL is required`
3. No session created
4. User remains on same screen
5. Can retry with valid URL

**UI State:**
- Scraping section shows error message
- Chat remains disabled
- Input field remains editable

---

#### Error 2: Scraping Failure

**Trigger:** Network error, unreachable site, or robots.txt blocks scraping

**Flow:**
1. Scraping starts normally
2. Session created successfully
3. During scraping, error occurs:
   ```
   [2025-11-28 14:05:30] Starting scrape of https://example.com
   [2025-11-28 14:05:31] Session created: 20251128_140530_abc123
   [2025-11-28 14:05:32] Status: in_progress | Pages: 0/0
   [2025-11-28 14:05:45] Error: Failed to connect to site
   [2025-11-28 14:05:45] Status: failed
   ```
4. Progress bar stops
5. Error message displayed in red

**Recovery:**
- User can submit different URL
- Previous failed session remains in `backend/data/`
- No embedding occurs (chat stays disabled)

---

#### Error 3: Embedding Failure

**Trigger:** Milvus connection issue, file not found, or model loading error

**Flow:**
1. Scraping completes successfully
2. Embedding phase starts automatically
3. Error occurs during embedding:
   ```
   [2025-11-28 14:06:26] Starting embedding process...
   [2025-11-28 14:06:27] Calling embedding API...
   [2025-11-28 14:06:30] HTTP error: 500 - Milvus connection failed
   [2025-11-28 14:06:30] Embedding failed
   ```
4. Chat remains disabled

**Recovery:**
- Check Milvus is running: `docker ps` (should see milvus-standalone)
- Restart Milvus if needed: `cd backend && docker-compose restart`
- Manually trigger embedding via API:
  ```bash
  curl -X POST http://localhost:8000/api/embed/ \
    -H "Content-Type: application/json" \
    -d '{"session_id": "20251128_140530_abc123"}'
  ```
- Refresh frontend page

---

#### Error 4: Query Without Data

**Trigger:** User tries to chat before completing scraping/embedding

**Flow:**
1. User manually enables chat (should not be possible via UI)
2. User types question
3. Backend returns error:
   ```json
   {
     "detail": "No data found in vector database. Please scrape a website first."
   }
   ```
4. Frontend displays: "Please enter your gym website url above, and click 'Start Scraping'."

**Prevention:**
- Chat is disabled by default
- Only enabled after successful embedding
- Gradio component properties control this

---

#### Error 5: API Connection Failure

**Trigger:** Backend server not running or network issue

**Flow:**
1. User clicks "Start Scraping"
2. Frontend attempts API call
3. Connection fails with timeout
4. Error displayed:
   ```
   [Error] Could not connect to backend API
   [Error] Please ensure backend is running on http://localhost:8000
   ```

**Recovery:**
1. Start backend server:
   ```bash
   cd backend
   source venv/bin/activate
   python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
   ```
2. Verify backend health: http://localhost:8000/health
3. Retry scraping in frontend

---

### Alternative Flow: Multiple Sessions

**Current Limitation:** No multi-session UI support

**How It Works:**
1. User scrapes Site A (e.g., `fitfactoryfitness.com`)
   - Data stored with domain: `fitfactoryfitness.com`
   - Session ID: `20251128_140530_abc123`

2. User scrapes Site B (e.g., `pilatesinpink.com`)
   - New session ID: `20251128_141205_def456`
   - Data stored with domain: `pilatesinpink.com`
   - **Both sites now in Milvus database**

3. User asks question: "What are the hours?"
   - Backend searches across **all embedded data**
   - Returns chunks from both sites (if relevant)
   - Sources show which site each answer came from

**Filtering (Backend Capability - Not Exposed in Frontend):**

Backend supports domain filtering:
```python
# Query specific site
POST /api/query/ask
{
  "question": "What classes are offered?",
  "filter": {"domain": "fitfactoryfitness.com"}
}
```

Frontend does not currently expose this. To add filtering, modify `app.py`:
```python
# Add dropdown to select domain
domain_dropdown = gr.Dropdown(
    choices=["All Sites", "fitfactoryfitness.com", "pilatesinpink.com"],
    value="All Sites",
    label="Filter by Site"
)

# Pass filter to API
if domain != "All Sites":
    response = await client.post(
        f"{API_URL}/api/query/ask",
        json={
            "question": message,
            "filter": {"domain": domain}
        }
    )
```

---

## Component Architecture

### Gradio Components (Frontend UI)

**Location:** `frontend/app.py`

#### 1. URL Input Section (Lines 290-296)

```python
with gr.Row():
    url_input = gr.Textbox(
        label="Website URL",
        placeholder="https://example.com",
        scale=4
    )
    scrape_btn = gr.Button("Start Scraping", scale=1, variant="primary")
```

**Functionality:**
- User enters target URL
- Button triggers `start_scraping()` function
- Input remains editable during scraping

---

#### 2. Scraping Progress Section (Lines 299-301)

```python
scrape_progress = gr.HTML(
    value="<div class='log-container'></div>",
    label="Scraping Progress"
)
```

**Functionality:**
- Displays animated terminal-style logs
- Updates via generator yields from `start_scraping()`
- CSS classes: `.log-container`, `.log-entry`, `.log-fade`

**Update Mechanism:**
```python
def start_scraping(url):
    logs = []
    # ... scraping logic ...
    logs.append(f"[{timestamp}] Status: {status}")
    yield session_id, format_logs(logs)  # Triggers UI update
```

---

#### 3. Embedding Progress Section (Lines 303-305)

```python
embed_progress = gr.HTML(
    value="<div class='log-container'></div>",
    label="Embedding Progress"
)
```

**Functionality:**
- Similar to scraping progress
- Updates during embedding phase
- Shows: Model loading, page processing, chunk generation

---

#### 4. Chat Interface (Lines 310-323)

```python
chatbot = gr.Chatbot(
    label="Ask Questions",
    height=400,
    interactive=False  # Disabled initially
)

with gr.Row():
    chat_input = gr.Textbox(
        placeholder="Wait for scraping and embedding to complete...",
        scale=4,
        interactive=False  # Disabled initially
    )
    send_btn = gr.Button("Send", scale=1, interactive=False)

clear_btn = gr.Button("Clear Chat", interactive=False)
```

**Functionality:**
- `chatbot`: Displays conversation history (user + assistant messages)
- `chat_input`: User types questions here
- `send_btn`: Submits question (also triggered by Enter key)
- `clear_btn`: Resets conversation

**Enabling After Embedding:**
```python
def enable_chat():
    return (
        gr.Chatbot(interactive=True),
        gr.Textbox(interactive=True, placeholder="Ask a question..."),
        gr.Button(interactive=True),
        gr.Button(interactive=True)
    )

embed_progress.change(
    enable_chat,
    outputs=[chatbot, chat_input, send_btn, clear_btn]
)
```

---

#### 5. State Components (Line 288)

```python
session_id_state = gr.State(None)
```

**Functionality:**
- Stores active session ID across function calls
- Not visible to user
- Passed between `start_scraping()` → `start_embedding()`

**Usage:**
```python
scrape_btn.click(
    start_scraping,
    inputs=url_input,
    outputs=[session_id_state, scrape_progress]  # Updates state
).then(
    start_embedding,
    inputs=session_id_state,  # Uses state from previous function
    outputs=embed_progress
)
```

---

### Event Handlers

#### Event 1: Scrape Button Click

```python
scrape_btn.click(
    fn=start_scraping,
    inputs=url_input,
    outputs=[session_id_state, scrape_progress]
)
```

**Triggers:** User clicks "Start Scraping"
**Executes:** `start_scraping()` generator function
**Updates:** Session ID state + Progress HTML

---

#### Event 2: Automatic Embedding Trigger

```python
.then(
    fn=start_embedding,
    inputs=session_id_state,
    outputs=embed_progress
)
```

**Triggers:** After `start_scraping()` completes
**Executes:** `start_embedding()` function
**Updates:** Embedding progress HTML

---

#### Event 3: Send Button Click

```python
send_btn.click(
    fn=chat_fn,
    inputs=[chat_input, chatbot],
    outputs=[chatbot, chat_input]
)
```

**Triggers:** User clicks "Send" button
**Executes:** `chat_fn()` async function
**Updates:** Chat history + Clears input field

---

#### Event 4: Enter Key Press (Chat Input)

```python
chat_input.submit(
    fn=chat_fn,
    inputs=[chat_input, chatbot],
    outputs=[chatbot, chat_input]
)
```

**Triggers:** User presses Enter in chat input
**Executes:** Same as send button
**Updates:** Chat history + Clears input field

---

#### Event 5: Clear Chat Button

```python
clear_btn.click(
    fn=lambda: ([], ""),
    outputs=[chatbot, chat_input]
)
```

**Triggers:** User clicks "Clear Chat"
**Executes:** Lambda function returns empty list and string
**Updates:** Resets chatbot history and clears input

---

#### Event 6: Embedding Completion → Enable Chat

```python
embed_progress.change(
    fn=enable_chat,
    outputs=[chatbot, chat_input, send_btn, clear_btn]
)
```

**Triggers:** `embed_progress` HTML content changes (completion detected)
**Executes:** `enable_chat()` function
**Updates:** Makes all chat components interactive

---

### Backend API Endpoints Reference

**Base URL:** `http://localhost:8000` (configurable via `API_BASE_URL` env var)

#### POST /api/scrape

**Purpose:** Start new scraping session

**Request:**
```json
{
  "url": "https://fitfactoryfitness.com",
  "mode": "whole-site",
  "purpose": "Web scraping for Q&A"
}
```

**Response:**
```json
{
  "session_id": "20251128_140530_abc123",
  "status": "pending",
  "message": "Scraping started",
  "url": "https://fitfactoryfitness.com"
}
```

**Frontend Usage:** `app.py` line 72

---

#### GET /api/sessions/{session_id}

**Purpose:** Poll scraping progress

**Request:** No body (session ID in URL)

**Response:**
```json
{
  "session_id": "20251128_140530_abc123",
  "url": "https://fitfactoryfitness.com",
  "status": "in_progress",
  "pages_scraped": 7,
  "total_pages": 15,
  "created_at": "2025-11-28T14:05:30",
  "updated_at": "2025-11-28T14:06:15"
}
```

**Frontend Usage:** `app.py` line 95 (polling loop)

---

#### POST /api/embed/

**Purpose:** Generate embeddings for scraped session

**Request:**
```json
{
  "session_id": "20251128_140530_abc123"
}
```

**Response:**
```json
{
  "status": "completed",
  "message": "Successfully embedded 15 pages with 127 total chunks",
  "session_id": "20251128_140530_abc123",
  "total_pages": 15,
  "total_chunks": 127
}
```

**Frontend Usage:** `app.py` line 174

---

#### POST /api/query/ask

**Purpose:** Ask question with RAG pipeline

**Request:**
```json
{
  "question": "What are the business hours?",
  "conversation_history": [
    {"role": "user", "content": "What classes do you offer?"},
    {"role": "assistant", "content": "We offer yoga, boxing, HIIT..."}
  ],
  "top_k": 10
}
```

**Response:**
```json
{
  "question": "What are the business hours?",
  "answer": "We are open Monday-Friday 5am-10pm, Saturday-Sunday 7am-8pm.",
  "optimized_query": "business hours operating schedule open close times",
  "sources_used": 3,
  "sources": [
    {
      "gym_name": "Fit Factory Fitness",
      "page_name": "Contact",
      "page_url": "https://fitfactoryfitness.com/contact",
      "chunk_text": "Our hours are...",
      "score": 0.92
    }
  ]
}
```

**Frontend Usage:** `app.py` line 230

---

## Configuration

### Environment Variables

**File Location:** `frontend/.env`

#### API_BASE_URL

**Purpose:** Backend API endpoint URL

**Default:** `http://localhost:8000`

**Production Example:**
```bash
API_BASE_URL=https://api.scraperagent.com
```

**Usage in Code:**
```python
API_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
response = await client.post(f"{API_URL}/api/scrape", ...)
```

---

#### GRADIO_SERVER_PORT

**Purpose:** Port for frontend server

**Default:** `7860`

**Custom Port:**
```bash
GRADIO_SERVER_PORT=8080
```

**Usage in Code:**
```python
port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
demo.launch(server_port=port)
```

---

#### GRADIO_SERVER_NAME

**Purpose:** Host binding (0.0.0.0 for public, 127.0.0.1 for local only)

**Default:** `0.0.0.0` (listens on all interfaces)

**Local Only:**
```bash
GRADIO_SERVER_NAME=127.0.0.1
```

**Production (Required for Deployment):**
```bash
GRADIO_SERVER_NAME=0.0.0.0
```

---

### Custom CSS Styling

**Location:** `app.py` lines 15-49

```python
custom_css = """
.log-container {
    background-color: #1e1e1e;
    color: #00ff00;
    font-family: 'Courier New', monospace;
    padding: 15px;
    border-radius: 5px;
    max-height: 400px;
    overflow-y: auto;
}

.log-entry {
    margin: 5px 0;
    animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}
"""
```

**Modifications:**
- Change `#00ff00` (green) to customize text color
- Adjust `max-height: 400px` for log container size
- Modify `animation` for different fade effects

---

## Production Deployment Checklist

### Pre-Deployment Tasks

- [ ] **Update CORS in backend** - Change from `allow_origins=["*"]` to specific domains
- [ ] **Add rate limiting** - Install `slowapi` and configure limits per endpoint
- [ ] **Set DEBUG=False** - Disable debug mode in production environment
- [ ] **Secure API keys** - Move `ANTHROPIC_API_KEY` to secure secret management
- [ ] **Test full workflow** - Scrape → Embed → Query in staging environment
- [ ] **Set up error monitoring** - Configure Sentry or similar service
- [ ] **Configure Milvus backups** - Enable automatic backups for vector database
- [ ] **Add authentication** - Implement API key or OAuth if needed for private use
- [ ] **Review input validation** - Ensure URL validation blocks localhost/private IPs
- [ ] **Document API** - Update API documentation for public endpoints

---

### Deployment Steps (Platform-Specific)

#### Railway

1. [ ] Install Railway CLI: `npm install -g railway`
2. [ ] Login: `railway login`
3. [ ] Create projects for backend and frontend
4. [ ] Deploy Milvus: `cd backend && railway up`
5. [ ] Set environment variables (backend):
   ```bash
   railway variables set ANTHROPIC_API_KEY=sk-ant-xxx
   railway variables set MILVUS_HOST=milvus.railway.internal
   railway variables set DEBUG=False
   railway variables set ALLOWED_ORIGINS=https://app.yourdomain.com
   ```
6. [ ] Set environment variables (frontend):
   ```bash
   railway variables set API_BASE_URL=https://backend.railway.app
   railway variables set GRADIO_SERVER_NAME=0.0.0.0
   ```
7. [ ] Deploy backend: `railway up`
8. [ ] Deploy frontend: `railway up`
9. [ ] Add custom domain (optional): `railway domain`
10. [ ] Configure health checks: `railway settings --healthcheck-path=/health`

---

### Post-Deployment Verification

- [ ] **Test health endpoints**
  - Backend: `curl https://api.yourdomain.com/health`
  - Milvus: `curl https://api.yourdomain.com/api/query/health`

- [ ] **Verify CORS configuration**
  - Open browser dev tools
  - Check for CORS errors in console
  - Test cross-origin requests

- [ ] **Test complete user flow**
  - Submit URL for scraping
  - Wait for scraping completion
  - Verify embedding completes
  - Ask test questions
  - Check source citations

- [ ] **Check Milvus data persistence**
  - Restart Milvus container
  - Verify data still accessible
  - Test queries return previous data

- [ ] **Verify environment variables loaded**
  - Check backend logs for API key (should be loaded, not printed)
  - Verify correct API base URL in frontend
  - Confirm CORS origins match deployment domains

- [ ] **Test error handling**
  - Submit invalid URL
  - Stop backend mid-scrape
  - Query before embedding
  - Verify user-friendly error messages

- [ ] **Monitor logs for issues**
  - Check for startup errors
  - Verify no credential leaks
  - Look for unexpected warnings

- [ ] **Check response times**
  - Scraping: Typical 30s-2min depending on site size
  - Embedding: Typical 30s-1min for 15 pages
  - Queries: Should be <5s per question

- [ ] **Verify SSL certificates**
  - Check HTTPS works on all domains
  - No certificate warnings in browser
  - Proper redirect from HTTP to HTTPS

- [ ] **Test from different networks**
  - Mobile device
  - Different ISP
  - VPN connection
  - Verify global accessibility

---

## Troubleshooting

### Issue: Frontend can't connect to backend

**Symptoms:**
- Error: "Could not connect to backend API"
- Timeout when clicking "Start Scraping"

**Solutions:**

1. **Check backend is running:**
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status": "ok"}
   ```

2. **Verify API_BASE_URL:**
   ```bash
   cat frontend/.env | grep API_BASE_URL
   # Should match backend address
   ```

3. **Check CORS configuration:**
   - Backend `src/main.py` should include frontend URL in `allow_origins`
   - Restart backend after CORS changes

4. **Test from command line:**
   ```bash
   curl -X POST http://localhost:8000/api/scrape \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com", "mode": "whole-site"}'
   ```

---

### Issue: Embedding fails

**Symptoms:**
- "Embedding failed" message in logs
- HTTP 500 error from `/api/embed/`

**Solutions:**

1. **Check Milvus is running:**
   ```bash
   docker ps | grep milvus
   # Should show milvus-standalone container
   ```

2. **Restart Milvus:**
   ```bash
   cd backend
   docker-compose restart
   docker logs milvus-standalone --tail=50
   ```

3. **Verify markdown file exists:**
   ```bash
   ls backend/data/20251128_*/cleaned_markdown/
   # Should show .json files
   ```

4. **Check backend logs:**
   ```bash
   # Look for BGE-M3 model loading errors
   # Look for Milvus connection errors
   ```

---

### Issue: Chat not working

**Symptoms:**
- Chat input remains disabled after embedding
- Questions return errors

**Solutions:**

1. **Verify query router registered:**
   ```python
   # backend/src/main.py should include:
   from src.routes import query
   app.include_router(query.router)
   ```

2. **Test query endpoint directly:**
   ```bash
   curl -X POST http://localhost:8000/api/query/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "test", "top_k": 5}'
   ```

3. **Check Milvus has data:**
   ```bash
   curl http://localhost:8000/api/query/health
   # Should return collection info
   ```

4. **Verify embedding completed:**
   - Check embedding logs show "completed" status
   - Verify chunk count > 0

---

### Issue: Slow scraping performance

**Symptoms:**
- Scraping takes >5 minutes for small sites
- Progress stuck on specific pages

**Solutions:**

1. **Check Playwright installation:**
   ```bash
   cd backend
   source venv/bin/activate
   playwright install chromium
   ```

2. **Verify network speed:**
   - Test site accessibility: `curl -I https://target-site.com`
   - Check if site has rate limiting

3. **Review backend logs:**
   - Look for timeout errors
   - Check if specific URLs are slow

4. **Adjust timeout settings:**
   ```python
   # backend/src/services/browser_client.py
   page.goto(url, timeout=30000)  # Increase if needed
   ```

---

### Issue: No cleaned markdown files found

**Symptoms:**
- Embedding fails with "file not found"
- Empty `cleaned_markdown` directory

**Solutions:**

1. **Check scraping completed:**
   ```bash
   curl http://localhost:8000/api/sessions/YOUR_SESSION_ID
   # Status should be "completed"
   ```

2. **Verify directory structure:**
   ```bash
   ls -R backend/data/20251128_*/
   # Should show: metadata.json, cleaned_markdown/
   ```

3. **Check file permissions:**
   ```bash
   ls -la backend/data/
   # Verify write permissions
   ```

4. **Review orchestrator logs:**
   - Look for HTML parsing errors
   - Check for sitemap discovery issues

---

### Issue: Questions return irrelevant answers

**Symptoms:**
- Answers don't match question
- Low relevance scores (<0.5)
- Wrong sources cited

**Solutions:**

1. **Check embedding quality:**
   - Verify pages were chunked correctly
   - Review chunk size (default: 4000 chars)
   - Check if important content was extracted

2. **Adjust `top_k` parameter:**
   ```python
   # Increase number of retrieved chunks
   response = await client.post(
       f"{API_URL}/api/query/ask",
       json={"question": question, "top_k": 15}  # Increase from 10
   )
   ```

3. **Review source pages:**
   - Check `backend/data/*/cleaned_markdown/*.json`
   - Verify content quality and completeness

4. **Test query rewriting:**
   - Check `optimized_query` in response
   - May need to adjust Claude Haiku prompt

---

## Additional Resources

### Project Structure

```
frontend/
├── app.py                 # Main Gradio application
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
├── .env                  # Local environment config (gitignored)
├── README.md             # This file
└── README_CONTINUATION.md # Extended documentation
```

### Key Functions Reference

**Location:** `frontend/app.py`

| Function | Lines | Purpose |
|----------|-------|---------|
| `start_scraping()` | 68-163 | Polls backend for scraping progress, yields UI updates |
| `start_embedding()` | 165-214 | Calls embedding API, displays progress logs |
| `chat_fn()` | 216-271 | Handles user questions, calls RAG endpoint |
| `format_logs()` | 51-66 | Generates animated HTML logs with timestamps |
| `enable_chat()` | 273-279 | Activates chat interface after embedding completes |

### API Endpoints Summary

| Endpoint | Method | Purpose | Frontend Function |
|----------|--------|---------|-------------------|
| `/api/scrape` | POST | Start scraping session | `start_scraping()` line 72 |
| `/api/sessions/{id}` | GET | Poll scraping progress | `start_scraping()` line 95 |
| `/api/embed/` | POST | Generate embeddings | `start_embedding()` line 174 |
| `/api/query/ask` | POST | RAG Q&A with citations | `chat_fn()` line 230 |
| `/health` | GET | Backend health check | Manual testing |
| `/api/query/health` | GET | Milvus connection check | Manual testing |

---

## License

See project root for license information.

---

## Support & Contributing

For issues, feature requests, or questions:
- Check backend logs: `docker logs milvus-standalone` or uvicorn output
- Review Gradio terminal output for frontend errors
- Verify all dependencies installed: `pip list`
- Ensure environment configuration matches `.env.example`