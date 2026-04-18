import json
from pathlib import Path
from unittest.mock import patch

import pytest

from duck_lakehouse.ducklake.init_ducklake import init_ducklake, create_schemas, create_staging_tables


@pytest.fixture
def initialized_db(ducklake_dirs, mesh_dirs):
    catalog_path = ducklake_dirs["catalog_path"]
    data_path = ducklake_dirs["data_path"]
    conn = init_ducklake(catalog_path=catalog_path, data_path=data_path)
    create_schemas(conn)
    create_staging_tables(conn)
    conn.close()
    return {
        "catalog_path": catalog_path,
        "data_path": data_path,
        "archive_dir": str(mesh_dirs["archive"]),
        "inbox_dir": str(mesh_dirs["inbox"]),
        "processing_dir": str(mesh_dirs["processing"]),
        "logs_dir": str(mesh_dirs["logs"]),
    }


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"


class TestStatusEndpoint:
    def test_status_returns_all_stages(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.get_json()
        for stage in ["generate", "mesh", "init", "ingest", "dbt"]:
            assert stage in data
            assert "state" in data[stage]


class TestFilesEndpoint:
    def test_files_inbox_empty(self, client, mesh_dirs):
        resp = client.get("/api/files/inbox")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["files"] == []

    def test_files_inbox_with_files(self, client, mesh_dirs):
        filepath = mesh_dirs["inbox"] / "test.csv"
        filepath.write_text("data\r\n", encoding="utf-8")

        resp = client.get("/api/files/inbox")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["files"]) == 1
        assert data["files"][0]["name"] == "test.csv"

    def test_files_invalid_stage(self, client):
        resp = client.get("/api/files/invalid")
        assert resp.status_code == 400

    def test_files_all_dirs(self, client, mesh_dirs):
        for stage in ["inbox", "processing", "archive", "logs", "catalog", "data"]:
            resp = client.get(f"/api/files/{stage}")
            assert resp.status_code == 200


class TestTablesEndpoint:
    def test_tables_empty_without_init(self, client):
        resp = client.get("/api/tables")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "tables" in data


class TestPreviewEndpoint:
    def test_preview_csv_sample_no_files(self, client, mesh_dirs):
        resp = client.get("/api/preview/csv_sample")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "headers" in data

    def test_preview_csv_sample_with_file(self, client, mesh_dirs, sample_csv_content):
        filepath = mesh_dirs["inbox"] / "test.csv"
        filepath.write_text(sample_csv_content, encoding="utf-8")

        resp = client.get("/api/preview/csv_sample")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["headers"]) > 0

    def test_preview_invalid_stage(self, client):
        resp = client.get("/api/preview/invalid")
        assert resp.status_code == 400


class TestSqlEndpoint:
    def test_sql_empty_query(self, client):
        resp = client.post("/api/sql", json={"query": ""})
        assert resp.status_code == 400

    def test_sql_no_query(self, client):
        resp = client.post("/api/sql", json={})
        assert resp.status_code == 400

    def test_sql_forbidden_insert(self, client):
        resp = client.post("/api/sql", json={"query": "INSERT INTO foo VALUES (1)"})
        assert resp.status_code == 403

    def test_sql_forbidden_drop(self, client):
        resp = client.post("/api/sql", json={"query": "DROP TABLE foo"})
        assert resp.status_code == 403

    def test_sql_forbidden_delete(self, client):
        resp = client.post("/api/sql", json={"query": "DELETE FROM foo"})
        assert resp.status_code == 403

    def test_sql_forbidden_create(self, client):
        resp = client.post("/api/sql", json={"query": "CREATE TABLE foo (id INT)"})
        assert resp.status_code == 403

    def test_sql_forbidden_alter(self, client):
        resp = client.post("/api/sql", json={"query": "ALTER TABLE foo ADD COLUMN x INT"})
        assert resp.status_code == 403

    def test_sql_forbidden_keyword_in_select(self, client):
        resp = client.post(
            "/api/sql",
            json={"query": "INSERT INTO staging.stg_vaccinations SELECT * FROM staging.stg_vaccinations"},
        )
        assert resp.status_code == 403


class TestSampleFiles:
    def test_list_sample_files_empty(self, client, mesh_dirs):
        resp = client.get("/api/sample-files")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["files"] == []

    def test_list_sample_files_with_data(self, client, mesh_dirs):
        filepath = mesh_dirs["inbox"] / "Flu_Vaccinations_v5_TEST.csv"
        filepath.write_text("a|b\r\n1|2\r\n", encoding="utf-8")

        resp = client.get("/api/sample-files")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["files"]) >= 1


class TestCleanEndpoint:
    def test_clean_resets_status(self, client, initialized_db, mesh_dirs):
        filepath = mesh_dirs["archive"] / "test.csv"
        filepath.write_text("data\r\n", encoding="utf-8")

        resp = client.post("/api/clean")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("success") is True

        status_resp = client.get("/api/status")
        status_data = status_resp.get_json()
        for stage in status_data.values():
            assert stage["state"] == "idle"