# The Lore of Scraper Agent

The complete history of this project, from a gym-focused data scraper to an AI-powered web intelligence platform.

---

## Chapter 1: The Gym Scraper (November 8, 2025)

The project began life as **scraper-agent v0.1.0** — a purpose-built tool for scraping gym and fitness websites. The original stack was:

- **Backend**: FastAPI with Anthropic Claude (Sonnet) for LLM intelligence
- **Frontend**: Gradio UI
- **Embeddings**: BGE-M3 (via FlagEmbedding) — a heavyweight open-source embedding model
- **Vector DB**: Milvus — a dedicated vector database server
- **Scraping**: httpx for static pages, Playwright for JS-rendered pages

The architecture was a **deterministic pipeline**: URL → Discover URLs → Fetch HTML → Clean → Chunk → Embed → Done. No reasoning, no adaptation. The LLM was only used for query synthesis after data was already ingested.

Within a day, the model was reverted from Claude 4 back to Sonnet (`revert to sonnet 4`, Nov 9) — likely a cost or latency decision.

---

## Chapter 2: Building the Platform (November 26–28, 2025)

A burst of development over Thanksgiving weekend transformed the scraper from a script into a platform:

**CLI Tools** (Nov 26): Added multi-level progress tracking and command-line tools for running scrapes without the frontend.

**Docker & Services** (Nov 27): Full Docker support with compose files. Added query/embed endpoints, making the backend a proper API server rather than a monolithic app. Updated README with deployment docs.

**The Great Nov 28 Sprint**: Eight commits in a single day:
- Phase 2 embedding endpoint and Phase 3 query/RAG endpoints went live
- Fixed a segmentation fault in BGE-M3 DataLoader by adding threading controls
- Fixed frontend session polling and added `pages_scraped` tracking
- Implemented incremental progress tracking so users could watch scrapes in real time
- Added dark theme styling, blue button accents, and branding updates
- Merged the `feature/simplified-httpx-crawling` branch — a major refactor of the HTTP layer

**Gradio 6.0 Upgrade** (Nov 28): Upgraded to Gradio 6.0.1 with its new chatbot features — avatar images, feedback options, native examples. Then iterated: removed source citations from chatbot responses, added custom avatar images. The frontend was becoming more polished.

---

## Chapter 3: Going General-Purpose (December 2–6, 2025)

**The Identity Shift** (Dec 2): The project shed its gym-scraper identity. Refactored from "gym-focused" to "general-purpose Agentic Scraper." Updated color scheme to match the new brand. This was the moment the project stopped being a toy and started becoming a product.

**Milvus → ChromaDB Migration** (Dec 3): Replaced Milvus (a separate server process requiring Docker) with ChromaDB (an embedded, pip-installable vector store). This was a major simplification — ChromaDB runs in-process, no external infrastructure needed. The migration was motivated by HuggingFace Spaces deployment: Milvus can't run in a Spaces container.

**The HuggingFace Spaces Saga** (Dec 3): Twelve commits in one day trying to get the app deployed on HuggingFace Spaces. This was a war of attrition against platform constraints:
1. Added HF Spaces deployment config
2. Fixed `colorFrom` in README for Spaces compatibility
3. Fixed config defaults for Spaces environment
4. Fixed Docker SDK deployment issues
5. Realized Docker SDK won't work — migrated to Gradio SDK
6. Hit FastAPI version conflict with Gradio 6.0.1
7. Hit python-multipart version conflict
8. Fixed CSS negative padding breaking the deployment
9. Added diagnostic logging to debug API key validation
10. Fixed timeout and path issues for Spaces
11. Disabled Playwright (can't run headless browsers in Spaces)
12. Fixed 503 error by making FlagEmbedding import lazy (BGE-M3 was crashing on import)
13. Moved storage to /tmp for Spaces compatibility
14. Changed backend port from 8000 to 8080

A painful lesson in platform compatibility, but the app was live.

**Single-Page Mode** (Dec 5): Added the ability to scrape just one URL instead of crawling an entire site. Added a mode selection toggle to the frontend UI.

**Ollama & Cohere** (Dec 17): Two major additions:
- **Ollama support**: Local LLM inference, no API keys needed. Kimi K2 model support added.
- **Cohere embeddings migration**: Replaced BGE-M3 with Cohere embed-v4.0. This was strategic — BGE-M3 caused seg faults, required heavyweight dependencies, and couldn't run on HF Spaces. Cohere's API was faster, more reliable, and added reranking (rerank-v4.0-fast) for search quality.

Renamed the HF Space to "Website Chat" to reflect the broader purpose.

**URL Normalization** (Dec 18): Added flexible URL input handling — users could type `example.com` without `https://` and it would work.

---

## Chapter 4: The Multi-Provider Era (January 2026)

**HuggingFace Provider** (Jan 7): Added HuggingFace Inference API as an LLM provider alongside Claude, Ollama, and Cohere. Fixed dropdown CSS, cleaned up tests. The system now supported four LLM backends.

**Cleanup Pass** (Jan 12): Removed deprecated code (the old Milvus vector service, data aggregator, URL queue, web search service, schema generator, content extractor). Updated docs. Added progress UI improvements. The codebase was getting leaner.

---

## Chapter 5: The Agentic Transformation (January 30, 2026)

This was the biggest architectural change in the project's history.

**The Problem**: The scraper was still a deterministic pipeline. `orchestrator.py` ran a fixed sequence: discover URLs → fetch → clean → embed. No reasoning about what to do when pages fail, when content is behind JavaScript, when pagination exists, when login walls appear.

**The Solution**: A true ReAct (Reason-Act-Observe) agent built on LangGraph.

Two design documents were written to guide the transformation:
- **AGENT-CONTEXT.md**: High-level context for the agentic scraper — what exists, what to build, what questions to consider
- **AGENTIC-ARCHITECTURE.md**: Detailed architecture with tool definitions, the ReAct loop diagram, ToolExecutor class, and example agent runs

The implementation (`Add LangGraph agentic scraper with multi-provider support`, Jan 30) introduced:

**LangGraph ReAct Agent** (`agents/agentic_scraper.py`): Uses `create_react_agent` from LangGraph with streaming events and token tracking. The agent decides what to do next based on observations.

**14 LangChain Tools** (`agents/tools.py`): Each tool wraps an existing service:
- `analyze_url` — classify site type, recommend strategy
- `fetch_page` — simple HTTP fetch
- `render_with_browser` — Playwright for JS-heavy sites
- `extract_links` — find all links on a page
- `extract_content` — CSS selector-based extraction
- `search_page_content` — regex search within fetched HTML
- `click_element` — browser interaction
- `scroll_and_wait` — trigger lazy loading
- `convert_to_markdown` — HTML → clean markdown
- `discover_site_urls` — sitemap/robots.txt discovery
- `embed_content` — vector store ingestion
- `search_embedded_content` — semantic search over ingested data
- `save_results` — persist extracted data (terminal)
- `report_failure` — give up gracefully (terminal)

**Global ToolContext** (`tools.py:32`): A shared state object holding the session ID, current HTML, browser client, and all service references. Scoped per agent session.

**LLM Factory** (`agents/llm_factory.py`): Factory function `get_llm(provider, model, callbacks)` that returns a LangChain-compatible LLM for any of the four providers.

**System Prompts** (`agents/prompts.py`): `SCRAPER_SYSTEM_PROMPT` instructs the agent on strategy — try HTTP first, fall back to browser, handle errors gracefully.

**V1 API Routes** (`routes/v1/agentic.py`): Both REST (`POST /api/v1/scrape/agentic`) and WebSocket (`/api/v1/scrape/agentic/ws`) endpoints with real-time streaming of agent steps.

**Agentic Models** (`models/agentic.py`): `AgenticScrapeRequest`, `AgentResult`, `AgentCostMetrics`, `AgentMessage` — full cost tracking per agent run.

The agent architecture was a fundamentally different approach. Instead of "run this pipeline," users could say "extract all product prices from this store" and the agent would figure out how — trying HTTP first, falling back to browser rendering, scrolling for lazy content, paginating through results, all autonomously.

---

## Chapter 6: Authentication & Identity (February 5, 2026)

**Supabase Authentication** (`Add Supabase authentication system`, Feb 5): The app was no longer a toy running on localhost. It needed user accounts.

Added:
- **Supabase JWT auth**: Register, login, token refresh
- **API key system**: Generate and manage API keys for programmatic access
- **Auth dependencies**: `get_current_user`, `get_rate_limit_key`, `require_scope` — reusable FastAPI dependencies
- **Rate limiting**: slowapi with per-user limits (authenticated users get higher limits)
- **Row-level security**: Users can only see their own data

Also in this commit: an OSINT research script (`scripts/search_arshveer.py`) — a one-off tool, separate from the main product.

---

## Chapter 7: The API Factory (February 9, 2026)

Born from a research question: *"What does Parse.bot mean when they say their browser-less architecture is more reliable than web drivers?"*

The answer revealed a paradigm the project hadn't considered: **HTTP request reverse-engineering**. Instead of rendering pages in headless browsers (Playwright), intercept the underlying XHR/fetch API calls a website makes, then replay them directly via HTTP. The browser is used once for discovery, never again for execution.

This wasn't a feature to bolt onto the existing scraper — it was a **new product**. A custom API factory for any website.

### The Architecture

**Discovery** (expensive, runs once):
1. Load URL in Playwright with `page.on("response")` listener
2. Capture all XHR/fetch traffic — URLs, methods, headers, response bodies
3. Filter for JSON APIs (ignore analytics, ads, tracking pixels)
4. Feed captured traffic to LLM for one-shot analysis
5. LLM classifies endpoints, names them, detects auth patterns, identifies pagination
6. Output: a **Recipe** — a persistent, reusable API specification

**Execution** (cheap, runs thousands of times):
1. Load recipe from Supabase
2. Ensure valid auth state (cookies/tokens, refresh if expired)
3. Make direct HTTP call via httpx
4. Return JSON data

No browser. No rendering. No Playwright. Just HTTP.

### Key Design Decisions

1. **Recipes, not results**: Store the *instructions* for getting data, not the data itself. A recipe for "get Hacker News front page" can be executed repeatedly as content changes.

2. **Discovery/Execution separation**: Discovery is expensive (browser + LLM). Execution is cheap (one HTTP call). This inversion — spend more upfront to save orders of magnitude later — is the core insight.

3. **Four levels of auth**: none → cookie_session → CSRF → bearer_token. V1 handles levels 1–3. The auth handler caches state per domain with a 15-minute TTL and auto-refreshes on 401/403.

4. **Own module, not agent tools**: The API Factory lives at `backend/src/api_factory/`, completely separate from the agentic scraper. Different product, different architecture, different user mental model.

5. **One-shot LLM analysis**: The TrafficAnalyzer uses a single LLM call (not a ReAct loop) to classify captured APIs. Discovery is a classification task, not a reasoning task.

### The Implementation

```
backend/src/api_factory/
├── __init__.py
├── models.py                    # Recipe, EndpointDefinition, AuthFlow, DynamicValue, etc.
├── discovery/
│   ├── interceptor.py           # Playwright network capture (page.on("response"))
│   └── analyzer.py              # LLM one-shot traffic analysis → Recipe
├── execution/
│   ├── engine.py                # httpx recipe executor with retry on 401/403
│   └── auth_handler.py          # Cookie/CSRF token lifecycle management
└── storage/
    └── recipe_store.py          # Supabase CRUD for recipes
```

**REST API surface:**
- `POST /api/v1/factory/discover` — URL → Recipe (3/minute rate limit)
- `GET /api/v1/factory/recipes` — list user's recipes
- `GET /api/v1/factory/recipes/{id}` — get specific recipe
- `POST /api/v1/factory/execute` — run a recipe endpoint (60/minute rate limit)
- `DELETE /api/v1/factory/recipes/{id}` — delete a recipe
- `POST /api/v1/factory/recipes/{id}/refresh` — re-run discovery

**Supabase migration required:**
```sql
create table recipes (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users(id) not null,
    domain text not null,
    name text not null,
    source_url text not null,
    auth_flow jsonb not null default '{}',
    endpoints jsonb not null default '[]',
    raw_capture_summary text default '',
    status text not null default 'active',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
alter table recipes enable row level security;
create policy "Users can manage own recipes" on recipes
    for all using (auth.uid() = user_id);
```

---

## Chapter 8: The Idea File

A product idea exists in `IDEAS.md` — an **AI Brand Monitoring Tool**:

> "How does AI see your brand, and how do you fix it?"

The concept: query ChatGPT, Claude, and Perplexity with "What is [Company]?" and analyze the responses. Trace sources, compare competitors, track sentiment, monitor changes. "AI SEO" for a world where customers ask chatbots instead of Google.

This hasn't been built yet, but it represents the direction the project could go — from scraping tools to AI intelligence products.

---

## Timeline Summary

| Date | Milestone |
|------|-----------|
| Nov 8, 2025 | v0.1.0 — gym-focused scraper with BGE-M3 + Milvus |
| Nov 26–28 | Platform buildout: CLI, Docker, API endpoints, progress tracking, dark theme |
| Dec 2 | Rebranded from gym-scraper to general-purpose |
| Dec 3 | Milvus → ChromaDB migration, HuggingFace Spaces deployment saga (12+ commits) |
| Dec 5 | Single-page scraping mode |
| Dec 17 | Ollama/Kimi K2 support, BGE-M3 → Cohere embeddings migration |
| Jan 7, 2026 | HuggingFace provider (4th LLM backend) |
| Jan 12 | Major codebase cleanup, deprecated code removal |
| Jan 30 | **LangGraph agentic scraper** — the biggest change. Pipeline → ReAct agent |
| Feb 5 | Supabase auth system (JWT + API keys + rate limiting) |
| Feb 9 | **API Factory** — browser-less custom API generation via network interception |

---

## Architecture as of February 2026

```
scraper-agent/
├── backend/src/
│   ├── agents/                    # Product 1: Agentic Scraper
│   │   ├── agentic_scraper.py     #   LangGraph ReAct agent
│   │   ├── tools.py               #   14 LangChain @tool functions
│   │   ├── llm_factory.py         #   Multi-provider LLM factory
│   │   ├── prompts.py             #   System prompts
│   │   └── orchestrator.py        #   Legacy non-agentic pipeline
│   │
│   ├── api_factory/               # Product 2: API Factory
│   │   ├── discovery/             #   Network interception + LLM analysis
│   │   ├── execution/             #   httpx recipe execution + auth
│   │   └── storage/               #   Supabase recipe persistence
│   │
│   ├── services/                  # Shared infrastructure
│   │   ├── browser_client.py      #   Playwright singleton
│   │   ├── http_client.py         #   httpx with retries
│   │   ├── html_cleaner.py        #   HTML → markdown
│   │   ├── vector_service_cohere.py  # Cohere + ChromaDB
│   │   └── storage_service.py     #   File-based session storage
│   │
│   ├── auth/                      # Authentication
│   │   ├── dependencies.py        #   FastAPI auth deps
│   │   └── supabase_client.py     #   Supabase admin client
│   │
│   ├── routes/
│   │   ├── v1/agentic.py          #   /api/v1/scrape/agentic
│   │   ├── v1/factory.py          #   /api/v1/factory/*
│   │   ├── scrape.py              #   Legacy /scrape endpoints
│   │   ├── embed.py, query.py     #   RAG endpoints
│   │   └── auth.py, keys.py       #   Auth endpoints
│   │
│   └── main.py                    # FastAPI entry point
│
└── ragnar-frontend/               # SvelteKit frontend (in development)
```

Two products share infrastructure (BrowserClient, LLM factory, Supabase auth) but solve fundamentally different problems:

- **Agentic Scraper**: "I don't know what's on this page. Figure it out." (Exploration)
- **API Factory**: "I know exactly what API to call. Do it fast." (Exploitation)

---

*47 commits. 4 months. From a gym scraper to an AI web intelligence platform.*
