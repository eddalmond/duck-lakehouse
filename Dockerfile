FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY dashboard/requirements.txt /app/dashboard/requirements.txt
RUN pip install --no-cache-dir -r /app/dashboard/requirements.txt

# Install additional dependencies
RUN pip install --no-cache-dir \
    duckdb \
    dbt-duckdb \
    pandas \
    numpy

# Copy the application code
COPY . /app/

# Set environment variables
# These can be overridden by Railway env vars
ENV PYTHONPATH=/app
ENV DUCKLAKE_CATALOG=/app/data/catalog/vaccination_lake.ducklake
ENV DUCKLAKE_DATA=/app/data/parquet
ENV MESH_ARCHIVE_DIR=/app/data/mesh/archive
ENV DUCKLAKE_HOST=0.0.0.0
ENV DUCKLAKE_PORT=8765
ENV FLASK_ENV=production

# Create required directories for both local and Railway paths
RUN mkdir -p \
    /app/data/catalog \
    /app/data/parquet \
    /app/data/mesh/inbox \
    /app/data/mesh/archive \
    /app/data/mesh/processing \
    /app/data/mesh/logs \
    /app/data/mesh/error \
    /app/duck_lakehouse/ducklake/catalog \
    /app/duck_lakehouse/ducklake/data \
    /app/duck_lakehouse/mesh_simulator/inbox \
    /app/duck_lakehouse/mesh_simulator/archive \
    /app/duck_lakehouse/mesh_simulator/processing \
    /app/duck_lakehouse/mesh_simulator/logs \
    /app/duck_lakehouse/mesh_simulator/error

# Do NOT init catalog at build time — it should be done at runtime
# to avoid stale locks and path mismatches

# Expose the port
EXPOSE 8765

# Use Flask dev server with threaded=True (single process avoids DuckDB lock conflicts)
# Gunicorn would also work with --workers 1 but Flask is simpler for a PoC
CMD ["python3", "/app/dashboard/app.py"]