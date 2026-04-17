# Duck Lakehouse - NHS Vaccinations v5 PoC

A proof-of-concept data lakehouse for NHS vaccination data using DuckLake,
DuckDB, and dbt-duckdb, following the NHSE Daily Vaccination Events (In-Bound)
Extract Technical Specification v5.1.

## Deployment

### Railway (One-Click Deploy)

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/YOUR_TEMPLATE_ID)

The project includes a `Dockerfile` and `railway.json` for Railway deployment. 
Simply connect your GitHub repo to Railway and it will automatically build and deploy.

**Environment Variables:**
- `DUCKLAKE_PORT` — Port for the dashboard (default: 8765)
- `DUCKLAKE_HOST` — Host to bind (default: 0.0.0.0)
- `DUCKLAKE_CATALOG` — Path to DuckLake catalog file
- `DUCKLAKE_DATA` — Path to DuckLake data directory

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │         NHS MESH (simulated)         │
                    └─────────────┬───────────────────────┘
                                  │ pipe-delimited CSV
                                  ▼
  ┌─────────────────────────────────────────────────────────┐
  │                    MESH Simulator                         │
  │   inbox/  →  processing/  →  archive/                    │
  └─────────────────────┬───────────────────────────────────┘
                        │ CSV files
                        ▼
  ┌─────────────────────────────────────────────────────────┐
  │                Ingest Layer                               │
  │   Parse pipe-delimited v5 CSV → DuckLake staging         │
  └─────────────────────┬───────────────────────────────────┘
                        │
                        ▼
  ┌─────────────────────────────────────────────────────────┐
  │                DuckLake (DuckDB Catalog)                  │
  │                                                           │
  │   staging.stg_vaccinations                               │
  │   intermediate.int_vaccinations_parsed                   │
  │   intermediate.int_vaccinations_validated                │
  │   intermediate.int_vaccinations_deduplicated             │
  │   marts.fct_vaccination_events                           │
  │   marts.dim_patient                                      │
  │   marts.dim_site                                         │
  │   marts.dim_vaccine                                      │
  │   reference.ref_file_audit                               │
  └─────────────────────┬───────────────────────────────────┘
                        │
                        ▼
  ┌─────────────────────────────────────────────────────────┐
  │                dbt-duckdb Models                          │
  │                                                           │
  │   staging/   → Raw data, column rename, type hints       │
  │   intermediate/ → Parse, validate, deduplicate            │
  │   marts/     → Star schema (fact + dimension tables)     │
  └─────────────────────────────────────────────────────────┘
```

## Local Development

### Prerequisites

- **Python 3.10+**
- **DuckDB** (`pip install duckdb`)
- **dbt-duckdb** (`pip install dbt-duckdb`)
- **Docker & Docker Compose** (optional, for containerised stack)
- **Make** (optional, for task runner)

### Quick Start (One-Command Smoke Test)

```bash
make smoke
```

This runs the full pipeline: initialise → generate → ingest → dbt-run → dbt-test.

### Start Dashboard

```bash
python3 dashboard/app.py
```

Access the dashboard at `http://localhost:8765`

## Project Structure

```
duck-lakehouse/
├── dashboard/                 # Flask web UI
│   ├── app.py                # Main Flask application
│   ├── requirements.txt      # Python dependencies
│   └── static/               # Frontend assets
│       ├── index.html
│       ├── app.js
│       └── styles.css
├── duck_lakehouse/           # Python package
│   ├── data_generator/       # NHS v5 CSV data generator
│   ├── ducklake/            # DuckLake catalog & ingest
│   ├── mesh_simulator/      # MESH file watcher
│   └── __init__.py
├── dbt/                      # dbt-duckdb transformations
│   └── dbt_ducklake/
├── docker/                   # Docker configurations
├── design/                   # Architecture docs
├── aws/                      # AWS deployment notes
├── terraform/                # Infrastructure as code
├── scripts/                  # Utility scripts
├── Dockerfile                # Railway deployment
├── railway.json              # Railway configuration
├── docker-compose.yml        # Local stack
├── Makefile                  # Task automation
└── README.md                 # This file
```

## Commands

| Command | Description |
|---------|-------------|
| `make init` | Initialise DuckLake catalog |
| `make generate` | Generate sample v5 CSV data |
| `make ingest` | Run MESH simulator + ingest to DuckLake |
| `make dbt-run` | Run dbt models |
| `make dbt-test` | Run dbt tests (v5 spec compliance) |
| `make smoke` | End-to-end pipeline test |
| `make clean` | Remove generated data |

## Docker Compose

```bash
# Start the stack
docker compose up

# Stop the stack
docker compose down
```

Services:
- **ducklake** — DuckDB with DuckLake extension
- **mesh-simulator** — MESH file processor
- **dbt** — dbt-duckdb runner
- **postgres** (profile: aws) — PostgreSQL catalog (optional)

## Tech Stack

- **DuckDB** — In-process OLAP database
- **DuckLake** — DuckDB-based lakehouse extension
- **dbt** — Data transformation (staging → marts)
- **Flask** — Web dashboard backend
- **Railway** — Cloud deployment platform

## License

MIT