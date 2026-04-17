#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PKG_ROOT="$(dirname "$PROJECT_DIR")"

PORT="${DUCKLAKE_PORT:-8765}"
HOST="${DUCKLAKE_HOST:-0.0.0.0}"

export PYTHONPATH="$PKG_ROOT:${PYTHONPATH:-}"

echo "=== DuckLake Local Launcher ==="
echo "Project:  $PROJECT_DIR"
echo "Pkg root: $PKG_ROOT"
echo "Host:     $HOST"
echo "Port:     $PORT"
echo ""

mkdir -p "$PROJECT_DIR/mesh_simulator/inbox"
mkdir -p "$PROJECT_DIR/mesh_simulator/archive"
mkdir -p "$PROJECT_DIR/mesh_simulator/processing"
mkdir -p "$PROJECT_DIR/mesh_simulator/logs"
mkdir -p "$PROJECT_DIR/mesh_simulator/error"
mkdir -p "$PROJECT_DIR/ducklake/catalog"
mkdir -p "$PROJECT_DIR/ducklake/data"

echo "--- Step 1/3: Init DuckLake ---"
python3 -c "from duck_lakehouse.ducklake.init_ducklake import main; main()" || { echo "Init failed"; exit 1; }

echo ""
echo "--- Step 2/3: Generate sample data ---"
python3 -m duck_lakehouse.data_generator --output "$PROJECT_DIR/mesh_simulator/inbox" --records 100 --type all || { echo "Generate failed"; exit 1; }

echo ""
echo "--- Step 3/3: Run MESH + Ingest ---"
python3 -m duck_lakehouse.mesh_simulator --once || { echo "MESH simulator failed"; exit 1; }
python3 -m duck_lakehouse.ducklake.ingest || { echo "Ingest failed"; exit 1; }

echo ""
echo "=== Starting dashboard on http://$HOST:$PORT ==="
echo "Press Ctrl+C to stop."
echo ""

cd "$PROJECT_DIR/dashboard"
exec python3 app.py