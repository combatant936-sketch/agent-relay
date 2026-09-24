# syntax=docker/dockerfile:1
# ── Agent Relay – SQLite starter ─────────────────────────────────────────────
#
# Build:  docker build -t agent-relay:local .
# Run:    docker run --rm -p 8000:8000 agent-relay:local
# Dashboard: http://localhost:8000/dashboard
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: install dependencies with uv ────────────────────────────────────
FROM python:3.11-slim AS builder

# Install uv (fast pip replacement)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifests first so Docker can cache this layer
COPY pyproject.toml uv.lock ./

# Install only production deps into a local venv
RUN uv sync --frozen --no-dev --no-install-project

# ── Stage 2: lean runtime image ───────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN adduser --disabled-password --no-create-home relay

WORKDIR /app

# Copy the pre-built venv from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY dashboard.html dashboard.py database.py errors.py \
     file.py main.py schemas.py storage.py worker.py ./

# The SQLite database lives in /data so it can be bind-mounted for persistence.
# Without a mount, the container uses an in-memory-equivalent ephemeral file.
RUN mkdir /data && chown relay:relay /data

USER relay

# Tell SQLAlchemy to put the database in /data
ENV RELAY_DATABASE_URL=sqlite:////data/agent-relay.db

# Expose the API port (documentation only; -p is still required at runtime)
EXPOSE 8000

# ── IMPORTANT: bind to 0.0.0.0, not the default 127.0.0.1 ───────────────────
# Without this, uvicorn only listens on the loopback interface *inside* the
# container, so -p 8000:8000 appears broken even though the port is published.
CMD ["/app/.venv/bin/uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000"]
