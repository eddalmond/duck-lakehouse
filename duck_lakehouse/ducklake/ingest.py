#!/usr/bin/env python3
"""
Ingest MESH-processed CSV files into DuckLake staging layer.

Reads pipe-delimited v5 CSV files from the MESH archive directory
and loads them into staging.stg_vaccinations.
"""

import csv
import os
import re
from datetime import datetime
from pathlib import Path

import duckdb


V5_FIELDS = [
    "NHS_NUMBER", "PERSON_FORENAME", "PERSON_SURNAME", "PERSON_DOB",
    "PERSON_GENDER_CODE", "PERSON_POSTCODE", "DATE_AND_TIME", "SITE_CODE",
    "SITE_CODE_TYPE_URI", "UNIQUE_ID", "UNIQUE_ID_URI", "ACTION_FLAG",
    "PERFORMING_PROFESSIONAL_FORENAME", "PERFORMING_PROFESSIONAL_SURNAME",
    "RECORDED_DATE", "PRIMARY_SOURCE", "VACCINATION_PROCEDURE_CODE",
    "VACCINATION_PROCEDURE_TERM", "DOSE_SEQUENCE", "VACCINE_PRODUCT_CODE",
    "VACCINE_PRODUCT_TERM", "VACCINE_MANUFACTURER", "BATCH_NUMBER",
    "EXPIRY_DATE", "SITE_OF_VACCINATION_CODE", "SITE_OF_VACCINATION_TERM",
    "ROUTE_OF_VACCINATION_CODE", "ROUTE_OF_VACCINATION_TERM",
    "DOSE_AMOUNT", "DOSE_UNIT_CODE", "DOSE_UNIT_TERM",
    "INDICATION_CODE", "LOCATION_CODE", "LOCATION_CODE_TYPE_URI",
]


def parse_pipe_csv(filepath: Path) -> list:
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    lines = raw.strip().split("\r\n") if "\r\n" in raw else raw.strip().split("\n")
    if not lines:
        return records

    field_re = re.compile(r'"([^"]*)"')
    header_fields = [m.group(1) for m in field_re.finditer(lines[0])]

    for line in lines[1:]:
        if not line.strip():
            continue
        values = [m.group(1) for m in field_re.finditer(line)]
        record = dict(zip(header_fields, values))
        record["_source_file"] = filepath.name
        records.append(record)

    return records


def ingest_files(
    archive_dir: str = None,
    lake_name: str = "vaccination_lake",
    catalog_path: str = None,
    data_path: str = None,
    base_dir: str = None,
):
    # Resolve archive dir from env or default
    if archive_dir is None:
        env_archive = os.environ.get("MESH_ARCHIVE_DIR")
        if env_archive:
            archive_dir = env_archive
        elif Path("/app/mesh_simulator/archive").exists():
            archive_dir = "/app/mesh_simulator/archive"
        else:
            archive_dir = "duck_lakehouse/mesh_simulator/archive"
    archive = Path(archive_dir)
    if not archive.exists():
        print(f"No archive directory: {archive}")
        return 0

    csv_files = sorted(archive.glob("*.csv"))
    if not csv_files:
        print("No CSV files in archive")
        return 0

    from duck_lakehouse.ducklake.init_ducklake import init_ducklake

    conn = init_ducklake(
        lake_name=lake_name,
        catalog_path=catalog_path,
        data_path=data_path,
    )

    conn.execute(f"USE {lake_name}.staging")

    total = 0
    for csv_file in csv_files:
        records = parse_pipe_csv(csv_file)
        if not records:
            print(f"  SKIP {csv_file.name} (empty)")
            continue

        cols = ["_source_file"] + V5_FIELDS
        placeholders = ", ".join(["?" for _ in cols])
        insert_sql = f"""
            INSERT INTO stg_vaccinations ({', '.join(cols)})
            VALUES ({placeholders})
        """
        for record in records:
            row = record.get("_source_file", "")
            values = [row] + [record.get(f, "") for f in V5_FIELDS]
            conn.execute(insert_sql, values)

        total += len(records)
        print(f"  Loaded {len(records)} records from {csv_file.name}")

    conn.close()
    print(f"\nIngested {total} total records from {len(csv_files)} files")
    return total


if __name__ == "__main__":
    ingest_files()