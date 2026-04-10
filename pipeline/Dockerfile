# SalientSignal pipeline Dockerfile — Phase E17 of the backfill plan.
#
# This image runs the hourly pipeline cron on Render's free tier. Render's
# Blueprint ("render.yaml") at the repo root points at this file and runs
# the final CMD as a scheduled cron job.
#
# Build context: repo root (the build reads ./pipeline and ./shared both).
# Build command: docker build -f pipeline/Dockerfile .
#
# Design notes:
#   - Uses python:3.11-slim as the base. ~50 MB uncompressed vs ~900 MB for
#     the non-slim image. Sufficient for what we need because gdeltdoc +
#     supabase + pandas are pure Python / small C extensions.
#   - System packages kept to the absolute minimum: ``git`` (some pip
#     installs need it), ``build-essential`` only long enough to compile
#     dependencies, then purged.
#   - Runs as non-root (uid 10001) per Render best practices.
#   - Only copies pipeline/ and shared/ into the image — NOT the whole repo.
#     The Next.js frontend code lives outside the Docker context for this
#     image and would just bloat it.
#   - Environment variables (SUPABASE_URL, SUPABASE_SECRET_KEY, LOG_LEVEL)
#     are NOT baked in. Render injects them at container start time from
#     the dashboard env vars.

FROM python:3.11-slim AS base

# Render-friendly: non-interactive, no pyc files, no pip cache
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LOG_LEVEL=INFO

WORKDIR /app

# System deps for compiling pandas / numpy / brotli wheels that don't ship
# pre-built for arm64 or musl. Purged after pip install completes.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest FIRST so Docker can cache the pip install layer
# across code-only changes.
COPY pipeline/pyproject.toml ./pipeline/pyproject.toml

# Install the pipeline package in editable mode. This reads pyproject.toml
# and pulls the full dependency tree (gdeltdoc, supabase, pandas, numpy,
# python-dotenv, etc.) without cloning a venv inside the image.
RUN pip install --upgrade pip \
    && pip install -e ./pipeline

# Now copy the actual code. Subsequent code-only changes only bust this
# layer, not the pip install above, so iteration stays fast.
COPY pipeline ./pipeline
COPY shared ./shared

# Remove build-only system packages to slim the final image.
RUN apt-get purge -y build-essential libffi-dev \
    && apt-get autoremove -y \
    && apt-get clean

# Non-root user per Render security best practices.
RUN useradd --uid 10001 --no-create-home --shell /bin/false pipeline \
    && chown -R pipeline:pipeline /app
USER pipeline

# Default command: run the live hourly pipeline.
# The Render cron schedule in render.yaml invokes this as a one-shot job.
CMD ["python", "-m", "pipeline.scripts.run_pipeline"]
