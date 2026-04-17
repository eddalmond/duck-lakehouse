#!/usr/bin/env bash
set -euo pipefail

echo "=== Duck Lakehouse: Full Pipeline ==="
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$ROOT_DIR"

echo "[1/5] Generating v5 vaccination data..."
python -m duck_lakehouse.data_generator \
    --output duck_lakehouse/mesh_simulator/inbox \
    --records 200 \
    --type all

echo ""
echo "[2/5] Running MESH simulator (process inbox -> archive)..."
python -m duck_lakehouse.mesh_simulator --once

echo ""
echo "[3/5] Initialising DuckLake..."
python -m duck_lakehouse.ducklake.init_ducklake

echo ""
echo "[4/5] Ingesting archived files into DuckLake..."
python -m duck_lakehouse.ducklake.ingest

echo ""
echo "[5/5] Running dbt models..."
cd duck_lakehouse/dbt/dbt_ducklake
dbt run --profiles-dir .
dbt test --profiles-dir .
cd "$ROOT_DIR"

echo ""
echo "=== Pipeline complete! ==="
echo ""
echo "Query DuckLake directly:"
echo "  duckdb duck_lakehouse/ducklake/catalog/vaccination_lake.ducklake"
echo ""
echo "  USE vaccination_lake;"
echo "  SELECT COUNT(*) FROM marts.fct_vaccination_events;"