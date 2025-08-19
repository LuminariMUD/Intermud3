# Multi-stage build for I3 Gateway
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels .

# Final stage
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 i3gateway && \
    mkdir -p /app/logs /app/state /app/config && \
    chown -R i3gateway:i3gateway /app

WORKDIR /app

# Copy wheels from builder
COPY --from=builder /app/wheels /wheels

# Install runtime dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /wheels/* && \
    rm -rf /wheels

# Copy application code
COPY --chown=i3gateway:i3gateway src/ src/
COPY --chown=i3gateway:i3gateway config/config.yaml config/

# Switch to non-root user
USER i3gateway

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s = socket.socket(); s.connect(('localhost', 4001)); s.close()"

# Expose ports
EXPOSE 4001 8080

# Run the application
CMD ["python", "-m", "src"]