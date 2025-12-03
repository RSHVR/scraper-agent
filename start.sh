#!/bin/bash

# Start FastAPI backend in background
cd /app/backend
uvicorn src.main:app --host 0.0.0.0 --port 8000 &

# Wait for backend to be ready
echo "Waiting for backend to start..."
sleep 5

# Check backend health
curl -s http://localhost:8000/api/query/health || echo "Backend health check failed"

# Start Gradio frontend (foreground - keeps container alive)
cd /app/frontend
python app.py
