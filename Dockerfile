FROM python:3.11-slim

WORKDIR /app

# Cache-bust: 2026-04-18 15:07 UTC - force rebuild for SQL editor feature

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    bsdutils \
    unzip \
    curl \
    && curl -sL https://github.com/duckdb/duckdb/releases/latest/download/duckdb_cli-linux-amd64.zip -o /tmp/duckdb.zip \
    && unzip -o /tmp/duckdb.zip -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/duckdb \
    && rm /tmp/duckdb.zip \
    && apt-get purge -y unzip curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY dashboard/requirements.txt /app/dashboard/requirements.txt
RUN pip install --no-cache-dir -r /app/dashboard/requirements.txt

# Install additional dependencies
RUN pip install --no-cache-dir \
    duckdb \
    dbt-duckdb \
    pandas \
    numpy \
    gunicorn

# Copy the application code
COPY . /app/

# Set environment variables
# Railway injects PORT; use it for the healthcheck to work
ENV PYTHONPATH=/app
ENV DUCKLAKE_CATALOG=/app/data/catalog/vaccination_lake.ducklake
ENV DUCKLAKE_DATA=/app/data/parquet
ENV MESH_ARCHIVE_DIR=/app/data/mesh/archive
ENV MESH_INBOX_DIR=/app/data/mesh/inbox
ENV MESH_PROCESSING_DIR=/app/data/mesh/processing
ENV MESH_LOGS_DIR=/app/data/mesh/logs
ENV DUCKLAKE_HOST=0.0.0.0
ENV FLASK_ENV=production

# Create required directories (aligned with MESH env vars above)
RUN mkdir -p \
    /app/data/catalog \
    /app/data/parquet \
    /app/data/mesh/inbox \
    /app/data/mesh/archive \
    /app/data/mesh/processing \
    /app/data/mesh/logs \
    /app/data/mesh/error

# Do NOT init catalog at build time — it should be done at runtime
# to avoid stale locks and path mismatches

# Use gunicorn with PORT env var (Railway injects this)
# 1 worker to avoid DuckDB lock conflicts, 4 threads for concurrent reads
EXPOSE 8080
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 120 dashboard.app:app