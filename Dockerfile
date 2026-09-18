# Stage 1: Build frontend with pnpm
FROM node:22-slim AS frontend-builder
RUN corepack enable && corepack prepare pnpm@11.20.0 --activate
WORKDIR /app/web

COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
# Run install
RUN pnpm install --frozen-lockfile

COPY web/ ./
RUN pnpm build

# Stage 2: Python runtime with uv
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Copy dependency definition
COPY pyproject.toml uv.lock ./

# Install python dependencies without project root
RUN uv sync --frozen --no-install-project --no-dev

# Copy application source
COPY src ./src
COPY README.md ./

# Install project package into virtualenv
RUN uv sync --frozen --no-dev

# Copy frontend static build assets from Stage 1
COPY --from=frontend-builder /app/web/dist ./web/dist

# Default environment configuration
ENV PATH="/app/.venv/bin:$PATH" \
    PORT=8000 \
    HOST=0.0.0.0 \
    HERMES_DB_PATH=/data/hermes/state.db \
    SHARE_DB_PATH=/data/share/share.db

# Create non-root user
RUN useradd -u 1000 -m -s /bin/bash appuser && \
    mkdir -p /data/share /data/hermes && \
    chown -R appuser:appuser /app /data

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

ENTRYPOINT ["hermes-share"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
