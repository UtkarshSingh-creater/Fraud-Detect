# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a separate layer for caching
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Create directories the app writes to
RUN mkdir -p logs data

# Create a non-root user — never run as root in production
RUN useradd -m -u 1001 proctor && chown -R proctor:proctor /app
USER proctor

# Expose the FastAPI port
EXPOSE 8000

# Docker health check — hits our /health/live endpoint every 30s
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')"

# Production server command
# --workers 1 is intentional — we use in-memory session state + WebSockets,
# which don't work correctly across multiple workers without Redis pub/sub.
# Scale horizontally with multiple containers + Redis instead.
CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "warning"]