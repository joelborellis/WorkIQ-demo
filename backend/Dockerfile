# ── Build stage ────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /app

# Install uv (fast Python package installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies into an in-project venv
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY app/ ./app/

# ── Runtime stage ───────────────────────────────────────────────────────────────
FROM python:3.13-slim

WORKDIR /app

# Copy installed venv and source from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app   /app/app

# Activate the venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Azure Container Apps injects $PORT; fall back to 8000 for local Docker runs.
# Adjust --workers based on your Container App CPU allocation (1 worker per core).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
