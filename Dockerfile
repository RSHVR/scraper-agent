FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers (optimized - only chromium, no extra deps)
RUN pip install --no-cache-dir playwright==1.40.0 && \
    playwright install chromium && \
    playwright install-deps chromium

# Copy requirements files first (for better layer caching)
COPY backend/requirements.txt /app/backend/requirements.txt
COPY frontend/requirements.txt /app/frontend/requirements.txt

# Install Python dependencies (backend)
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Install Python dependencies (frontend)
RUN pip install --no-cache-dir -r /app/frontend/requirements.txt

# Copy application code
COPY backend /app/backend
COPY frontend /app/frontend

# Create directories for ChromaDB and data persistence
RUN mkdir -p /app/chroma_db /app/data

# Copy startup script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose ports (Gradio on 7860, FastAPI on 8000)
EXPOSE 7860 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1

# Run startup script
CMD ["/app/start.sh"]
