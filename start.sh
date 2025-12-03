#!/bin/bash
set -e

echo "==================================="
echo "Starting Agentic Scraper..."
echo "==================================="

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY environment variable is not set!"
    echo "Please set it in the Space settings under 'Repository secrets'"
    exit 1
fi

echo "✓ ANTHROPIC_API_KEY is set"

# Verify directories exist
echo "Creating data directories..."
mkdir -p /app/chroma_db /app/data
echo "✓ Directories created"

echo ""
echo "==================================="
echo "Starting FastAPI backend..."
echo "==================================="
cd /app/backend
uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to be ready
echo "Waiting for backend to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/api/query/health > /dev/null 2>&1; then
        echo "✓ Backend is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo ""
        echo "==================================="
        echo "ERROR: Backend failed to start within 30 seconds"
        echo "==================================="
        echo ""
        echo "Backend logs:"
        cat /tmp/backend.log
        echo ""
        kill $BACKEND_PID 2>/dev/null || true
        exit 1
    fi
    echo -n "."
    sleep 1
done

echo ""
echo "==================================="
echo "Starting Gradio frontend..."
echo "==================================="
cd /app/frontend
python app.py
