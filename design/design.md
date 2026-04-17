# Duck Lakehouse — Design Document

NHS Vaccinations v5 PoC: MESH ingestion → DuckLake lakehouse → dbt transforms → analytics marts

---

## 1. Component Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Local Stack (Docker Compose)                 │
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────────────────┐  │
│  │ MESH Simulator│───▶│  Ingestion   │───▶│  DuckLake (DuckDB)   │  │
│  │ (file watcher)│    │  Scripts     │    │  + SQLite catalog     │  │
│  └──────────────┘    └──────────────┘    └──────────┬─────────────┘  │
│                                                    │                │
│                                          ┌─────────▼──────────┐    │
│                                          │   dbt-duckdb        │    │
│                                          │   staging → int →   │    │
│                                          │   marts             │    │
│                                          └─────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.1 Data Generator

Generates realistic NHS vaccination records following the v5.1 spec (NHSE Daily Vaccination Events In-Bound Extract Technical Specification v5.1 FINAL).

- **Output format**: Pipe-delimited CSV with double-quoted fields per NHSE spec (section 3.4)
- **File naming**: `{DiseaseType}_Vaccinations_v5_{ODSCode}_{YYYYMMDDThhmmsszz}.csv`
- **Header row**: Pipe-delimited field names (section 3.2)
- **Field set**: 34 fields from v5.1 spec (NHS_NUMBER through LOCATION_CODE_TYPE_URI)
- **Record terminator**: CRLF
- **Null representation**: Consecutive delimiters with no content

Supported vaccination types:
- COVID-19
- Flu (seasonal)
- RSV
- HPV
- MMR

Each type generates into a separate CSV file (different vaccinations must not be mixed in the same file per spec).

**Key v5.1 fields** (positional order):

| Pos | Field | Type | M/R/O | Notes |
|-----|-------|------|-------|-------|
| 1 | NHS_NUMBER | String(10) | R | Validated, no padding |
| 2 | PERSON_FORENAME | String | M | PDS-registered |
| 3 | PERSON_SURNAME | String | M | PDS-registered |
| 4 | PERSON_DOB | Date YYYYMMDD | M | |
| 5 | PERSON_GENDER_CODE | String(0/1/2/9) | M | |
| 6 | PERSON_POSTCODE | String(8) | M | Inward/outward separated by space |
| 7 | DATE_AND_TIME | DateTime YYYYMMDDThhmmsszz | M | Vaccination admin time |
| 8 | SITE_CODE | ODS Code | M | Commissioned provider ODS |
| 9 | SITE_CODE_TYPE_URI | URI | M | https://fhir.nhs.uk/Id/ods-organization-code |
| 10 | UNIQUE_ID | String (UUID) | M | Globally unique with UNIQUE_ID_URI |
| 11 | UNIQUE_ID_URI | URI | M | System identifier URI |
| 12 | ACTION_FLAG | new/update/delete | M | |
| 13 | PERFORMING_PROFESSIONAL_FORENAME | String | O | |
| 14 | PERFORMING_PROFESSIONAL_SURNAME | String | O | |
| 15 | RECORDED_DATE | Date YYYYMMDD | M | Record creation date |
| 16 | PRIMARY_SOURCE | TRUE/FALSE | M | Case-sensitive uppercase |
| 17 | VACCINATION_PROCEDURE_CODE | SNOMED-CT | M | Procedure concept ID |
| 18 | VACCINATION_PROCEDURE_TERM | SNOMED-CT | R | |
| 19 | DOSE_SEQUENCE | String(1-9) | R | |
| 20 | VACCINE_PRODUCT_CODE | dm+d AMP | R | Not AMPP/VMP/VMPP |
| 21 | VACCINE_PRODUCT_TERM | dm+d AMP | R | |
| 22 | VACCINE_MANUFACTURER | String | R | |
| 23 | BATCH_NUMBER | String(100) | R | GS1 GTIN/NTIN preferred |
| 24 | EXPIRY_DATE | Date YYYYMMDD | R | |
| 25 | SITE_OF_VACCINATION_CODE | SNOMED-CT | R | Refset 1127941000000100 |
| 26 | SITE_OF_VACCINATION_TERM | SNOMED-CT | R | |
| 27 | ROUTE_OF_VACCINATION_CODE | SNOMED-CT | R | Refset 999000051000001100 |
| 28 | ROUTE_OF_VACCINATION_TERM | SNOMED-CT | R | |
| 29 | DOSE_AMOUNT | Decimal(max 4) | R | e.g. "0.30" |
| 30 | DOSE_UNIT_CODE | dm+d SNOMED-CT | R | 258773002 = millilitre |
| 31 | DOSE_UNIT_TERM | dm+d SNOMED-CT | R | |
| 32 | INDICATION_CODE | SNOMED-CT | R | |
| 33 | LOCATION_CODE | ODS or URN | M | Where vaccination administered |
| 34 | LOCATION_CODE_TYPE_URI | URI | M | |

### 1.2 MESH Simulator

Local file-based simulation of NHS MESH (Message Exchange for Social Care and Health).

NHS MESH is the standard secure file transfer mechanism for NHS data flows. In production, suppliers upload CSV files to MESH, and NHSE consumes them. This simulator replicates that flow locally.

**Directory structure:**
```
mesh/
├── inbox/          # Supplier drops files here (simulates MESH send)
├── processing/     # Files being ingested
├── archive/        # Successfully processed files
├── error/          # Files that failed validation
└── logs/           # Processing logs
```

**Operation:**
1. Watch `inbox/` for new CSV files (polling interval: 5s)
2. Move file to `processing/`
3. Validate file against v5.1 spec (header format, field count, encoding)
4. On success: ingest into DuckLake, move file to `archive/`
5. On failure: move file to `error/`, log error details
6. Emulates the terraform-aws-mesh-client serverless pattern:
   - inbox = S3 upload → Lambda trigger
   - processing = Lambda execution
   - archive = S3 archive bucket
   - error = DLQ

### 1.3 DuckLake Layer

DuckLake provides an ACID-transactional lakehouse on top of Parquet files, using DuckDB's `ducklake` extension (v1.0).

**Catalog**: Stores table metadata
- **Local**: SQLite file (`catalog.ducklake`)
- **AWS**: PostgreSQL (RDS/Aurora Serverless)

**Data storage**: Stores actual data as Parquet files
- **Local**: Local filesystem (`./data/` directory)
- **AWS**: S3 bucket

**Connection pattern:**
```sql
-- Local
ATTACH 'ducklake:catalog.ducklake' AS lakehouse (DATA './data');
-- AWS
ATTACH 'ducklake:pg:postgrs://user:pass@host:5432/catalog' AS lakehouse (DATA 's3://bucket/data');
```

**Tables created by ingestion:**
- `lakehouse.raw_vaccinations` — raw v5.1 CSV data (all fields as VARCHAR initially)
- `lakehouse.raw_vaccinations_archive` — append-only audit log of processed files

### 1.4 dbt Project

Uses `dbt-duckdb` adapter with DuckLake support for transformation and modelling.

**Model layers:**

```
models/
├── staging/
│   ├── stg_vaccinations.sql          # Cast types, rename, add metadata
│   └── _staging__models.yml          # Source definitions + basic tests
├── intermediate/
│   ├── int_vaccinations_deduped.sql   # Deduplicate by UNIQUE_ID (keep latest ACTION_FLAG)
│   ├── int_vaccinations_enriched.sql  # Join with SNOMED lookups, derive fields
│   └── _intermediate__models.yml
└── marts/
    ├── mart_vaccinations_by_site.sql  # Aggregated site-level metrics
    ├── mart_vaccinations_by_type.sql  # Aggregated vaccine-type metrics
    ├── mart_patient_history.sql       # Patient vaccination history
    └── _marts__models.yml
```

**Staging tests (v5 field validation):**
- `NHS_NUMBER`: not null, length 10, numeric only
- `PERSON_DOB`: valid date format YYYYMMDD
- `PERSON_GENDER_CODE`: accepted_values [0, 1, 2, 9]
- `PRIMARY_SOURCE`: accepted_values [TRUE, FALSE]
- `ACTION_FLAG`: accepted_values [new, update, delete]
- `DATE_AND_TIME`: valid datetime format
- `DOSE_SEQUENCE`: accepted_values 1-9
- `UNIQUE_ID`: not null, unique (with UNIQUE_ID_URI)
- `SITE_CODE`: not null

**Intermediates:**
- Deduplication: Keep latest record per `UNIQUE_ID + UNIQUE_ID_URI` based on `RECORDED_DATE`
- Enrichment: Derive vaccine type from `VACCINATION_PROCEDURE_CODE`, map SNOMED terms

**Marts:**
- Site-level: vaccinations per site per day, by vaccine type
- Type-level: vaccinations by disease type, dose sequence
- Patient: full vaccination history per NHS_NUMBER

### 1.5 Local Stack (Docker Compose)

```yaml
services:
  ducklake:           # DuckDB + ducklake extension + SQLite catalog
  mesh-simulator:     # MESH file watcher process
  dbt:                # dbt-duckdb runner
```

**Scripts (Makefile targets):**
- `make init` — Initialize DuckLake catalog and tables
- `make generate` — Run data generator to produce v5 CSV files
- `make send` — Copy generated files to MESH inbox
- `make ingest` — Run MESH simulator ingestion loop (one-shot)
- `make dbt-run` — Run dbt models
- `make dbt-test` — Run dbt tests
- `make up` — Start all containers
- `make down` — Stop all containers
- `make smoke` — End-to-end: generate → send → ingest → dbt-run → dbt-test

### 1.6 AWS Expansion (Future)

Infrastructure-as-code for deploying to AWS:

**Terraform modules:**
- `terraform-aws-ducklake` — S3 bucket + PostgreSQL catalog (RDS/Aurora) + IAM
- `terraform-aws-mesh-client` — MESH integration (reuses existing terraform-aws-mesh-client pattern)
- `terraform-aws-dbt-runner` — ECS/Fargate task for dbt execution on schedule

**Not in scope for PoC — documented here for architectural completeness only.**

---

## 2. Data Flow

```
┌─────────────┐    ┌────────────────┐    ┌───────────┐    ┌──────────────────────┐
│   Data       │    │  MESH Simulator │    │  DuckLake  │    │  dbt-duckdb          │
│   Generator  │───▶│  inbox/         │───▶│  Ingestion │───▶│  staging → int → mart │
│   (Python)   │    │  processing/    │    │  (SQL)     │    │  (SQL + YAML)        │
│              │    │  archive/       │    │            │    │                      │
└─────────────┘    └────────────────┘    └───────────┘    └──────────────────────┘
       1                    2                    3                    4
```

### Step 1: Generate

The Python data generator produces v5.1-compliant CSV files into `data/generated/`. Each file contains a realistic batch of vaccination records ( configurable count, default 1000 records per file). Patient data uses realistic SNOMED codes, dm+d product codes, and ODS site codes sourced from the existing `schemas/` and `enriched/` data in this repository.

### Step 2: MESH Send → Inbox

Generated files are moved to `mesh/inbox/`, simulating a supplier uploading to MESH. The MESH simulator watches this directory and picks up new files.

### Step 3: Ingestion

The ingestion process:
1. Picks up file from `inbox/`, moves to `processing/`
2. Reads CSV with pipe delimiter, validates header row matches v5.1 field names
3. Loads into `lakehouse.raw_vaccinations` (all VARCHAR — preserves raw data)
4. Appends file metadata to `lakehouse.raw_vaccinations_archive` (filename, record count, processing timestamp)
5. On success: moves file to `archive/`
6. On error: moves file to `error/`, logs details

DuckLake guarantees ACID transactions — partial ingestion is rolled back on failure.

### Step 4: dbt Transform

dbt processes the data through three layers:
1. **Staging**: Cast raw VARCHAR fields to proper types (DATE, INTEGER, BOOLEAN), add `_loaded_at` timestamp, rename for clarity
2. **Intermediate**: Deduplicate records (latest per UNIQUE_ID), enrich with derived fields
3. **Marts**: Build aggregation tables for reporting — by site, by vaccine type, by patient

---

## 3. File Structure

```
duck_lakehouse/
├── docs/
│   └── design.md                       # This document
├── data/
│   └── generated/                      # Output from data generator
│       └── Flu_Vaccinations_v5_X99999_20250413T10000000.csv
├── mesh/
│   ├── inbox/                          # MESH inbox (simulates supplier send)
│   ├── processing/                     # Files being ingested
│   ├── archive/                       # Successfully processed files
│   ├── error/                         # Failed files
│   └── logs/                          # Ingestion logs
├── catalog/                            # DuckLake catalog storage
│   └── catalog.ducklake               # SQLite catalog file
├── lake/                               # DuckLake data storage
│   └── (Parquet files managed by DuckLake)
├── generator/
│   ├── __init__.py
│   ├── generate.py                     # Main data generator
│   ├── patients.py                     # Realistic patient data (NHS numbers, PDS fields)
│   ├── vaccinations.py                 # Vaccination event generation (SNOMED, dm+d codes)
│   └── config.py                       # Generator settings (vaccine types, batch sizes)
├── mesh_simulator/
│   ├── __init__.py
│   ├── watcher.py                      # File system watcher (polling)
│   ├── validator.py                    # v5.1 header/format validation
│   └── config.py                       # Simulator settings (poll interval, directories)
├── ingestion/
│   ├── __init__.py
│   ├── ingest.py                       # CSV → DuckLake loading
│   └── init_catalog.py                 # DuckLake catalog + table initialization
├── dbt_project/
│   ├── dbt_project.yml                 # dbt config (ducklake target)
│   ├── profiles.yml                    # Connection profile
│   ├── packages.yml                    # dbt packages
│   ├── models/
│   │   ├── staging/
│   │   │   ├── _staging__models.yml
│   │   │   ├── _staging__sources.yml
│   │   │   └── stg_vaccinations.sql
│   │   ├── intermediate/
│   │   │   ├── _intermediate__models.yml
│   │   │   ├── int_vaccinations_deduped.sql
│   │   │   └── int_vaccinations_enriched.sql
│   │   └── marts/
│   │       ├── _marts__models.yml
│   │       ├── mart_vaccinations_by_site.sql
│   │       ├── mart_vaccinations_by_type.sql
│   │       └── mart_patient_history.sql
│   ├── tests/                          # Custom dbt tests
│   │   ├── test_nhs_number_format.sql
│   │   └── test_datetime_format.sql
│   └── macros/
│       └── dedup_latest.sql            # Macro for latest-record deduplication
├── docker/
│   ├── docker-compose.yml              # Local stack orchestration
│   ├── Dockerfile.ducklake             # DuckDB + ducklake extension
│   └── entrypoint.sh                   # Container init script
├── scripts/
│   ├── init.sh                         # Initialize catalog and tables
│   ├── generate_data.sh                # Run data generator
│   ├── ingest.sh                       # Run ingestion (one-shot)
│   └── run_dbt.sh                      # Run dbt models + tests
├── Makefile                            # Top-level task runner
├── pyproject.toml                      # Python dependencies
└── README.md                           # Quickstart guide
```

---

## 4. Implementation Plan

### Phase 1: Foundation (Data Generator + DuckLake Init)

**Goal**: Generate v5.1 CSV data and load it into DuckLake.

1. Create `duck_lakehouse/` directory structure
2. Implement `generator/generate.py`:
   - Read SMOMED/dm+d code reference data from existing `schemas/` and `enriched/`
   - Generate realistic patient records (8+ patients from existing SAMPLE_PATIENTS)
   - Generate vaccination events per v5.1 spec with correct pipe-delimited CSV format
   - Support configurable vaccination types (COVID, Flu, RSV, HPV, MMR)
   - Produce one file per vaccination type per run
3. Implement `ingestion/init_catalog.py`:
   - Create DuckLake catalog with SQLite backend
   - Attach DuckLake storage
   - Create `raw_vaccinations` table (all VARCHAR columns matching v5.1 header)
   - Create `raw_vaccinations_archive` table
4. Implement `ingestion/ingest.py`:
   - Read pipe-delimited CSV from file path
   - Validate header row against v5.1 field list
   - Load into `raw_vaccinations` via DuckDB `read_csv_auto` with pipe delimiter
   - Append metadata to archive table
5. Add `Makefile` with `init` and `generate` targets
6. Create Docker Compose with DuckLake container
7. Test: generate → ingest → query raw data

### Phase 2: MESH Simulator

**Goal**: Simulate the MESH file transfer flow.

1. Implement `mesh_simulator/watcher.py`:
   - Poll `mesh/inbox/` at configurable interval
   - Move files to `processing/`
   - Call ingestion on each file
   - Move to `archive/` or `error/` based on result
2. Implement `mesh_simulator/validator.py`:
   - Validate header row matches v5.1 field names exactly
   - Validate field count (34 columns)
   - Validate encoding (UTF-8, no embedded pipe chars)
   - Validate record terminator (CRLF)
3. Wire MESH simulator into Docker Compose
4. Add `make send` (copy generated files to inbox) and `make ingest` targets
5. Test: generate → send → ingest → verify archive

### Phase 3: dbt Transforms

**Goal**: Build staging → intermediate → marts pipeline.

1. Initialize dbt project with `dbt-duckdb` adapter
2. Configure `profiles.yml` for DuckLake connection
3. Build staging models:
   - `stg_vaccinations.sql`: type casting, renaming, metadata
   - `_staging__sources.yml`: source table definition
   - `_staging__models.yml`: column tests (v5 field validation)
4. Build intermediate models:
   - `int_vaccinations_deduped.sql`: dedup by UNIQUE_ID (latest RECORDED_DATE)
   - `int_vaccinations_enriched.sql`: derive vaccine type, SNOMED lookups
5. Build mart models:
   - `mart_vaccinations_by_site.sql`
   - `mart_vaccinations_by_type.sql`
   - `mart_patient_history.sql`
6. Write custom tests: NHS number format, datetime format
7. Add `make dbt-run` and `make dbt-test` targets
8. Test: full pipeline generate → send → ingest → dbt-run → dbt-test

### Phase 4: Docker Compose + Smoke Test

**Goal**: Full local stack with one-command smoke test.

1. Finalize Docker Compose with all services
2. Write `scripts/init.sh`, `scripts/generate_data.sh`, `scripts/ingest.sh`, `scripts/run_dbt.sh`
3. Wire `make smoke` target for end-to-end test
4. Write `duck_lakehouse/README.md` with quickstart
5. Test: `make smoke` from clean state

### Phase 5: AWS Design Notes (Documentation Only)

**Goal**: Document AWS expansion path (not implement).

1. Add AWS architecture notes to design doc
2. Draft Terraform module interfaces (no implementation)
3. Document S3 + PostgreSQL + ECS patterns
4. Reference terraform-aws-mesh-client integration points

---

## 5. Design Decisions

### Why DuckLake over plain DuckDB?
- ACID transactions on ingestion (rollback on failure)
- Parquet-based storage (interoperable, queryable by other engines)
- Catalog separation (SQLite locally, PostgreSQL on AWS)
- Versioned data — supports time-travel queries
- Direct upgrade path to AWS (swap catalog → PostgreSQL, storage → S3)

### Why pipe-delimited CSV for raw storage?
- Matches NHS MESH spec exactly (section 3.4)
- Preserves raw input for audit trail
- Enables re-processing from archive if pipeline logic changes
- Staging layer in dbt handles type casting — raw layer stays faithful to source

### Why all-VARCHAR in raw table?
- Avoids type errors on ingestion (bad data doesn't fail the load)
- Enables validation in dbt tests (explicit, documented, testable)
- Matches lakehouse best practice: raw → typed → enriched
- Easier debugging — can inspect malformed data in raw table

### Why dbt-duckdb and not plain SQL scripts?
- Declarative models with automatic dependency graph
- Built-in testing framework (v5 field validation as tests)
- Documentation generation
- Industry-standard tooling (team familiarity)
- Incremental model support for large volumes

---

## 6. Key Reference Data

The existing repository contains essential reference data that the generator and dbt models will leverage:

- `schemas/vaccinations.vaccinations.json` — Full field schema (34+ fields including DPS-derived fields)
- `enriched/FIELD_DICTIONARY.md` — Human-readable field reference with descriptions
- `enriched/field_processing_context.json` — Validation rules and derivations
- `schemas/flu_vaccinations.vaccinations.json` — Flu-specific schema
- `schemas/hpv_vaccinations.hpv.json` — HPV-specific schema
- `schemas/mmr_vaccinations.mmr.json` — MMR-specific schema
- `schemas/vaccinations.rsv_vaccinations.json` — RSV-specific schema
- `generate_sample_data.py` — Existing sample data generator (reference for SNOMED codes, patient data)

The v5.1 specification is available at:
`extracted_docs/NHSE Daily Vaccination Events (In-Bound) Extract Technical Specification v5.1_FINAL_extracted.md`

---

## 7. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| DuckLake extension compatibility with DuckDB version | Ingestion fails | Pin DuckDB + ducklake versions in Dockerfile |
| Pipe characters in data fields | File rejected by MESH/validator | Generator escapes pipes; validator checks for embedded pipes |
| Large file ingestion memory | OOM on constrained containers | Stream CSV in batches (DuckDB auto-handling for read_csv) |
| dbt-duckdb ↔ DuckLake compatibility | Transform failures | Test with exact version matrix before committing |
| Null handling differences between DuckDB and v5 spec | Data quality issues | Staging layer explicitly handles null per v5 spec (consecutive delimiters) |