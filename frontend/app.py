"""Gradio frontend for web scraping and Q&A system."""
import asyncio
import os
import time
from datetime import datetime
from typing import Optional, List, Tuple, Generator
import httpx
import gradio as gr
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

custom_css = """
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
    color: #ffffff;
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


async def start_scraping(url: str, progress=gr.Progress()) -> Generator[Tuple[Optional[str], str], None, None]:
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
                    "mode": "whole-site",
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

                    # Update logs
                    new_log = f"[{datetime.now().strftime('%H:%M:%S')}] Status: {status} | Pages scraped: {pages}"
                    logs = [new_log] + logs[:9]  # Keep last 10

                    # Update progress bar
                    progress_val = min(pages / 50.0, 0.99) if pages and pages > 0 else 0.1
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
            formatted = f"{answer}\n\n**Sources:**\n"
            for i, s in enumerate(sources[:3], 1):
                gym_name = s.get('gym_name', 'Unknown')
                page_name = s.get('page_name', 'Unknown')
                score = s.get('score', 0.0)
                formatted += f"{i}. {gym_name} - {page_name} (relevance: {score:.2f})\n"
        else:
            formatted = answer

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": formatted})
        return history

    except httpx.HTTPError as e:
        # Check if it's a "no embeddings" error
        if "404" in str(e) or "not found" in str(e).lower():
            error_msg = "Please enter your gym website url above, and click 'Start Scraping'."
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


# Build Gradio interface
with gr.Blocks(title="Reppin' Assistant") as demo:
    gr.HTML(f"<style>{custom_css}</style>")
    gr.Markdown("# Reppin' Assistant")
    gr.Markdown("Register your gym, or find new ones through our agent")

    # State
    session_id_state = gr.State(None)

    with gr.Row():
        url_input = gr.Textbox(
            label="Enter URL to Scrape",
            placeholder="https://example.com",
            scale=4
        )
        scrape_btn = gr.Button("Start Scraping", variant="primary", scale=1)

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
        height=400
    )

    with gr.Row():
        msg_input = gr.Textbox(
            label="Your Question",
            placeholder="Ask a question about the scraped content...",
            scale=4,
            interactive=True
        )
        send_btn = gr.Button("Send", scale=1, interactive=True)

    clear_btn = gr.Button("Clear Chat")

    # Event Handlers with .then() chaining
    scrape_event = scrape_btn.click(
        fn=start_scraping,
        inputs=[url_input],
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

if __name__ == "__main__":
    demo.queue()
    demo.launch(
        server_port=int(os.getenv("GRADIO_SERVER_PORT", 7860)),
        server_name="0.0.0.0",
        share=False
    )
