# Scraper Agent - Frontend

Gradio-based web interface for the Scraper Agent with automatic scraping, embedding, and Q&A capabilities.

## Features

- **URL Submission**: Simple textbox interface to submit URLs for scraping
- **Automatic Workflow**: Scraping automatically triggers embedding without manual intervention
- **Real-time Progress**: Visual loading bars and animated logs for both scraping and embedding
- **Minimalistic Log Display**: Terminal-style logs with fade-out effects
- **AI-Powered Q&A**: Chat interface for querying scraped content using RAG
- **No Admin Access**: User-friendly interface without delete or admin functionality

## Prerequisites

- Python 3.11 or higher
- Backend server running on http://localhost:8000 (or configured API endpoint)
- Backend virtual environment with all dependencies installed

## Installation

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Create a virtual environment (optional but recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file:
```bash
cp .env.example .env
```

5. Edit `.env` to configure settings (optional):
```bash
API_BASE_URL=http://localhost:8000
GRADIO_SERVER_PORT=7860
BACKEND_PATH=../backend
```

## Running the Frontend

### Make sure the backend is running first

From the backend directory:
```bash
cd ../backend
source venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Start the frontend

From the frontend directory:
```bash
cd frontend
python app.py
```

The Gradio interface will be available at:
- Local: http://localhost:7860
- Network: http://0.0.0.0:7860

## Usage

### 1. Scrape a Website

1. Enter a URL in the text input field (e.g., `https://example.com`)
2. Click "Start Scraping"
3. Watch the real-time progress in the scraping logs
4. Progress will show:
   - Session ID
   - Current status
   - Number of pages scraped
   - Animated terminal logs

### 2. Automatic Embedding

- Once scraping completes, embedding automatically starts
- The embedding process:
  - Finds the latest cleaned markdown file
  - Processes pages and chunks
  - Generates BGE-M3 embeddings
  - Stores vectors in Milvus database
- Progress shown in real-time with embedding logs

### 3. Ask Questions

- After embedding completes, the chat interface is automatically enabled
- Type your question in the chat input
- Click "Send" or press Enter
- Receive AI-generated answers based on scraped content
- See relevant source citations with relevance scores

### Example Workflow

```
1. Enter URL: https://example.com/faq
2. Click "Start Scraping"
3. Wait for scraping to complete (automatic progress tracking)
4. Wait for embedding to complete (automatic)
5. Ask questions like:
   - "What are the business hours?"
   - "Do you offer any discounts?"
   - "Where are you located?"
```

## Features in Detail

### Progress Tracking

**Scraping Progress:**
- Real-time status updates (pending → in_progress → completed)
- Page count tracking
- Animated terminal-style logs
- Error reporting with detailed messages

**Embedding Progress:**
- File detection and loading
- Multi-level progress (Files → Pages → Chunks)
- BGE-M3 model loading status
- Completion confirmation

### Log Display

- Terminal-style monospace font
- Green text on dark background
- Fade-out animation for old logs
- Auto-scroll to newest entries
- Keeps last 10 log entries visible

### Q&A System

- Powered by Claude Sonnet 4 and BGE-M3 embeddings
- 3-stage RAG pipeline:
  1. Query rewriting for better search
  2. Vector semantic search in Milvus
  3. Answer synthesis from relevant chunks
- Source attribution with relevance scores
- Conversational chat interface

## Configuration

### Environment Variables

- `API_BASE_URL`: Backend API endpoint (default: `http://localhost:8000`)
- `GRADIO_SERVER_PORT`: Frontend port (default: `7860`)
- `BACKEND_PATH`: Path to backend directory (default: `../backend`)

### Custom Styling

The interface uses custom CSS for:
- Terminal-style log container
- Fade-in/fade-out animations
- Status-based color coding
- Responsive layout

## Troubleshooting

**Issue: Frontend can't connect to backend**
- Ensure backend is running on the configured port
- Check `API_BASE_URL` in `.env`
- Verify CORS is enabled in backend

**Issue: Embedding fails**
- Ensure Milvus is running (if using Docker: `docker-compose up -d`)
- Check backend virtual environment is activated
- Verify `BACKEND_PATH` points to correct directory

**Issue: No cleaned markdown files found**
- Wait a few seconds after scraping completes
- Check `backend/cleaned_markdown_sites/` directory exists
- Ensure scraping completed successfully

**Issue: Chat not working**
- Verify query router is registered in `backend/src/main.py`
- Check `/api/query/ask` endpoint is accessible
- Ensure Milvus has embedded data

## Architecture

### Workflow

```
URL Input → Scrape API → Poll Status → Scraping Complete
                                           ↓
                                    Find Latest File
                                           ↓
                                    Run Embedding CLI
                                           ↓
                                    Parse Subprocess Output
                                           ↓
                                    Embedding Complete
                                           ↓
                                    Enable Chat Interface
                                           ↓
                              User Queries → RAG Pipeline → Answers
```

### Technology Stack

- **Frontend Framework**: Gradio 6.0+
- **HTTP Client**: httpx (async)
- **Backend Communication**: HTTP polling (1-second intervals)
- **Embedding Execution**: Python subprocess
- **Progress Tracking**: Gradio Progress component
- **Styling**: Custom CSS with animations

## Development

### Project Structure

```
frontend/
├── app.py              # Main Gradio application
├── requirements.txt    # Python dependencies
├── .env.example       # Environment template
└── README.md          # This file
```

### Key Functions

- `start_scraping()`: Polls backend for scraping progress
- `start_embedding()`: Runs embedding CLI as subprocess
- `chat_fn()`: Queries RAG endpoint for answers
- `format_logs()`: Generates animated HTML logs
- `enable_chat()`: Enables chat interface after embedding

## Next Steps

Future enhancements could include:

- File upload for custom documents
- Multi-site knowledge base management
- Export chat history
- Advanced filtering and search
- Batch URL processing

## Support

For issues or questions:
- Check backend logs for API errors
- Review Gradio terminal output for frontend errors
- Ensure all dependencies are installed
- Verify environment configuration

## License

See project root for license information.
