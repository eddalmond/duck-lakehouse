import duckdb
import pytest

from duck_lakehouse.ducklake.init_ducklake import (
    create_intermediate_tables,
    create_mart_tables,
    create_reference_tables,
    create_schemas,
    create_staging_tables,
    init_ducklake,
)


@pytest.fixture
def ducklake_conn(ducklake_dirs):
    catalog_path = ducklake_dirs["catalog_path"]
    data_path = ducklake_dirs["data_path"]
    conn = init_ducklake(catalog_path=catalog_path, data_path=data_path)
    yield conn
    try:
        conn.close()
    except Exception:
        pass


class TestInitDuckLake:
    def test_init_creates_catalog(self, ducklake_dirs):
        conn = init_ducklake(
            catalog_path=ducklake_dirs["catalog_path"],
            data_path=ducklake_dirs["data_path"],
        )
        assert conn is not None
        conn.execute("SHOW ALL TABLES").fetchall()
        conn.close()

    def test_init_idempotent(self, ducklake_dirs):
        conn1 = init_ducklake(
            catalog_path=ducklake_dirs["catalog_path"],
            data_path=ducklake_dirs["data_path"],
        )
        conn1.close()
        conn2 = init_ducklake(
            catalog_path=ducklake_dirs["catalog_path"],
            data_path=ducklake_dirs["data_path"],
        )
        result = conn2.execute("SHOW ALL TABLES").fetchall()
        conn2.close()
        assert len(result) > 0

    def test_init_creates_data_dir(self, tmp_dir):
        data_path = tmp_dir / "custom_data"
        catalog_path = str(tmp_dir / "catalog" / "test.ducklake")
        conn = init_ducklake(catalog_path=catalog_path, data_path=str(data_path))
        assert data_path.exists()
        conn.close()

    def test_init_env_override(self, ducklake_dirs):
        import os

        os.environ["DUCKLAKE_CATALOG"] = ducklake_dirs["catalog_path"]
        os.environ["DUCKLAKE_DATA"] = ducklake_dirs["data_path"]
        conn = init_ducklake()
        assert conn is not None
        conn.close()


class TestCreateSchemas:
    def test_creates_all_schemas(self, ducklake_conn):
        create_schemas(ducklake_conn)
        schemas = ducklake_conn.execute(
            "SELECT schema_name FROM duckdb_schemas() WHERE database_name = 'vaccination_lake'"
        ).fetchall()
        schema_names = {s[0] for s in schemas}
        for expected in ["staging", "intermediate", "marts", "reference"]:
            assert expected in schema_names, f"Missing schema: {expected}"


class TestCreateStagingTables:
    def test_creates_stg_vaccinations(self, ducklake_conn):
        create_schemas(ducklake_conn)
        create_staging_tables(ducklake_conn)
        tables = ducklake_conn.execute(
            "SELECT table_name FROM duckdb_tables() WHERE database_name = 'vaccination_lake' AND schema_name = 'staging'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        assert "stg_vaccinations" in table_names

    def test_stg_vaccinations_columns(self, ducklake_conn):
        create_schemas(ducklake_conn)
        create_staging_tables(ducklake_conn)
        cols = ducklake_conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'stg_vaccinations' AND table_schema = 'staging'"
        ).fetchall()
        col_names = {c[0] for c in cols}
        assert "NHS_NUMBER" in col_names
        assert "_source_file" in col_names
        assert "_loaded_at" in col_names


class TestCreateIntermediateTables:
    def test_creates_intermediate_tables(self, ducklake_conn):
        create_schemas(ducklake_conn)
        create_intermediate_tables(ducklake_conn)
        tables = ducklake_conn.execute(
            "SELECT table_name FROM duckdb_tables() WHERE database_name = 'vaccination_lake' AND schema_name = 'intermediate'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        assert "int_validated_vaccinations" in table_names
        assert "int_deduplicated_vaccinations" in table_names


class TestCreateMartTables:
    def test_creates_mart_tables(self, ducklake_conn):
        create_schemas(ducklake_conn)
        create_mart_tables(ducklake_conn)
        tables = ducklake_conn.execute(
            "SELECT table_name FROM duckdb_tables() WHERE database_name = 'vaccination_lake' AND schema_name = 'marts'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        assert "fct_vaccination_events" in table_names
        assert "dim_patient" in table_names
        assert "dim_site" in table_names
        assert "dim_vaccine" in table_names


class TestCreateReferenceTables:
    def test_creates_ref_file_audit(self, ducklake_conn):
        create_schemas(ducklake_conn)
        create_reference_tables(ducklake_conn)
        tables = ducklake_conn.execute(
            "SELECT table_name FROM duckdb_tables() WHERE database_name = 'vaccination_lake' AND schema_name = 'reference'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        assert "ref_file_audit" in table_names


class TestFullInit:
    def test_main_creates_all_tables(self, ducklake_dirs):
        from duck_lakehouse.ducklake.init_ducklake import main

        main(
            catalog_path=ducklake_dirs["catalog_path"],
            data_path=ducklake_dirs["data_path"],
        )

        conn = duckdb.connect()
        conn.execute("INSTALL ducklake")
        conn.execute("LOAD ducklake")
        conn.execute(
            f"ATTACH 'ducklake:{ducklake_dirs['catalog_path']}' AS vaccination_lake "
            f"(READ_ONLY, DATA_PATH '{ducklake_dirs['data_path']}')"
        )
        tables = conn.execute(
            "SELECT schema_name, table_name FROM duckdb_tables() WHERE database_name = 'vaccination_lake'"
        ).fetchall()
        conn.close()

        assert len(tables) >= 5
        schema_table = {(s, t) for s, t in tables}
        assert ("staging", "stg_vaccinations") in schema_table
        assert ("marts", "fct_vaccination_events") in schema_table
