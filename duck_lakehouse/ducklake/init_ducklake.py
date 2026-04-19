#!/usr/bin/env python3
"""
DuckLake Initialisation Script

Creates a DuckLake warehouse using DuckDB as the catalog backend
and local filesystem as data storage.

DuckLake v1.0 uses the ducklake: schema prefix:
  ATTACH 'ducklake:catalog.ducklake' AS vaccination_lake
  (DATA_PATH '/path/to/data')

Reference: https://ducklake.select/docs/
"""

import duckdb
import os
from pathlib import Path


def init_ducklake(
    lake_name: str = "vaccination_lake",
    catalog_path: str = None,
    data_path: str = None,
    base_dir: str = None,
) -> duckdb.DuckDBPyConnection:
    """Initialise a DuckLake warehouse.

    Paths are resolved in this order:
      1. Explicit catalog_path / data_path arguments
      2. DUCKLAKE_CATALOG / DUCKLAKE_DATA environment variables
      3. Auto-detect from /app/data (production) or duck_lakehouse/ducklake (local)
    """
    env_catalog = os.environ.get("DUCKLAKE_CATALOG")
    env_data = os.environ.get("DUCKLAKE_DATA")

    if base_dir is None:
        if env_catalog or Path("/app/data").exists():
            base_dir = "/app/data"
        else:
            base_dir = "duck_lakehouse/ducklake"

    base = Path(base_dir)
    if catalog_path is None:
        catalog_path = env_catalog or str(base / "catalog" / f"{lake_name}.ducklake")
    if data_path is None:
        if env_data:
            data_path = env_data
        elif env_catalog or Path("/app/data").exists():
            data_path = str(base / "parquet")
        else:
            data_path = str(base / "data")

    Path(catalog_path).parent.mkdir(parents=True, exist_ok=True)
    Path(data_path).mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect()

    conn.execute("INSTALL ducklake")
    conn.execute("LOAD ducklake")

    conn.execute(f"""
        ATTACH 'ducklake:{catalog_path}' AS {lake_name}
        (DATA_PATH '{data_path}', OVERRIDE_DATA_PATH true)
    """)

    conn.execute(f"USE {lake_name}")
    print(f"DuckLake '{lake_name}' attached")
    print(f"  Catalog: {catalog_path}")
    print(f"  Data:    {data_path}")
    return conn


def create_schemas(
    conn: duckdb.DuckDBPyConnection, lake_name: str = "vaccination_lake"
):
    conn.execute(f"USE {lake_name}")
    for schema in [
        "staging",
        "intermediate",
        "marts",
        "reference",
        "main_staging",
        "main_intermediate",
        "main_marts",
    ]:
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    print(
        "Schemas created: staging, intermediate, marts, reference, main_staging, main_intermediate, main_marts"
    )


def create_staging_tables(
    conn: duckdb.DuckDBPyConnection, lake_name: str = "vaccination_lake"
):
    conn.execute(f"USE {lake_name}.staging")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS stg_vaccinations (
            _source_file VARCHAR,
            _loaded_at TIMESTAMP DEFAULT current_timestamp,
            NHS_NUMBER VARCHAR,
            PERSON_FORENAME VARCHAR,
            PERSON_SURNAME VARCHAR,
            PERSON_DOB VARCHAR,
            PERSON_GENDER_CODE VARCHAR,
            PERSON_POSTCODE VARCHAR,
            DATE_AND_TIME VARCHAR,
            SITE_CODE VARCHAR,
            SITE_CODE_TYPE_URI VARCHAR,
            UNIQUE_ID VARCHAR,
            UNIQUE_ID_URI VARCHAR,
            ACTION_FLAG VARCHAR,
            PERFORMING_PROFESSIONAL_FORENAME VARCHAR,
            PERFORMING_PROFESSIONAL_SURNAME VARCHAR,
            RECORDED_DATE VARCHAR,
            PRIMARY_SOURCE VARCHAR,
            VACCINATION_PROCEDURE_CODE VARCHAR,
            VACCINATION_PROCEDURE_TERM VARCHAR,
            DOSE_SEQUENCE VARCHAR,
            VACCINE_PRODUCT_CODE VARCHAR,
            VACCINE_PRODUCT_TERM VARCHAR,
            VACCINE_MANUFACTURER VARCHAR,
            BATCH_NUMBER VARCHAR,
            EXPIRY_DATE VARCHAR,
            SITE_OF_VACCINATION_CODE VARCHAR,
            SITE_OF_VACCINATION_TERM VARCHAR,
            ROUTE_OF_VACCINATION_CODE VARCHAR,
            ROUTE_OF_VACCINATION_TERM VARCHAR,
            DOSE_AMOUNT VARCHAR,
            DOSE_UNIT_CODE VARCHAR,
            DOSE_UNIT_TERM VARCHAR,
            INDICATION_CODE VARCHAR,
            LOCATION_CODE VARCHAR,
            LOCATION_CODE_TYPE_URI VARCHAR
        )
    """)
    print("staging.stg_vaccinations created")


def create_intermediate_tables(
    conn: duckdb.DuckDBPyConnection, lake_name: str = "vaccination_lake"
):
    conn.execute(f"USE {lake_name}.intermediate")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS int_validated_vaccinations (
            _source_file VARCHAR,
            _loaded_at TIMESTAMP,
            nhs_number VARCHAR,
            person_forename VARCHAR,
            person_surname VARCHAR,
            person_dob DATE,
            person_gender_code VARCHAR,
            person_postcode VARCHAR,
            vaccination_datetime TIMESTAMP,
            site_code VARCHAR,
            site_code_type_uri VARCHAR,
            unique_id VARCHAR,
            unique_id_uri VARCHAR,
            action_flag VARCHAR,
            performing_professional_forename VARCHAR,
            performing_professional_surname VARCHAR,
            recorded_date DATE,
            primary_source BOOLEAN,
            vaccination_procedure_code VARCHAR,
            vaccination_procedure_term VARCHAR,
            dose_sequence INTEGER,
            vaccine_product_code VARCHAR,
            vaccine_product_term VARCHAR,
            vaccine_manufacturer VARCHAR,
            batch_number VARCHAR,
            expiry_date DATE,
            site_of_vaccination_code VARCHAR,
            site_of_vaccination_term VARCHAR,
            route_of_vaccination_code VARCHAR,
            route_of_vaccination_term VARCHAR,
            dose_amount DOUBLE,
            dose_unit_code VARCHAR,
            dose_unit_term VARCHAR,
            indication_code VARCHAR,
            location_code VARCHAR,
            location_code_type_uri VARCHAR,
            validation_status VARCHAR
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS int_deduplicated_vaccinations (
            _source_file VARCHAR,
            _loaded_at TIMESTAMP,
            nhs_number VARCHAR,
            person_forename VARCHAR,
            person_surname VARCHAR,
            person_dob DATE,
            person_gender_code VARCHAR,
            person_postcode VARCHAR,
            vaccination_datetime TIMESTAMP,
            site_code VARCHAR,
            site_code_type_uri VARCHAR,
            unique_id VARCHAR,
            unique_id_uri VARCHAR,
            action_flag VARCHAR,
            performing_professional_forename VARCHAR,
            performing_professional_surname VARCHAR,
            recorded_date DATE,
            primary_source BOOLEAN,
            vaccination_procedure_code VARCHAR,
            vaccination_procedure_term VARCHAR,
            dose_sequence INTEGER,
            vaccine_product_code VARCHAR,
            vaccine_product_term VARCHAR,
            vaccine_manufacturer VARCHAR,
            batch_number VARCHAR,
            expiry_date DATE,
            site_of_vaccination_code VARCHAR,
            site_of_vaccination_term VARCHAR,
            route_of_vaccination_code VARCHAR,
            route_of_vaccination_term VARCHAR,
            dose_amount DOUBLE,
            dose_unit_code VARCHAR,
            dose_unit_term VARCHAR,
            indication_code VARCHAR,
            location_code VARCHAR,
            location_code_type_uri VARCHAR,
            validation_status VARCHAR,
            _row_rank BIGINT
        )
    """)
    print("intermediate tables created")


def create_mart_tables(
    conn: duckdb.DuckDBPyConnection, lake_name: str = "vaccination_lake"
):
    conn.execute(f"USE {lake_name}.marts")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS fct_vaccination_events (
            vaccination_event_id VARCHAR,
            nhs_number VARCHAR,
            person_forename VARCHAR,
            person_surname VARCHAR,
            person_dob DATE,
            person_gender_code VARCHAR,
            person_postcode VARCHAR,
            vaccination_datetime TIMESTAMP,
            site_code VARCHAR,
            site_code_type_uri VARCHAR,
            unique_id VARCHAR,
            unique_id_uri VARCHAR,
            action_flag VARCHAR,
            recorded_date DATE,
            primary_source BOOLEAN,
            vaccination_procedure_code VARCHAR,
            vaccination_procedure_term VARCHAR,
            dose_sequence INTEGER,
            vaccine_product_code VARCHAR,
            vaccine_product_term VARCHAR,
            vaccine_manufacturer VARCHAR,
            batch_number VARCHAR,
            expiry_date DATE,
            site_of_vaccination_code VARCHAR,
            site_of_vaccination_term VARCHAR,
            route_of_vaccination_code VARCHAR,
            route_of_vaccination_term VARCHAR,
            dose_amount DOUBLE,
            dose_unit_code VARCHAR,
            dose_unit_term VARCHAR,
            indication_code VARCHAR,
            location_code VARCHAR,
            location_code_type_uri VARCHAR,
            _valid_from TIMESTAMP DEFAULT current_timestamp,
            _is_current BOOLEAN DEFAULT TRUE,
            _loaded_at TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS dim_patient (
            patient_id INTEGER,
            nhs_number VARCHAR,
            person_forename VARCHAR,
            person_surname VARCHAR,
            person_dob DATE,
            person_gender_code VARCHAR,
            person_postcode VARCHAR,
            _valid_from TIMESTAMP DEFAULT current_timestamp,
            _is_current BOOLEAN DEFAULT TRUE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS dim_site (
            site_id INTEGER,
            site_code VARCHAR,
            site_code_type_uri VARCHAR,
            location_code VARCHAR,
            location_code_type_uri VARCHAR,
            _valid_from TIMESTAMP DEFAULT current_timestamp,
            _is_current BOOLEAN DEFAULT TRUE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS dim_vaccine (
            vaccine_id INTEGER,
            vaccine_product_code VARCHAR,
            vaccine_product_term VARCHAR,
            vaccine_manufacturer VARCHAR,
            dose_unit_code VARCHAR,
            dose_unit_term VARCHAR,
            _valid_from TIMESTAMP DEFAULT current_timestamp,
            _is_current BOOLEAN DEFAULT TRUE
        )
    """)

    print(
        "marts tables created: fct_vaccination_events, dim_patient, dim_site, dim_vaccine"
    )


def create_reference_tables(
    conn: duckdb.DuckDBPyConnection, lake_name: str = "vaccination_lake"
):
    conn.execute(f"USE {lake_name}.reference")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ref_file_audit (
            file_id INTEGER,
            filename VARCHAR,
            message_id VARCHAR,
            file_size BIGINT,
            checksum VARCHAR,
            received_at TIMESTAMP,
            processed_at TIMESTAMP,
            status VARCHAR,
            record_count INTEGER,
            error_message VARCHAR
        )
    """)
    print("reference.ref_file_audit created")


def main(catalog_path=None, data_path=None):
    conn = init_ducklake(catalog_path=catalog_path, data_path=data_path)
    create_schemas(conn)
    create_staging_tables(conn)
    create_intermediate_tables(conn)
    create_mart_tables(conn)
    create_reference_tables(conn)

    result = conn.execute("SHOW ALL TABLES").fetchall()
    print(f"\nTotal tables: {len(result)}")
    for row in result:
        print(f"  {row[0]}.{row[1]}.{row[2]}")

    conn.close()
    print("\nDuckLake initialisation complete")


if __name__ == "__main__":
    main()
