# DuckLake Dashboard

An attractive web interface for visualizing and controlling the NHS Vaccination v5 data pipeline.

## Features

- **Visual Pipeline Flow**: See all 5 stages at a glance with real-time status
- **Interactive Execution**: Run individual stages or the full pipeline with one click
- **Live Console**: Stream output from each stage in real-time
- **Data Preview**: Browse files and preview data at each pipeline stage
- **NHS Branded Design**: Clean, professional interface using NHS color palette

## Quick Start

```bash
cd duck_lakehouse/dashboard

# Install dependencies
pip install -r requirements.txt

# Run the dashboard
python app.py
```

Open http://localhost:5000 in your browser.

## Pipeline Stages

1. **Generate Data** - Creates realistic v5 vaccination CSV files (Flu, COVID, RSV, HPV, MMR)
2. **MESH Simulator** - Processes files through inbox → processing → archive workflow
3. **Init DuckLake** - Creates DuckLake catalog and database schemas
4. **Ingest** - Loads CSV data into staging tables
5. **dbt Transform** - Runs staging → intermediate → marts transformations

## Usage

### Run Individual Stage
Click the "Run" button on any stage card to execute just that step.

### Run Full Pipeline
Click the blue "Run Full Pipeline" button to execute all stages sequentially.

### Clean All Data
Click "Clean All Data" to reset everything (removes generated files, catalog, and data).

### View Data
Switch between the Files, Staging, and Marts tabs to see data at different pipeline stages.

## API Endpoints

- `GET /api/status` - Get current pipeline status
- `GET /api/files/{inbox|processing|archive|logs|catalog|data}` - List files
- `GET /api/preview/{csv_sample|staging|marts|row_counts}` - Preview data
- `GET /api/run/{generate|mesh|init|ingest|dbt}` - Stream stage execution (SSE)
- `POST /api/clean` - Clean all generated data
