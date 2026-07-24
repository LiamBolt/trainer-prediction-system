# ---------------------------------------------------------------------------
# Builder — resolves and installs dependencies into a self-contained venv.
# Kept separate so the runtime image carries no compilers, no uv, and no lock
# file; only the virtualenv and the source.
#
# Deliberately no `# syntax=docker/dockerfile:1` directive and no
# `COPY --from=ghcr.io/astral-sh/uv`: both pull an image from an external
# registry at build time, turning a local build into a network dependency on two
# registries beyond Docker Hub. uv is installed from PyPI, which the project
# already depends on and which is therefore already known to be reachable.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=20 \
    # uv's default HTTP timeout is 30s, which a constrained link exceeds on the
    # larger wheels. Raising it turns a hard build failure into a slow build.
    UV_HTTP_TIMEOUT=300

RUN pip install --no-cache-dir uv==0.5.11

WORKDIR /app

# Dependency manifests first, and only them. Editing application source must not
# invalidate this layer — that is the difference between a few-second rebuild and
# a multi-minute one.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Source last.
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
COPY data ./data
COPY alembic.ini ./
RUN uv sync --frozen --no-dev


# ---------------------------------------------------------------------------
# Runtime — slim, non-root, no build tooling.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# A container running as root is an audit finding, and the blast radius of a
# container escape is proportional to the privileges of the process inside it.
RUN groupadd --system --gid 1001 tps \
 && useradd --system --uid 1001 --gid tps --create-home tps

WORKDIR /app

COPY --from=builder --chown=tps:tps /app/.venv /app/.venv
COPY --from=builder --chown=tps:tps /app/app /app/app
COPY --from=builder --chown=tps:tps /app/migrations /app/migrations
COPY --from=builder --chown=tps:tps /app/scripts /app/scripts
COPY --from=builder --chown=tps:tps /app/data /app/data
COPY --from=builder --chown=tps:tps /app/alembic.ini /app/alembic.ini

USER tps

EXPOSE 8000

# Hits a real readiness endpoint that executes SELECT 1, not a static 200. A
# healthcheck that cannot fail reports nothing. Reads $PORT so it follows the app
# whether that is the local default (8000) or the port a platform injects.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=20s \
  CMD python -c "import os,urllib.request,sys; p=os.environ.get('PORT','8000'); sys.exit(0 if urllib.request.urlopen(f'http://localhost:{p}/health/ready').status==200 else 1)"

# Migrations are NOT run here (B12). The container starts the API; a human runs
# Alembic as an explicit, reviewable step (from a laptop against the managed
# database, or `docker compose exec backend alembic upgrade head` locally).
#
# Shell form so ${PORT} is expanded: a managed platform (Render, Fly, Cloud Run)
# injects the port to bind, and defaults to 8000 everywhere else — the local
# compose file and the tested image are unaffected because PORT is unset there.
# `exec` hands PID 1 to uvicorn so it receives SIGTERM directly and shuts down cleanly.
ENTRYPOINT ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
