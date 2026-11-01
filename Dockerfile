# ==============================================================================
# Multi-stage Dockerfile for erp-iot-simulator using uv (Dev/Staging Only)
# ==============================================================================

# Stage 1: Build virtual environment
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy application source explicitly (avoid COPY . to prevent leaking non-essential files)
COPY app/ /app/app/
COPY main.py pyproject.toml uv.lock README.md /app/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Stage 2: Minimal runtime image
FROM python:3.12-slim-bookworm

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY --from=builder --chown=appuser:appuser /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=dev \
    SERVER_PORT=8089

USER appuser

EXPOSE 8089

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8089/healthz').read()" || exit 1

ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8089"]
