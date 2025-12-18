"""Gradio frontend for web scraping and Q&A system - Single Process for HuggingFace Spaces."""
import asyncio
import os
import sys
from datetime import datetime
from typing import Optional, List, Tuple, Generator
from pathlib import Path

import gradio as gr
from dotenv import load_dotenv

# Add backend to path for direct imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Get the directory where this script is located (for asset paths)
SCRIPT_DIR = Path(__file__).parent.resolve()

load_dotenv()

# Import backend services directly (no subprocess)
from backend.src.config import settings
from backend.src.models import ScrapeRequest, ScrapeMode, SessionStatus
from backend.src.services import storage_service, vector_service, session_manager
from backend.src.agents import orchestrator
import anthropic
import ollama

custom_css = """
/* Global theme colors */
.gradio-container {
    background-color: #252523 !important;
    color: #F7F7FA !important;
    padding-left: max(0px, calc((100% - 800px) / 2)) !important;
    padding-right: max(0px, calc((100% - 800px) / 2)) !important;
}
body {
    background-color: #252523 !important;
}

/* ============================================
   GLASSMORPHISM STYLES
   ============================================ */

/* Wavy animated background */
.gradio-container::before {
    content: '';
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: -2;
    background: linear-gradient(135deg, #252523 0%, #1a1a1a 50%, #252523 100%);
}

/* SVG wave animation layer */
.gradio-container::after {
    content: '';
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 250px;
    z-index: -1;
    background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1440 320'%3E%3Cpath fill='%23C6603F' fill-opacity='0.12' d='M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,154.7C960,171,1056,181,1152,165.3C1248,149,1344,107,1392,85.3L1440,64L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z'%3E%3Canimate attributeName='d' dur='10s' repeatCount='indefinite' values='M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,154.7C960,171,1056,181,1152,165.3C1248,149,1344,107,1392,85.3L1440,64L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z;M0,64L48,96C96,128,192,192,288,192C384,192,480,128,576,128C672,128,768,192,864,213.3C960,235,1056,213,1152,181.3C1248,149,1344,107,1392,85.3L1440,64L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z;M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,154.7C960,171,1056,181,1152,165.3C1248,149,1344,107,1392,85.3L1440,64L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z'/%3E%3C/path%3E%3C/svg%3E") no-repeat bottom center;
    background-size: cover;
    opacity: 0.7;
    pointer-events: none;
}

/* Glass log containers */
.log-container {
    max-height: 200px;
    overflow-y: auto;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    /* Glassmorphism */
    background: rgba(26, 26, 26, 0.7) !important;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 12px;
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
}

.log-entry {
    padding: 4px 8px;
    margin: 2px 0;
    animation: fadeIn 0.3s;
    transition: opacity 1s, transform 0.3s;
    color: #F7F7FA;
}
.log-entry.old {
    color: #888888;
    opacity: 0.7;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(-5px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Animated gradient border on focus */
@keyframes borderGlow {
    0%, 100% { border-color: rgba(198, 96, 63, 0.3); }
    50% { border-color: rgba(198, 96, 63, 0.6); }
}

.log-container:focus-within {
    animation: borderGlow 2s ease-in-out infinite;
}

.status-box {
    padding: 12px;
    border-radius: 6px;
    margin: 8px 0;
}
.status-pending { background: #fff3cd; color: #856404; }
.status-in_progress { background: #cfe2ff; color: #084298; }
.status-completed { background: #d1e7dd; color: #0f5132; }
.status-failed { background: #f8d7da; color: #842029; }

/* Override Gradio default text colors */
.gr-markdown, .gr-textbox label, .gr-button, h1, h2, h3, p {
    color: #F7F7FA !important;
}
/* User text color in chatbot */
.message.user, .user, [data-testid="user"], .message-wrap.user {
    color: #61A6FB !important;
}

/* Glass buttons */
button.primary, .primary {
    background: linear-gradient(135deg, rgba(198, 96, 63, 0.9), rgba(177, 78, 49, 0.9)) !important;
    backdrop-filter: blur(5px);
    -webkit-backdrop-filter: blur(5px);
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 15px rgba(198, 96, 63, 0.3);
    color: #FFFFFF !important;
    transition: all 0.3s ease;
}
button.primary:hover, .primary:hover {
    background: linear-gradient(135deg, rgba(177, 78, 49, 1), rgba(156, 62, 35, 1)) !important;
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(198, 96, 63, 0.4);
}

/* Glass form containers */
.form {
    background: rgba(38, 38, 36, 0.6) !important;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 16px;
}

/* Glass block containers */
.block,
.block.url-input-box {
    background: rgba(38, 38, 36, 0.5) !important;
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px;
}

/* Glass panels/groups */
.gr-group, .gr-box {
    background: rgba(38, 38, 36, 0.6) !important;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 16px;
    padding: 16px;
}

/* Glass inputs */
.url-input-box textarea,
.url-input-box input,
.block.url-input-box textarea,
.block.url-input-box input,
.question-input textarea,
.question-input input,
.block.question-input textarea,
.block.question-input input {
    background: rgba(31, 30, 29, 0.8) !important;
    backdrop-filter: blur(5px);
    -webkit-backdrop-filter: blur(5px);
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
}

/* All textbox inputs */
.gradio-container textarea,
.gradio-container input[type="text"] {
    background: rgba(31, 30, 29, 0.8) !important;
    backdrop-filter: blur(5px);
    -webkit-backdrop-filter: blur(5px);
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 20px !important;
    transition: all 0.3s ease;
}

.gradio-container textarea:focus,
.gradio-container input[type="text"]:focus {
    border-color: rgba(198, 96, 63, 0.6) !important;
    box-shadow: 0 0 15px rgba(198, 96, 63, 0.15);
}

/* Question input container */
.block.question-input {
    background: rgba(38, 38, 36, 0.5) !important;
}

/* Glass example buttons */
.example,
.example-content {
    background: rgba(31, 30, 29, 0.7) !important;
    backdrop-filter: blur(5px);
    -webkit-backdrop-filter: blur(5px);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 8px;
}

/* Glass chatbot container */
.chatbot {
    background: rgba(26, 26, 26, 0.5) !important;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
}

/* Subtle glow on section headers */
.gr-markdown h3 {
    text-shadow: 0 0 20px rgba(198, 96, 63, 0.3);
}

/* ============================================
   BROWSER COMPATIBILITY FALLBACKS
   ============================================ */
@supports not (backdrop-filter: blur(10px)) {
    .log-container {
        background: rgba(26, 26, 26, 0.95) !important;
    }
    .form, .block, .gr-group, .gr-box {
        background: rgba(38, 38, 36, 0.95) !important;
    }
    .gradio-container textarea,
    .gradio-container input[type="text"] {
        background: rgba(31, 30, 29, 0.95) !important;
    }
}
"""


def format_logs(logs_list: List[str]) -> str:
    """Generate HTML for animated log display."""
    if not logs_list:
        return '<div class="log-container"><div class="log-entry">Ready...</div></div>'

    html = '<div class="log-container">'
    # Take first 3 logs (newest are at index 0)
    for idx, log in enumerate(logs_list[:3]):
        # First log (index 0) is newest - white text
        # Logs at index 1, 2 are older - grey text
        css_class = "log-entry" if idx == 0 else "log-entry old"
        html += f'<div class="{css_class}">{log}</div>'
    html += '</div>'
    return html


async def start_scraping(url: str, mode: str, progress=gr.Progress()) -> Generator[Tuple[Optional[str], str], None, None]:
    """Execute scraping directly using orchestrator (no HTTP calls)."""
    if not url or not url.strip():
        yield None, format_logs(["Error: URL is required"])
        return

    logs = []
    session_id = None

    try:
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Starting scrape of {url}")
        yield None, format_logs(logs)

        # Create scrape request
        scrape_mode = ScrapeMode.SINGLE_PAGE if mode == "single-page" else ScrapeMode.WHOLE_SITE
        request = ScrapeRequest(
            url=url,
            mode=scrape_mode,
            purpose="Web scraping for Q&A"
        )

        # Generate session ID and create directory
        session_id = storage_service.generate_session_id()
        storage_service.create_session_directory(session_id)

        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Session created: {session_id}")
        yield session_id, format_logs(logs)

        # Progress callback for real-time updates
        def progress_callback(event_type: str, data: dict):
            nonlocal logs
            timestamp = datetime.now().strftime('%H:%M:%S')

            if event_type == "discovering_urls":
                msg = f"[{timestamp}] Discovering URLs from {data.get('url', '')}"
            elif event_type == "scraping_page":
                msg = f"[{timestamp}] Scraping: {data.get('progress', '')} - {data.get('url', '')[:50]}..."
            elif event_type == "page_scraped":
                msg = f"[{timestamp}] Scraped page ({data.get('html_length', 0)} chars)"
            elif event_type == "converting_to_markdown":
                msg = f"[{timestamp}] Converting {data.get('total_pages', 0)} pages to markdown"
            elif event_type == "page_converted":
                msg = f"[{timestamp}] Converted: {data.get('page_name', '')}"
            elif event_type == "saving_session":
                msg = f"[{timestamp}] Saving session data..."
            elif event_type == "completed":
                msg = f"[{timestamp}] Scraping completed!"
            elif event_type == "error":
                msg = f"[{timestamp}] Error: {data.get('message', 'Unknown error')}"
            else:
                msg = f"[{timestamp}] {event_type}: {data}"

            logs = [msg] + logs[:9]

        # Execute scraping directly
        result_session_id, success = await orchestrator.execute_scrape(
            request=request,
            session_id=session_id,
            progress_callback=progress_callback
        )

        if success:
            logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] Scraping complete!")
            progress(1.0, desc="Scraping complete")
            yield session_id, format_logs(logs)
        else:
            logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] Scraping failed")
            yield None, format_logs(logs)

    except Exception as e:
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {str(e)}")
        yield None, format_logs(logs)


async def start_embedding(session_id: Optional[str]) -> Generator[str, None, None]:
    """Execute embedding directly using vector service (no HTTP calls)."""
    if not session_id:
        yield format_logs(["No session to embed"])
        return

    logs = []
    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Starting embedding process...")
    yield format_logs(logs)

    # Wait a moment for files to be written
    await asyncio.sleep(1)

    try:
        # Find markdown file for this session
        files = storage_service.list_raw_html_files()
        matching_files = [f for f in files if session_id in f]

        if not matching_files:
            logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] No markdown file found for session")
            yield format_logs(logs)
            return

        filename = matching_files[0]
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Found file: {filename}")
        yield format_logs(logs)

        # Load the data
        data = storage_service.load_raw_html(filename)
        if not data:
            logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] Failed to load file")
            yield format_logs(logs)
            return

        domain = data.get("website", "unknown")
        site_name = data.get("site_name", "Unknown Site")
        pages = data.get("pages", [])

        if not pages:
            logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] No pages found")
            yield format_logs(logs)
            return

        # Initialize Cohere API
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Connecting to Cohere API...")
        yield format_logs(logs)

        vector_service.load_model()
        vector_service.create_collection()

        logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] Connected to Cohere, processing {len(pages)} pages...")
        yield format_logs(logs)

        # Process pages
        total_chunks = 0
        pages_processed = 0

        for page_idx, page in enumerate(pages):
            page_name = page.get("page_name", "Unknown Page")
            page_url = page.get("page_url", "")
            markdown_content = page.get("markdown_content", "")

            if not markdown_content:
                continue

            # Chunk and embed
            chunks = vector_service.chunk_markdown(markdown_content, page_name)
            if not chunks:
                continue

            vector_service.insert_chunks(
                domain=domain,
                site_name=site_name,
                page_name=page_name,
                page_url=page_url,
                chunks=chunks,
            )

            total_chunks += len(chunks)
            pages_processed += 1

            logs = [f"[{datetime.now().strftime('%H:%M:%S')}] Embedded: {page_name} ({len(chunks)} chunks)"] + logs[:9]
            yield format_logs(logs)

        logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] Embedding complete! {pages_processed} pages, {total_chunks} chunks")
        yield format_logs(logs)

    except Exception as e:
        logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] Error: {str(e)}")
        yield format_logs(logs)


def extract_thinking_response(content: str) -> str:
    """Extract actual response from thinking model output.

    Thinking models like Kimi K2 output in format:
    <think>reasoning here</think>
    actual answer here

    This function strips the thinking tags and returns just the answer.
    """
    import re

    if not content:
        return ""

    # Remove <think>...</think> blocks (including multiline)
    cleaned = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)

    # Also try removing <thinking>...</thinking> variant
    cleaned = re.sub(r'<thinking>.*?</thinking>', '', cleaned, flags=re.DOTALL)

    return cleaned.strip()


async def chat_fn(message: str, history, llm_provider: str = "claude"):
    """Query using direct vector search and LLM (Claude or Ollama)."""
    if not message or not message.strip():
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": "Please enter a question."})
        return history

    try:
        query_rewrite_prompt = f"""Given this user question about websites, rewrite it as an optimized search query.

User Question: {message}

Instructions:
- Extract key concepts and keywords
- Add relevant synonyms and related terms
- Keep it concise (2-10 words)
- Focus on terms likely to appear in website content
- Do not add quotes or special characters

Return ONLY the optimized search query, nothing else."""

        # Stage 1: Query Rewriting
        if llm_provider == "ollama":
            # Use Ollama (Kimi K2) for query rewriting
            ollama_model = settings.ollama_model
            ollama_host = settings.ollama_host
            print(f"[CHAT] Stage 1: Calling Ollama {ollama_model} at {ollama_host} for query rewriting...")
            try:
                # Initialize Ollama client
                if ollama_host == "https://ollama.com":
                    ollama_client = ollama.Client(
                        host=ollama_host,
                        headers={"Authorization": f"Bearer {settings.ollama_api_key}"}
                    )
                else:
                    ollama_client = ollama.Client(host=ollama_host)

                # System message to encourage direct output (discourage thinking)
                system_msg = "You are a search query optimizer. Output ONLY the optimized query, nothing else. No explanations, no thinking, just the query."

                response = ollama_client.chat(
                    model=ollama_model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": query_rewrite_prompt}
                    ],
                    options={"num_predict": 500}
                )

                raw_content = response.message.content
                print(f"[CHAT] Stage 1 raw response: '{raw_content[:500] if raw_content else 'EMPTY'}'")

                # Extract answer from thinking model (strips <think> tags)
                optimized_query = extract_thinking_response(raw_content)

                # Fallback to original query if empty or just "..."
                if not optimized_query or optimized_query == "...":
                    print(f"[CHAT] Stage 1 WARNING: Empty/invalid response, using original query")
                    optimized_query = message

                print(f"[CHAT] Stage 1 complete: Query rewritten to '{optimized_query}'")
            except Exception as e:
                print(f"[CHAT] Stage 1 FAILED (Ollama {ollama_model}): {e}")
                raise
        else:
            # Use Claude Haiku for query rewriting
            print("[CHAT] Stage 1: Calling Claude Haiku for query rewriting...")
            try:
                client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                query_message = client.messages.create(
                    model="claude-3-5-haiku-20241022",
                    max_tokens=100,
                    messages=[{"role": "user", "content": query_rewrite_prompt}]
                )
                optimized_query = query_message.content[0].text.strip()
                print(f"[CHAT] Stage 1 complete: Query rewritten to '{optimized_query}'")
            except Exception as e:
                print(f"[CHAT] Stage 1 FAILED (Claude Haiku): {e}")
                raise

        # Stage 2: Vector Search + Reranking (Cohere embed + rerank) - same for both providers
        print("[CHAT] Stage 2: Calling Cohere embed-v4.0 + rerank-v4.0-fast...")
        try:
            results = vector_service.search(
                query=optimized_query,
                top_k=30,         # Retrieve more candidates
                rerank_top_n=10   # Rerank to top 10
            )
            print(f"[CHAT] Stage 2 complete: Retrieved {len(results)} results")
        except Exception as e:
            print(f"[CHAT] Stage 2 FAILED (Cohere): {e}")
            raise

        if not results:
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": "I don't have any information about that. Please scrape a website first, then ask questions about its content."})
            return history

        # Build context from results
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"[Source {i} - {result['site_name']} - {result['page_name']}]\n"
                f"{result['chunk_text']}\n"
            )

        context = "\n---\n".join(context_parts)

        system_prompt = """You are a helpful assistant answering questions about websites.

You will be provided with relevant information extracted from websites. Use this information to answer the user's question accurately and naturally.

Guidelines:
- Provide a clear, concise answer based ONLY on the information given
- If multiple sites are mentioned, organize the information clearly
- Include specific details like addresses, prices, class types, hours when available
- If the provided information doesn't fully answer the question, acknowledge what you can answer
- Be conversational and helpful
- Cite site names when providing specific information
- Don't make up information not present in the sources"""

        user_prompt = f"""Based on the following information from websites, please answer this question:

Question: {message}

Relevant Information from Websites:
{context}

Please provide a natural, helpful answer based on this information."""

        # Stage 3: Answer Synthesis
        if llm_provider == "ollama":
            # Use Ollama (Kimi K2) for answer synthesis
            ollama_model = settings.ollama_model
            ollama_host = settings.ollama_host
            print(f"[CHAT] Stage 3: Calling Ollama {ollama_model} for answer synthesis...")
            try:
                # Initialize Ollama client (reuse if possible)
                if ollama_host == "https://ollama.com":
                    ollama_client = ollama.Client(
                        host=ollama_host,
                        headers={"Authorization": f"Bearer {settings.ollama_api_key}"}
                    )
                else:
                    ollama_client = ollama.Client(host=ollama_host)

                response = ollama_client.chat(
                    model=ollama_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    options={"num_predict": 4096}  # More tokens for thinking + answer
                )
                raw_answer = response.message.content
                print(f"[CHAT] Stage 3 raw response length: {len(raw_answer)} chars")

                # Extract answer from thinking model (strips <think> tags)
                answer = extract_thinking_response(raw_answer)

                if not answer:
                    answer = "I was unable to generate a response. Please try again."

                print("[CHAT] Stage 3 complete: Answer generated")
            except Exception as e:
                print(f"[CHAT] Stage 3 FAILED (Ollama {ollama_model}): {e}")
                raise
        else:
            # Use Claude Sonnet for answer synthesis
            print("[CHAT] Stage 3: Calling Claude Sonnet for answer synthesis...")
            try:
                client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                answer_message = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                answer = answer_message.content[0].text
                print("[CHAT] Stage 3 complete: Answer generated")
            except Exception as e:
                print(f"[CHAT] Stage 3 FAILED (Claude Sonnet): {e}")
                raise

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": answer})
        return history

    except Exception as e:
        error_str = str(e)
        if "no embeddings" in error_str.lower() or "not found" in error_str.lower():
            error_msg = "Please enter a website URL above and click 'Start Scraping'."
        else:
            error_msg = f"Error querying the system: {error_str}"

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": error_msg})
        return history


def enable_chat() -> Tuple:
    """Enable chat interface after embedding is complete."""
    return (
        gr.update(interactive=True, placeholder="Ask a question about the scraped content..."),
        gr.update(interactive=True)
    )


def handle_feedback(data: gr.LikeData):
    """Handle user feedback on chatbot responses."""
    feedback_type = "liked" if data.liked else "disliked"
    message_index = data.index
    message_value = data.value
    print(f"[FEEDBACK] User {feedback_type} message at index {message_index}")
    print(f"[FEEDBACK] Message content: {message_value}")


async def handle_example_click(evt: gr.SelectData, history, llm_provider: str = "claude"):
    """Handle when user clicks an example question."""
    example_text = evt.value.get("text", "")
    return await chat_fn(example_text, history, llm_provider)


# Build Gradio interface
with gr.Blocks(title="Agentic Scraper") as demo:
    gr.HTML(f"<style>{custom_css}</style>")

    gr.HTML("<h1>Agentic <span style='color: #C6603F;'>Scraper</span></h1>")
    gr.Markdown("Scrape any website and ask questions powered by Claude/Ollama AI and Cohere embeddings")

    # State
    session_id_state = gr.State(None)

    with gr.Row():
        url_input = gr.Textbox(
            label="Enter URL to Scrape",
            placeholder="https://example.com",
            scale=6,
            elem_classes="url-input-box"
        )
        scrape_btn = gr.Button("Start Scraping", variant="primary", scale=1)

    # Mode selection radio
    mode_radio = gr.Radio(
        choices=["single-page", "whole-site"],
        value="whole-site",
        label="Scrape Mode",
        show_label=True,
        scale=1,
        info="Single-page: scrape only this URL | Whole-site: crawl entire website",
        elem_classes="mode-radio"
    )

    # LLM Provider selection
    llm_provider_radio = gr.Radio(
        choices=["claude", "ollama"],
        value="claude",
        label="LLM Provider",
        show_label=True,
        scale=1,
        info="Claude: Haiku + Sonnet | Ollama: Kimi K2 (local or cloud)",
        elem_classes="llm-provider-radio"
    )

    # Progress Section
    with gr.Group():
        gr.Markdown("### Scraping Progress")
        scrape_logs = gr.HTML(value=format_logs([]), label="Logs")

    with gr.Group():
        gr.Markdown("### Embedding Progress")
        embed_logs = gr.HTML(value=format_logs([]), label="Logs")

    gr.Markdown("---")

    # Chatbot Section
    gr.Markdown("### Ask Questions")
    chatbot = gr.Chatbot(
        label="Q&A Assistant",
        height=400,
        avatar_images=(str(SCRIPT_DIR / "assets/user-avatar-dark.png"), str(SCRIPT_DIR / "assets/bot-avatar-dark.png")),
        feedback_options=["Like", "Dislike"],
        examples=[
            {"text": "What is this website about?"},
            {"text": "Summarize the main services offered"},
            {"text": "What are the pricing options?"},
            {"text": "How can I contact support?"},
            {"text": "What are the business hours?"},
            {"text": "Are there any special offers or promotions?"},
            {"text": "What payment methods are accepted?"},
            {"text": "What is the return or refund policy?"}
        ]
    )

    with gr.Row(elem_classes="question-row"):
        msg_input = gr.Textbox(
            label="Your Question",
            placeholder="Ask a question about the scraped content...",
            scale=4,
            interactive=True,
            elem_classes="question-input"
        )
        send_btn = gr.Button("Send", scale=1, interactive=True)

    clear_btn = gr.Button("Clear Chat")

    # Event Handlers with .then() chaining
    scrape_event = scrape_btn.click(
        fn=start_scraping,
        inputs=[url_input, mode_radio],
        outputs=[session_id_state, scrape_logs]
    ).then(
        fn=start_embedding,
        inputs=[session_id_state],
        outputs=[embed_logs]
    ).then(
        fn=enable_chat,
        outputs=[msg_input, send_btn]
    )

    # Enter key on URL input triggers scraping (same as clicking the button)
    url_input.submit(
        fn=start_scraping,
        inputs=[url_input, mode_radio],
        outputs=[session_id_state, scrape_logs]
    ).then(
        fn=start_embedding,
        inputs=[session_id_state],
        outputs=[embed_logs]
    ).then(
        fn=enable_chat,
        outputs=[msg_input, send_btn]
    )

    # Chat handlers
    msg_submit = msg_input.submit(
        fn=chat_fn,
        inputs=[msg_input, chatbot, llm_provider_radio],
        outputs=[chatbot]
    ).then(
        fn=lambda: "",
        outputs=[msg_input]
    )

    send_click = send_btn.click(
        fn=chat_fn,
        inputs=[msg_input, chatbot, llm_provider_radio],
        outputs=[chatbot]
    ).then(
        fn=lambda: "",
        outputs=[msg_input]
    )

    clear_btn.click(fn=lambda: None, outputs=[chatbot])

    # Feedback handler
    chatbot.like(fn=handle_feedback, inputs=None, outputs=None)

    # Example select handler
    chatbot.example_select(
        fn=handle_example_click,
        inputs=[chatbot, llm_provider_radio],
        outputs=[chatbot]
    )


def validate_environment():
    """Check required environment variables before starting."""
    # Check Anthropic API key (required for Claude provider)
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key and anthropic_key.strip():
        print(f"[STARTUP] ANTHROPIC_API_KEY is set: {anthropic_key[:15]}...")
    else:
        print("[STARTUP] ANTHROPIC_API_KEY not set (Claude provider will not work)")

    # Check Cohere API key (required for embeddings)
    cohere_key = os.getenv("COHERE_API_KEY")
    if not cohere_key or not cohere_key.strip():
        print("[ERROR] COHERE_API_KEY environment variable must be set")
        print("[ERROR] Add it in your Space's Settings > Repository secrets")
        sys.exit(1)
    print(f"[STARTUP] COHERE_API_KEY is set: {cohere_key[:15]}...")

    # Check Ollama configuration (optional, for Ollama provider)
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ollama_api_key = os.getenv("OLLAMA_API_KEY", "")
    print(f"[STARTUP] OLLAMA_HOST: {ollama_host}")
    if ollama_api_key:
        print(f"[STARTUP] OLLAMA_API_KEY is set: {ollama_api_key[:15]}...")
    else:
        print("[STARTUP] OLLAMA_API_KEY not set (required for Ollama Cloud)")

    # Ensure at least one LLM provider is available
    if not (anthropic_key and anthropic_key.strip()) and not ollama_host:
        print("[ERROR] At least one LLM provider must be configured")
        print("[ERROR] Set ANTHROPIC_API_KEY for Claude or OLLAMA_HOST for Ollama")
        sys.exit(1)


def setup_directories():
    """Create necessary directories for data persistence."""
    is_hf_spaces = os.getenv("SPACE_ID") is not None

    if is_hf_spaces:
        directories = ["/tmp/chroma_db", "/tmp/data"]
    else:
        directories = ["./chroma_db", "./data"]

    for directory in directories:
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
            print(f"[STARTUP] Created directory: {directory}")
        except Exception as e:
            print(f"[WARNING] Failed to create directory {directory}: {e}")


if __name__ == "__main__":
    # Validate environment before starting
    validate_environment()

    # Create necessary directories
    setup_directories()

    # Start Gradio frontend (no subprocess needed!)
    print("[STARTUP] Starting single-process Gradio app...")
    demo.queue()
    demo.launch(
        server_port=int(os.getenv("GRADIO_SERVER_PORT", 7860)),
        server_name="0.0.0.0",
        share=False
    )
