# Multi-stage build for Canvas Scraper
# Stage 1: Build dependencies
FROM python:3.11-slim as builder

# Set build arguments
ARG BUILD_DATE
ARG VERSION
ARG VCS_REF

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Production runtime
FROM python:3.11-slim as production

# Add metadata labels
LABEL maintainer="your-email@example.com" \
      version="${VERSION}" \
      build-date="${BUILD_DATE}" \
      vcs-ref="${VCS_REF}" \
      description="Canvas LMS API Scraper"

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --user-group --uid 1000 canvas

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder stage
COPY --from=builder /root/.local /home/canvas/.local

# Copy application code
COPY --chown=canvas:canvas . .

# Create logs directory
RUN mkdir -p /app/logs && chown canvas:canvas /app/logs

# Switch to non-root user
USER canvas

# Add local Python packages to PATH
ENV PATH=/home/canvas/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from config import Config; Config.validate()" || exit 1

# Default command
CMD ["python", "canvas_client.py"]