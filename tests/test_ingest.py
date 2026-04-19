import pytest

from duck_lakehouse.ducklake.ingest import V5_FIELDS, parse_pipe_csv, ingest_files
from duck_lakehouse.ducklake.init_ducklake import (
    init_ducklake,
    create_schemas,
    create_staging_tables,
)


@pytest.fixture
def setup_ducklake(ducklake_dirs):
    catalog_path = ducklake_dirs["catalog_path"]
    data_path = ducklake_dirs["data_path"]
    conn = init_ducklake(catalog_path=catalog_path, data_path=data_path)
    create_schemas(conn)
    create_staging_tables(conn)
    conn.close()
    return ducklake_dirs


class TestParsePipeCsv:
    def test_parse_valid_csv(self, sample_csv_file):
        records = parse_pipe_csv(sample_csv_file)
        assert len(records) == 2

    def test_parsed_record_fields(self, sample_csv_file):
        records = parse_pipe_csv(sample_csv_file)
        rec = records[0]
        assert rec["NHS_NUMBER"] == "9990000001"
        assert rec["PERSON_FORENAME"] == "Oliver"
        assert rec["PERSON_SURNAME"] == "Smith"
        assert rec["ACTION_FLAG"] == "new"

    def test_parsed_has_source_file(self, sample_csv_file):
        records = parse_pipe_csv(sample_csv_file)
        for rec in records:
            assert "_source_file" in rec
            assert rec["_source_file"] == sample_csv_file.name

    def test_parse_all_v5_fields_present(self, sample_csv_file):
        records = parse_pipe_csv(sample_csv_file)
        rec = records[0]
        for field in V5_FIELDS:
            assert field in rec, f"Missing field: {field}"

    def test_parse_empty_file(self, tmp_dir):
        filepath = tmp_dir / "empty.csv"
        filepath.write_text("", encoding="utf-8")
        records = parse_pipe_csv(filepath)
        assert records == []

    def test_parse_header_only(self, tmp_dir):
        header = '"NHS_NUMBER"|"PERSON_FORENAME"|"PERSON_SURNAME"\r\n'
        filepath = tmp_dir / "header_only.csv"
        filepath.write_text(header, encoding="utf-8")
        records = parse_pipe_csv(filepath)
        assert records == []

    def test_parse_second_record(self, sample_csv_file):
        records = parse_pipe_csv(sample_csv_file)
        rec = records[1]
        assert rec["NHS_NUMBER"] == "9990000002"
        assert rec["PERSON_FORENAME"] == "Amelia"


class TestIngestFiles:
    def test_ingest_from_archive(self, setup_ducklake, sample_csv_file, mesh_dirs):
        result = ingest_files(
            archive_dir=str(mesh_dirs["archive"]),
            catalog_path=setup_ducklake["catalog_path"],
            data_path=setup_ducklake["data_path"],
        )
        assert result == 2

    def test_ingest_no_files(self, setup_ducklake, mesh_dirs):
        result = ingest_files(
            archive_dir=str(mesh_dirs["archive"]),
            catalog_path=setup_ducklake["catalog_path"],
            data_path=setup_ducklake["data_path"],
        )
        assert result == 0

    def test_ingest_from_inbox_fallback(
        self, setup_ducklake, mesh_dirs, sample_csv_content
    ):
        inbox_file = mesh_dirs["inbox"] / "Flu_Vaccinations_v5_TEST_inbox.csv"
        inbox_file.write_text(sample_csv_content, encoding="utf-8")

        result = ingest_files(
            archive_dir=str(mesh_dirs["archive"]),
            catalog_path=setup_ducklake["catalog_path"],
            data_path=setup_ducklake["data_path"],
        )
        assert result == 2

    def test_ingest_data_in_table(self, setup_ducklake, sample_csv_file, mesh_dirs):
        import duckdb

        ingest_files(
            archive_dir=str(mesh_dirs["archive"]),
            catalog_path=setup_ducklake["catalog_path"],
            data_path=setup_ducklake["data_path"],
        )

        conn = duckdb.connect()
        conn.execute("INSTALL ducklake")
        conn.execute("LOAD ducklake")
        conn.execute(
            f"ATTACH 'ducklake:{setup_ducklake['catalog_path']}' AS vaccination_lake "
            f"(READ_ONLY, DATA_PATH '{setup_ducklake['data_path']}')"
        )
        count = conn.execute(
            "SELECT COUNT(*) FROM vaccination_lake.staging.stg_vaccinations"
        ).fetchone()[0]
        conn.close()
        assert count == 2

    def test_ingest_multiple_files(self, setup_ducklake, mesh_dirs, sample_csv_content):
        for i in range(3):
            filepath = mesh_dirs["archive"] / f"Flu_Vaccinations_v5_TEST_{i}.csv"
            filepath.write_text(sample_csv_content, encoding="utf-8")

        result = ingest_files(
            archive_dir=str(mesh_dirs["archive"]),
            catalog_path=setup_ducklake["catalog_path"],
            data_path=setup_ducklake["data_path"],
        )
        assert result == 6
