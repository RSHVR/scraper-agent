---
title: Website Chat
emoji: 💬
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
---

# Agentic Scraper

AI-powered web scraping system with intelligent content extraction, vector embeddings, and natural language Q&A capabilities.

## Overview

Scraper Agent combines web scraping, vector search, and Claude AI to enable natural language querying of website content. Simply provide a URL, and the system will scrape the site, generate embeddings, and allow you to ask questions about the content.

### Key Features

- **Intelligent Web Scraping**: Sitemap-based discovery with Playwright browser automation
- **AI-Powered Extraction**: Claude Sonnet 4 for structured data extraction
- **Vector Search**: Cohere embed-v4.0 (1536-dim) with ChromaDB vector database
- **RAG Q&A Pipeline**: 3-stage retrieval-augmented generation for accurate answers
- **LLM Provider Choice**: Switch between Claude and Ollama (Kimi K2) via UI toggle
- **Real-time Progress**: Animated progress tracking
- **Web Interface**: Gradio-based UI with automatic workflow orchestration

### Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Frontend  │      │   Cohere     │      │  ChromaDB   │
│  (Gradio)   │ ───> │  embed/rank  │ ───> │  (local)    │
│  Port 7860  │      └──────────────┘      └─────────────┘
└─────────────┘               │
       │                      v
       │              ┌──────────────┐
       └────────────> │   LLM API    │
                      │ Claude/Ollama│
                      └──────────────┘
```

---

## Quick Start

### Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose**
- **Cohere API Key** ([Get one here](https://dashboard.cohere.com/)) - Required for embeddings
- **Anthropic API Key** ([Get one here](https://console.anthropic.com/)) - For Claude provider
- **Ollama** (optional) - For local/cloud Kimi K2 provider

### Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd scraper-agent
```

2. **Start Milvus (Vector Database):**
```bash
cd backend
docker-compose up -d
```

3. **Set up Backend:**
```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# Configure environment
cp .env.example .env
# Edit .env and add: ANTHROPIC_API_KEY=sk-ant-...

# Start backend server
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

4. **Set up Frontend:**
```bash
cd ../frontend
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment (optional)
cp .env.example .env

# Start frontend
python app.py
```

5. **Access the application:**
   - **Frontend UI**: http://localhost:7860
   - **Backend API**: http://localhost:8000
   - **API Docs**: http://localhost:8000/docs

---

## Usage

### Web Interface (Recommended)

1. Open http://localhost:7860
2. Enter a website URL (e.g., `https://example.com`)
3. Click "Start Scraping" and wait for completion
4. Embedding generation starts automatically
5. Chat interface activates when ready
6. Ask questions about the scraped content!

### API Usage

**Start Scraping:**
```bash
curl -X POST http://localhost:8000/api/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "mode": "whole-site",
    "purpose": "I need the data"
  }'
```

**Generate Embeddings:**
```bash
curl -X POST http://localhost:8000/api/embed/ \
  -H "Content-Type: application/json" \
  -d '{"session_id": "YOUR_SESSION_ID"}'
```

**Ask Questions:**
```bash
curl -X POST http://localhost:8000/api/query/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the business hours?",
    "top_k": 10
  }'
```

---

## How It Works

### 1. Scraping Phase
- Discovers URLs via sitemap parsing
- Fetches pages using Playwright (headless browser)
- Converts HTML to clean markdown
- Stores content in structured JSON format

### 2. Embedding Phase
- Chunks markdown content (4000 chars max)
- Generates Cohere embed-v4.0 embeddings (1536-dimensional)
- Stores vectors in ChromaDB with metadata
- Uses HNSW index for fast similarity search

### 3. Q&A Phase (RAG Pipeline)
- **Stage 1**: Query optimization with Claude Haiku or Kimi K2
- **Stage 2**: Vector similarity search + Cohere rerank-v4.0-fast
- **Stage 3**: Answer synthesis with Claude Sonnet or Kimi K2
- Returns natural language answer with source citations

---

## Technology Stack

### AI & Embeddings
- **Cohere embed-v4.0** - Text embeddings (1536-dim)
- **Cohere rerank-v4.0-fast** - Result reranking
- **Claude Sonnet/Haiku** - Anthropic LLM (default)
- **Ollama Kimi K2** - Alternative LLM (local/cloud)

### Backend
- **ChromaDB** - Vector database (persistent, local)
- **Playwright** - Browser automation
- **BeautifulSoup** - HTML parsing
- **Pydantic** - Data validation

### Frontend
- **Gradio 6.0+** - Python web UI framework
- Single-process architecture (HuggingFace Spaces compatible)

### Infrastructure
- **Docker** - Containerized deployment
- **Python 3.11+** - Runtime environment

---

## Project Structure

```
scraper-agent/
├── backend/              # FastAPI backend
│   ├── src/
│   │   ├── agents/      # AI agents (orchestrator, extractors)
│   │   ├── routes/      # API endpoints
│   │   ├── services/    # Core services (storage, vector, browser)
│   │   ├── models/      # Pydantic data models
│   │   └── main.py      # FastAPI application
│   ├── data/            # Session storage (runtime)
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── README.md        # Detailed backend documentation
│
├── frontend/            # Gradio frontend
│   ├── app.py          # Main application
│   ├── requirements.txt
│   └── README.md       # Detailed frontend documentation
│
└── README.md           # This file
```

---

## Configuration

### Environment Variables

Create `.env` in the root directory:
```bash
# Required
COHERE_API_KEY=your-cohere-key        # Required for embeddings/reranking

# LLM Provider (choose one or both)
ANTHROPIC_API_KEY=sk-ant-your-key     # For Claude provider
OLLAMA_HOST=https://ollama.com        # For Ollama cloud (or http://localhost:11434 for local)
OLLAMA_API_KEY=your-ollama-key        # Required for Ollama cloud
OLLAMA_MODEL=kimi-k2:1t-cloud         # Ollama model to use

# Optional
GRADIO_SERVER_PORT=7860
```

### LLM Provider Options

| Provider | Models | Setup |
|----------|--------|-------|
| **Claude** (default) | Haiku + Sonnet | Set `ANTHROPIC_API_KEY` |
| **Ollama Local** | Kimi K2 | Run `ollama serve`, set `OLLAMA_HOST=http://localhost:11434` |
| **Ollama Cloud** | Kimi K2 | Set `OLLAMA_HOST=https://ollama.com` + `OLLAMA_API_KEY` |

---

## Verification & Health Checks

**Check Backend:**
```bash
curl http://localhost:8000/health
```

**Check Milvus:**
```bash
curl http://localhost:9091/healthz
curl http://localhost:8000/api/query/health
```

**Check All Services:**
```bash
docker ps  # Should show etcd, minio, milvus
```

---

## Troubleshooting

### Milvus Connection Issues
```bash
cd backend
docker-compose down
docker-compose up -d
docker logs milvus-standalone
```

### Backend Not Starting
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### Embedding Failures
- Verify Milvus is running: `docker ps | grep milvus`
- Check cleaned markdown exists: `ls backend/data/*/cleaned_markdown/`
- Review backend logs for BGE-M3 model loading errors

### Frontend Can't Connect
- Verify backend is running: `curl http://localhost:8000/health`
- Check `API_BASE_URL` in `frontend/.env`
- Ensure CORS allows frontend origin (default allows all)

---

## Documentation

- **Backend Details**: See `backend/README.md` for comprehensive API documentation, architecture details, and deployment guides
- **Frontend Details**: See `frontend/README.md` for UI workflow, component architecture, and hosting options
- **API Reference**: Visit http://localhost:8000/docs for interactive Swagger documentation

---

## Development

### Running Tests
```bash
cd backend
pytest
pytest --cov=src --cov-report=html
```

### Adding Custom Agents
Extend `BaseSchemaGenerator` or `BaseContentExtractor` in `backend/src/agents/specialized/`

### Modifying UI
Edit `frontend/app.py` - all UI components use Gradio's Python API

---

## Production Deployment

### Recommended Platforms
- **Railway** - Native Docker Compose support, easy deployment
- **Fly.io** - Excellent Docker support, global edge deployment
- **Render** - Simple Python hosting with persistent volumes

### Key Considerations
- Set `DEBUG=False` in production
- Configure CORS with specific allowed origins
- Add rate limiting (use `slowapi`)
- Secure API keys with platform secret management
- Set up health check endpoints
- Configure Milvus persistent volumes

See `backend/README.md` and `frontend/README.md` for detailed deployment instructions.

---

## Important Notes

### Docker Containerization
- **Milvus ONLY** runs in Docker (via docker-compose.yml)
- **Backend must run locally** due to PyTorch segmentation fault in containerized environments
- **Frontend runs locally** as a Gradio server

This hybrid deployment is necessary until the PyTorch Docker issue is resolved.

### Data Persistence
- Session data stored in `backend/data/`
- Vector embeddings stored in Milvus (Docker volumes)
- Ensure persistent volumes configured in production

---

## License

Apache 2.0

---

## Support

For detailed troubleshooting, API reference, and advanced configuration:
- **Backend docs**: `backend/README.md`
- **Frontend docs**: `frontend/README.md`
- **API docs**: http://localhost:8000/docs
- **Check logs**: Backend terminal, Docker logs, browser console
