# Canvas Scraper Production Dockerfile
# Multi-stage build for optimized production deployment

#===========================================
# Stage 1: Base Dependencies Builder
#===========================================
FROM python:3.11-slim as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

#===========================================
# Stage 2: Production Runtime
#===========================================
FROM python:3.11-slim as production

# Install runtime system dependencies including OCR support
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    cron \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r canvas && useradd -r -g canvas -s /bin/bash canvas

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/
COPY database/ ./database/
COPY tests/ ./tests/
COPY .env.example ./

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/downloads /app/config && \
    chown -R canvas:canvas /app

# Copy and set up entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Health check
COPY docker/healthcheck.py /healthcheck.py
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python /healthcheck.py

# Switch to non-root user
USER canvas

# Environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO \
    LOG_DIR=/app/logs

# Expose port for health checks (optional)
EXPOSE 8080

# Default command - can be overridden
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "scripts/run_enhanced_scraper.py", "run"]

#===========================================
# Stage 3: Development Environment
#===========================================
FROM production as development

# Switch back to root to install dev dependencies
USER root

# Install development tools
RUN apt-get update && apt-get install -y \
    git \
    vim \
    less \
    && rm -rf /var/lib/apt/lists/*

# Install development Python packages
RUN pip install --no-cache-dir \
    pytest \
    pytest-cov \
    black \
    flake8 \
    ipython

# Switch back to canvas user
USER canvas

# Override default command for development
CMD ["tail", "-f", "/dev/null"]