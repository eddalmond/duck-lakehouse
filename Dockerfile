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
    pandas \
    numpy

# Copy the application code
COPY . /app/

# Set environment variables
ENV PYTHONPATH=/app
ENV DUCKLAKE_CATALOG=/app/duck_lakehouse/ducklake/catalog/vaccination_lake.ducklake
ENV DUCKLAKE_DATA=/app/duck_lakehouse/ducklake/data
ENV DUCKLAKE_HOST=0.0.0.0
ENV DUCKLAKE_PORT=8765
ENV FLASK_ENV=production

# Create required directories
RUN mkdir -p /app/duck_lakehouse/ducklake/catalog \
    /app/duck_lakehouse/ducklake/data \
    /app/duck_lakehouse/mesh_simulator/inbox \
    /app/duck_lakehouse/mesh_simulator/archive \
    /app/duck_lakehouse/mesh_simulator/processing \
    /app/duck_lakehouse/mesh_simulator/logs \
    /app/duck_lakehouse/mesh_simulator/error

# Initialize the DuckLake catalog at build time
RUN python3 -c "from duck_lakehouse.ducklake.init_ducklake import main; main()" || echo "Note: Catalog init may require runtime data"

# Expose the port
EXPOSE 8765

# Run the application
CMD ["python3", "/app/dashboard/app.py"]