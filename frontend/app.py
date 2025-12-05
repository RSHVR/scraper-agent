"""Gradio frontend for web scraping and Q&A system."""
import asyncio
import os
import time
from datetime import datetime
from typing import Optional, List, Tuple, Generator
import subprocess
import sys
import atexit
from pathlib import Path
import httpx
import gradio as gr
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_BASE_URL", "http://localhost:8080")

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

/* DEPRECATED: Removed logo styling */
.log-container {
    max-height: 200px;
    overflow-y: auto;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    background: #1a1a1a;
    padding: 12px;
    border-radius: 6px;
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
/* Primary button styling */
button.primary, .primary {
    background-color: #C6603F !important;
    border-color: #C6603F !important;
    color: #FFFFFF !important;
}
button.primary:hover, .primary:hover {
    background-color: #b14e31 !important;
    border-color: #b14e31 !important;
    color: #FFFFFF !important;
}
/* Form containers (URL input and question input rows) */
.form {
    background-color: #262624 !important;
    background: #262624 !important;
}
/* Block containers */
.block,
.block.url-input-box {
    background-color: #262624 !important;
    background: #262624 !important;
    border: 0;
}

/* URL input textbox background */
.url-input-box textarea,
.url-input-box input,
.block.url-input-box textarea,
.block.url-input-box input {
    background-color: #1F1E1D !important;
}
/* Query input textbox background */
.question-input textarea,
.question-input input,
.block.question-input textarea,
.block.question-input input {
    background-color: #1F1E1D !important;
}
/* All textbox inputs */
.gradio-container textarea,
.gradio-container input[type="text"] {
    background-color: #1F1E1D !important;
    border-radius: 20px !important;
}
/* Question input container */
.block.question-input {
    background-color: #262624 !important;
}
/* Example buttons background */
.example,
.example-content {
    background-color: #1F1E1D !important;
    background: #1F1E1D !important;
}
"""


def start_backend_server():
    """Start the FastAPI backend as a subprocess."""
    backend_dir = Path(__file__).parent.parent / "backend"

    # Check if running in HuggingFace Spaces
    is_hf_spaces = os.getenv("SPACE_ID") is not None
    if is_hf_spaces:
        backend_dir = Path("/app/backend")

    if not backend_dir.exists():
        print(f"[ERROR] Backend directory not found: {backend_dir}")
        return None

    cmd = [
        sys.executable, "-m", "uvicorn",
        "src.main:app",
        "--host", "0.0.0.0",
        "--port", "8080",
        "--log-level", "info"
    ]

    print(f"[STARTUP] Starting backend server in {backend_dir}")
    print(f"[STARTUP] Command: {' '.join(cmd)}")

    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(backend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        print(f"[STARTUP] Backend server started with PID: {process.pid}")

        # Give process a moment to fail if there are immediate errors
        time.sleep(1)
        if process.poll() is not None:
            # Process already exited
            print(f"[ERROR] Backend process exited immediately with code: {process.returncode}")
            # Try to read any error output
            try:
                output = process.stdout.read()
                if output:
                    print(f"[ERROR] Backend output:\n{output}")
            except:
                pass
            return None

        return process
    except Exception as e:
        print(f"[STARTUP] Failed to start backend: {e}")
        import traceback
        traceback.print_exc()
        return None


def wait_for_backend_ready(timeout=300):
    """Wait for backend to be ready by polling health endpoint.

    Args:
        timeout: Maximum time to wait in seconds (default 300s / 5 minutes).
                 Increased from 120s to allow for BGE-M3 model download on first run.
    """
    print("[STARTUP] Waiting for backend to be ready...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{API_URL}/health")
                if response.status_code == 200:
                    print("[STARTUP] ✓ Backend is ready!")
                    return True
        except Exception:
            pass

        print(".", end="", flush=True)
        time.sleep(2)

    print("\n[STARTUP] ✗ Backend failed to start within timeout")
    return False


def cleanup_backend(backend_process):
    """Cleanup backend process on exit."""
    if backend_process and backend_process.poll() is None:
        print("[SHUTDOWN] Stopping backend server...")
        backend_process.terminate()
        try:
            backend_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            backend_process.kill()
        print("[SHUTDOWN] Backend stopped")


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
    """Poll scraping session for progress updates."""
    if not url or not url.strip():
        yield None, format_logs(["Error: URL is required"])
        return

    logs = []
    session_id = None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Starting scrape of {url}")
            yield None, format_logs(logs)

            # Start scrape
            response = await client.post(
                f"{API_URL}/api/scrape",
                json={
                    "url": url,
                    "mode": mode,
                    "purpose": "Web scraping for Q&A"
                }
            )
            response.raise_for_status()
            data = response.json()
            session_id = data.get("session_id")

            if not session_id:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Error: No session ID received")
                yield None, format_logs(logs)
                return

            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Session created: {session_id}")
            yield session_id, format_logs(logs)

            # Poll for progress
            max_attempts = 600  # 10 minutes max
            attempt = 0

            while attempt < max_attempts:
                try:
                    resp = await client.get(f"{API_URL}/api/sessions/{session_id}")
                    resp.raise_for_status()
                    session_data = resp.json()

                    status = session_data.get("status", "unknown")
                    pages = session_data.get("pages_scraped") or 0
                    total = session_data.get("total_pages")

                    # Update logs with progress
                    if total:
                        new_log = f"[{datetime.now().strftime('%H:%M:%S')}] Status: {status} | Pages: {pages}/{total}"
                    else:
                        new_log = f"[{datetime.now().strftime('%H:%M:%S')}] Status: {status} | Pages scraped: {pages}"

                    logs = [new_log] + logs[:9]  # Keep last 10

                    # Update progress bar (use real ratio if total available)
                    if total and total > 0:
                        progress_val = min(pages / float(total), 0.99)
                        progress(progress_val, desc=f"Scraping: {pages}/{total} pages")
                    else:
                        progress_val = 0.1 if pages == 0 else min(pages / 50.0, 0.99)
                        progress(progress_val, desc=f"Scraping: {status}")

                    if status == "completed":
                        logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] Scraping complete!")
                        progress(1.0, desc="Scraping complete")
                        yield session_id, format_logs(logs)
                        break
                    elif status == "failed":
                        error_msg = session_data.get("error_message", "Unknown error")
                        logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] Error: {error_msg}")
                        yield None, format_logs(logs)
                        break

                    yield session_id, format_logs(logs)

                except httpx.HTTPError as e:
                    logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] HTTP error: {str(e)}")
                    yield session_id, format_logs(logs)

                await asyncio.sleep(1)
                attempt += 1

            if attempt >= max_attempts:
                logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] Timeout: Scraping took too long")
                yield session_id, format_logs(logs)

    except httpx.HTTPError as e:
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {str(e)}")
        yield None, format_logs(logs)
    except Exception as e:
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Unexpected error: {str(e)}")
        yield None, format_logs(logs)


async def start_embedding(session_id: Optional[str]) -> Generator[str, None, None]:
    """Call embedding API endpoint."""
    if not session_id:
        yield format_logs(["No session to embed"])
        return

    logs = []
    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Starting embedding process...")
    yield format_logs(logs)

    # Wait a moment for file to be written
    await asyncio.sleep(2)

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minute timeout for embedding
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Calling embedding API...")
            yield format_logs(logs)

            # Call the embedding API (now synchronous - waits for completion)
            response = await client.post(
                f"{API_URL}/api/embed/",
                json={"session_id": session_id}
            )
            response.raise_for_status()
            data = response.json()

            # Show results
            status = data.get("status", "unknown")
            message = data.get("message", "")
            total_chunks = data.get("total_chunks", 0)
            total_pages = data.get("total_pages", 0)

            logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] Status: {status}")
            logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
            logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] Processed {total_pages} pages, {total_chunks} chunks")

            if status == "completed":
                logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] Embedding complete!")
            else:
                logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] Embedding failed or incomplete")

            yield format_logs(logs)

    except httpx.HTTPError as e:
        logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] HTTP error: {str(e)}")
        yield format_logs(logs)
    except Exception as e:
        logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] Error: {str(e)}")
        yield format_logs(logs)


async def chat_fn(message: str, history):
    """Query the RAG endpoint."""
    if not message or not message.strip():
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": "Please enter a question."})
        return history

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Build conversation history for the API (exclude current message)
            conversation_history = history if history else []

            response = await client.post(
                f"{API_URL}/api/query/ask",
                json={
                    "question": message,
                    "conversation_history": conversation_history,
                    "top_k": 10
                }
            )
            response.raise_for_status()
            data = response.json()

        answer = data.get("answer", "No answer available")
        sources = data.get("sources", [])

        # Format with sources
        if sources:
            formatted = answer
            # formatted = f"{answer}\n\n**Sources:**\n"
            # for i, s in enumerate(sources[:3], 1):
            #     gym_name = s.get('gym_name', 'Unknown')
            #     page_name = s.get('page_name', 'Unknown')
            #     score = s.get('score', 0.0)
            #     formatted += f"{i}. {gym_name} - {page_name} (relevance: {score:.2f})\n"
        else:
            formatted = answer

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": formatted})
        return history

    except httpx.HTTPError as e:
        # Check if it's a "no embeddings" error
        if "404" in str(e) or "not found" in str(e).lower():
            error_msg = "Please enter a website URL above and click 'Start Scraping'."  # DEPRECATED: was "Please enter your gym website url above..."
        else:
            error_msg = f"Error querying the system: {str(e)}"

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": error_msg})
        return history
    except Exception as e:
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": f"Unexpected error: {str(e)}"})
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


async def handle_example_click(evt: gr.SelectData, history):
    """Handle when user clicks an example question."""
    # Extract the example text from the SelectData
    example_text = evt.value.get("text", "")
    # Call the chat function with the example text
    return await chat_fn(example_text, history)


# Build Gradio interface
with gr.Blocks(title="Agentic Scraper") as demo:  # DEPRECATED: was "Reppin' Assistant"
    gr.HTML(f"<style>{custom_css}</style>")

    # DEPRECATED: Removed Reppin' logo section
    gr.HTML("<h1>Agentic <span style='color: #C6603F;'>Scraper</span></h1>")  # DEPRECATED: was "Reppin' <span...>Assistant</span>"
    gr.Markdown("Scrape any website and ask questions powered by Claude AI, Milvus vector database, Playwright, and HTTPX")  # DEPRECATED: was "Register your gym, or find new ones through our agent"

    # State
    session_id_state = gr.State(None)

    with gr.Row():
        url_input = gr.Textbox(
            label="Enter URL to Scrape",
            placeholder="https://example.com",
            scale=4,
            elem_classes="url-input-box"
        )
        scrape_btn = gr.Button("Start Scraping", variant="primary", scale=1)

    # Mode selection radio
    mode_radio = gr.Radio(
        choices=["single-page", "whole-site"],
        value="whole-site",
        label="Scraping Mode",
        info="Single-page: scrape only this URL | Whole-site: crawl entire website",
        elem_classes="mode-radio"
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
        avatar_images=("assets/user-avatar-dark.png", "assets/bot-avatar-dark.png"),
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
        ]  # DEPRECATED: was gym-specific examples
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

    # Chat handlers
    msg_submit = msg_input.submit(
        fn=chat_fn,
        inputs=[msg_input, chatbot],
        outputs=[chatbot]
    ).then(
        fn=lambda: "",
        outputs=[msg_input]
    )

    send_click = send_btn.click(
        fn=chat_fn,
        inputs=[msg_input, chatbot],
        outputs=[chatbot]
    ).then(
        fn=lambda: "",
        outputs=[msg_input]
    )

    clear_btn.click(fn=lambda: None, outputs=[chatbot])

    # Feedback handler
    chatbot.like(fn=handle_feedback, inputs=None, outputs=None)

    # Example select handler - when user clicks an example, submit it to chat
    chatbot.example_select(
        fn=handle_example_click,
        inputs=[chatbot],
        outputs=[chatbot]
    )


def validate_environment():
    """Check required environment variables before starting."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or not api_key.strip():
        print("[ERROR] ANTHROPIC_API_KEY environment variable must be set")
        print("[ERROR] Add it in your Space's Settings > Repository secrets")
        sys.exit(1)
    print(f"[STARTUP] ANTHROPIC_API_KEY is set: {api_key[:15]}...")


def setup_directories():
    """Create necessary directories for data persistence."""
    is_hf_spaces = os.getenv("SPACE_ID") is not None

    if is_hf_spaces:
        # Use /tmp for HuggingFace Spaces (only writable directory)
        directories = ["/tmp/chroma_db", "/tmp/data"]
    else:
        # Local development
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
    # Start backend server
    backend_process = start_backend_server()

    if backend_process:
        # Register cleanup handler
        atexit.register(cleanup_backend, backend_process)

        # Wait for backend to be ready
        if not wait_for_backend_ready():
            print("[ERROR] Backend failed to start, exiting...")
            sys.exit(1)
    else:
        print("[WARNING] Backend server not started, assuming external backend")

    # Start Gradio frontend
    demo.queue()
    demo.launch(
        server_port=int(os.getenv("GRADIO_SERVER_PORT", 7860)),
        server_name="0.0.0.0",
        share=False
    )
