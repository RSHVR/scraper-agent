# Scraper Agent Dockerfile
# Python 3.11 base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install system dependencies
# - build-essential: Required for compiling Python packages
# - libxml2-dev, libxslt1-dev: Required for lxml (HTML parsing)
# - zlib1g-dev: Required for zlib-state (Milvus dependency)
# - curl: For health checks
RUN apt-get update && apt-get install -y \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright dependencies manually (avoiding obsolete font packages)
RUN apt-get update && apt-get install -y \
    # Chromium dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    # Fonts (using modern package names)
    fonts-liberation \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright and Chromium browser (without --with-deps to avoid package conflicts)
RUN playwright install chromium

# Copy application code
COPY . .

# Create directories for persistent data
# These will be mounted as volumes in docker-compose
RUN mkdir -p /app/data /app/models /app/milvus_data

# Expose port 8000 for FastAPI
EXPOSE 8000

# Health check - verifies the API is responding
# Runs every 30 seconds, times out after 10 seconds
# Gives 40 seconds at startup before first check
# Fails after 3 consecutive failures
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the FastAPI application
# --host 0.0.0.0: Listen on all network interfaces
# --port 8000: Default API port
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
