import duckdb
import pytest

from duck_lakehouse.data_generator.generate_v5_data import generate_dataset
from duck_lakehouse.ducklake.init_ducklake import (
    create_intermediate_tables,
    create_mart_tables,
    create_reference_tables,
    create_schemas,
    create_staging_tables,
    init_ducklake,
)
from duck_lakehouse.mesh_simulator.mesh_simulator import MESHSimulator


@pytest.fixture
def pipeline_dirs(ducklake_dirs, mesh_dirs):
    return {
        **ducklake_dirs,
        "archive_dir": str(mesh_dirs["archive"]),
        "inbox_dir": str(mesh_dirs["inbox"]),
        "processing_dir": str(mesh_dirs["processing"]),
        "logs_dir": str(mesh_dirs["logs"]),
    }


class TestFullPipeline:
    def test_generate_produces_csv_files(self, pipeline_dirs, mesh_dirs):
        for vtype in ["Flu", "COVID"]:
            path = generate_dataset(
                vtype,
                num_records=10,
                output_dir=str(mesh_dirs["inbox"]),
                org_code="TEST",
            )
            assert path.exists()
            content = path.read_text(encoding="utf-8")
            assert len(content) > 0
            lines = (
                content.strip().split("\r\n")
                if "\r\n" in content
                else content.strip().split("\n")
            )
            assert len(lines) == 11

    def test_mesh_processes_files(self, pipeline_dirs, mesh_dirs):
        from duck_lakehouse.data_generator.generate_v5_data import generate_dataset

        generate_dataset(
            "Flu", num_records=5, output_dir=str(mesh_dirs["inbox"]), org_code="TEST"
        )

        sim = MESHSimulator(base_dir=str(mesh_dirs["archive"].parent))
        results = sim.process_all()

        assert len(results) >= 1
        for filename, success in results:
            assert success, f"Failed to process {filename}"

        assert len(list(mesh_dirs["archive"].glob("*.csv"))) >= 1
        assert len(list(mesh_dirs["inbox"].glob("*.csv"))) == 0

    def test_init_then_ingest(self, pipeline_dirs, mesh_dirs):
        generate_dataset(
            "Flu", num_records=5, output_dir=str(mesh_dirs["inbox"]), org_code="TEST"
        )

        sim = MESHSimulator(base_dir=str(mesh_dirs["archive"].parent))
        sim.process_all()

        from duck_lakehouse.ducklake.ingest import ingest_files

        conn = init_ducklake(
            catalog_path=pipeline_dirs["catalog_path"],
            data_path=pipeline_dirs["data_path"],
        )
        create_schemas(conn)
        create_staging_tables(conn)
        create_intermediate_tables(conn)
        create_mart_tables(conn)
        create_reference_tables(conn)
        conn.close()

        count = ingest_files(
            archive_dir=str(mesh_dirs["archive"]),
            catalog_path=pipeline_dirs["catalog_path"],
            data_path=pipeline_dirs["data_path"],
        )
        assert count >= 5

        verify_conn = duckdb.connect()
        verify_conn.execute("INSTALL ducklake")
        verify_conn.execute("LOAD ducklake")
        verify_conn.execute(
            f"ATTACH 'ducklake:{pipeline_dirs['catalog_path']}' AS vaccination_lake "
            f"(READ_ONLY, DATA_PATH '{pipeline_dirs['data_path']}')"
        )

        row_count = verify_conn.execute(
            "SELECT COUNT(*) FROM vaccination_lake.staging.stg_vaccinations"
        ).fetchone()[0]
        assert row_count >= 5

        tables = verify_conn.execute(
            "SELECT schema_name, table_name FROM duckdb_tables() WHERE database_name = 'vaccination_lake'"
        ).fetchall()
        table_set = {(s, t) for s, t in tables}
        assert ("staging", "stg_vaccinations") in table_set

        verify_conn.close()

    def test_ingest_multiple_vaccine_types(self, pipeline_dirs, mesh_dirs):
        for vtype in ["Flu", "COVID", "RSV"]:
            generate_dataset(
                vtype,
                num_records=3,
                output_dir=str(mesh_dirs["inbox"]),
                org_code="TEST",
            )

        sim = MESHSimulator(base_dir=str(mesh_dirs["archive"].parent))
        sim.process_all()

        from duck_lakehouse.ducklake.ingest import ingest_files

        conn = init_ducklake(
            catalog_path=pipeline_dirs["catalog_path"],
            data_path=pipeline_dirs["data_path"],
        )
        create_schemas(conn)
        create_staging_tables(conn)
        conn.close()

        count = ingest_files(
            archive_dir=str(mesh_dirs["archive"]),
            catalog_path=pipeline_dirs["catalog_path"],
            data_path=pipeline_dirs["data_path"],
        )
        assert count >= 9

    def test_reingest_does_not_duplicate(self, pipeline_dirs, mesh_dirs):
        generate_dataset(
            "Flu", num_records=3, output_dir=str(mesh_dirs["inbox"]), org_code="TEST"
        )

        sim = MESHSimulator(base_dir=str(mesh_dirs["archive"].parent))
        sim.process_all()

        from duck_lakehouse.ducklake.ingest import ingest_files

        conn = init_ducklake(
            catalog_path=pipeline_dirs["catalog_path"],
            data_path=pipeline_dirs["data_path"],
        )
        create_schemas(conn)
        create_staging_tables(conn)
        conn.close()

        count1 = ingest_files(
            archive_dir=str(mesh_dirs["archive"]),
            catalog_path=pipeline_dirs["catalog_path"],
            data_path=pipeline_dirs["data_path"],
        )
        assert count1 >= 3

        count2 = ingest_files(
            archive_dir=str(mesh_dirs["archive"]),
            catalog_path=pipeline_dirs["catalog_path"],
            data_path=pipeline_dirs["data_path"],
        )
        assert count2 >= 3

        verify_conn = duckdb.connect()
        verify_conn.execute("INSTALL ducklake")
        verify_conn.execute("LOAD ducklake")
        verify_conn.execute(
            f"ATTACH 'ducklake:{pipeline_dirs['catalog_path']}' AS vaccination_lake "
            f"(READ_ONLY, DATA_PATH '{pipeline_dirs['data_path']}')"
        )
        total = verify_conn.execute(
            "SELECT COUNT(*) FROM vaccination_lake.staging.stg_vaccinations"
        ).fetchone()[0]
        verify_conn.close()
        assert total == count1 + count2
