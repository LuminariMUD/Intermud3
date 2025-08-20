# Intermud3 Gateway Service - Production Docker Image
# Phase 3 COMPLETE (2025-08-20): Full API implementation
# Includes WebSocket & TCP servers, event distribution, auth middleware

# Multi-stage build for I3 Gateway
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY requirements.txt .
COPY requirements-dev.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

# Install runtime dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 i3gateway && \
    mkdir -p /app/logs /app/state /app/config && \
    chown -R i3gateway:i3gateway /app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code and client libraries
COPY --chown=i3gateway:i3gateway src/ src/
COPY --chown=i3gateway:i3gateway config/ config/
COPY --chown=i3gateway:i3gateway clients/ clients/

# Switch to non-root user
USER i3gateway

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO

# Health check using curl
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose ports
# 8080 - WebSocket API
# 8081 - TCP API  
# 9090 - Metrics/Health
EXPOSE 8080 8081 9090

# Run the application
CMD ["python", "-m", "src"]