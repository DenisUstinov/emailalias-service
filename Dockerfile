# base
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# builder
FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.10.7 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev -o requirements.txt && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt && \
    rm requirements.txt

# runtime
FROM base AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels
RUN useradd --create-home --uid 1000 appuser
RUN chown appuser:appuser /app
COPY --chown=appuser:appuser . .
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
  CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# development
FROM runtime AS development
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
RUN uv sync --frozen --dev
