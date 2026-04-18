#!/usr/bin/env python3
"""
DuckLake Dashboard - Flask backend for pipeline visualization and control

Concurrency strategy for DuckDB:
  DuckDB does not support concurrent access to the same .ducklake catalog.
  Even read-only ATTACHes take a shared file lock that blocks writers.

  Our approach:
  - Read queries use ATTACH with READ_ONLY flag to minimise lock contention.
  - A _write_in_progress Event signals when a write operation (init/ingest/dbt)
    is running. Read queries check this and return a "busy" response rather than
    competing for the file lock.
  - Write operations acquire _pipeline_lock to run exclusively.
  - All connections are short-lived: open → query → close.
  - Frontend polling handles "busy" responses gracefully.
"""

import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import duckdb
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).parent.parent
MESH_DIR = BASE_DIR / "duck_lakehouse" / "mesh_simulator"
DBT_DIR = BASE_DIR / "dbt" / "dbt_ducklake"
DUCKLAKE_DIR = BASE_DIR / "duck_lakehouse" / "ducklake"

ARCHIVE_DIR = Path(os.environ.get("MESH_ARCHIVE_DIR", str(MESH_DIR / "archive")))
INBOX_DIR = Path(os.environ.get("MESH_INBOX_DIR", str(MESH_DIR / "inbox")))
PROCESSING_DIR = Path(os.environ.get("MESH_PROCESSING_DIR", str(MESH_DIR / "processing")))
LOGS_DIR = Path(os.environ.get("MESH_LOGS_DIR", str(MESH_DIR / "logs")))
CATALOG_PATH = Path(os.environ.get("DUCKLAKE_CATALOG", str(DUCKLAKE_DIR / "catalog" / "vaccination_lake.ducklake")))
DATA_PATH = Path(os.environ.get("DUCKLAKE_DATA", str(DUCKLAKE_DIR / "data")))
CATALOG_DIR = CATALOG_PATH.parent
DATA_DIR = DATA_PATH

# ---- Concurrency control ----
# _pipeline_lock: serialises write operations (init/ingest/dbt)
# _write_in_progress: Event set while a write op runs; reads check and back off
_pipeline_lock = threading.Lock()
_write_in_progress = threading.Event()

status = {
    "generate": {"state": "idle", "output": [], "last_run": None},
    "mesh": {"state": "idle", "output": [], "last_run": None},
    "init": {"state": "idle", "output": [], "last_run": None},
    "ingest": {"state": "idle", "output": [], "last_run": None},
    "dbt": {"state": "idle", "output": [], "last_run": None},
}

cached_tables = []


def get_ducklake_conn(read_only=False):
    """Open a short-lived connection to the DuckLake catalog.

    read_only=True uses ATTACH ... (READ_ONLY) which takes a shared lock
    instead of an exclusive lock. This still blocks writers, but is safer
    for concurrent reads.

    For write operations, use read_only=False (default).
    """
    conn = duckdb.connect()
    conn.execute("INSTALL ducklake")
    conn.execute("LOAD ducklake")
    if read_only:
        conn.execute(
            f"ATTACH 'ducklake:{CATALOG_PATH}' "
            f"AS vaccination_lake (READ_ONLY, DATA_PATH '{DATA_PATH}')"
        )
    else:
        conn.execute(
            f"ATTACH 'ducklake:{CATALOG_PATH}' "
            f"AS vaccination_lake (DATA_PATH '{DATA_PATH}', OVERRIDE_DATA_PATH true)"
        )
    conn.execute("USE vaccination_lake")
    return conn


def _get_read_conn():
    """Get a read-only connection, or None if DB is busy or catalog missing.

    Returns (conn, busy_flag). If busy_flag is True, conn is None.
    Caller MUST close conn when done.
    """
    if _write_in_progress.is_set():
        return None, True
    if not CATALOG_PATH.exists():
        return None, False
    try:
        return get_ducklake_conn(read_only=True), False
    except Exception:
        # Fallback: try write-mode connection (single worker, low traffic)
        try:
            return get_ducklake_conn(read_only=False), False
        except Exception:
            return None, False


def _refresh_table_cache():
    """Populate cached_tables from DuckLake metadata."""
    global cached_tables
    try:
        conn, busy = _get_read_conn()
        if conn is None:
            return
        try:
            names = _discover_tables(conn)
            tables = []
            for fq_name in names:
                try:
                    # Quote schema.table to handle dotted names correctly
                    schema, table = fq_name.split(".", 1)
                    count = conn.execute(
                        f'SELECT COUNT(*) FROM vaccination_lake."{schema}"."{table}"'
                    ).fetchone()[0]
                except Exception:
                    count = None
                tables.append({"name": fq_name, "rows": count})
            cached_tables = tables
        finally:
            conn.close()
    except Exception:
        pass


def run_command(cmd, cwd=None, stage=None):
    """Run a command and stream output via SSE.

    For write operations (init/ingest/dbt), acquires the pipeline lock
    and sets _write_in_progress so reads back off.
    """
    write_stages = {"init", "ingest", "dbt"}
    needs_lock = stage in write_stages

    if needs_lock:
        if not _pipeline_lock.acquire(blocking=False):
            def stream():
                msg = f"Cannot run {stage}: another write operation is in progress. Please wait."
                status[stage]["state"] = "error"
                status[stage]["output"] = [msg]
                yield f"data: {json.dumps({'stage': stage, 'error': msg})}\n\n"
                yield f"data: {json.dumps({'stage': stage, 'done': True, 'exit_code': 1})}\n\n"
            return stream

        _write_in_progress.set()

    status[stage]["state"] = "running"
    status[stage]["output"] = []
    status[stage]["last_run"] = datetime.now().isoformat()

    def stream():
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=cwd or str(BASE_DIR),
                text=True,
                bufsize=1,
                env={**os.environ, "PYTHONUNBUFFERED": "1"}
            )

            for line in process.stdout:
                status[stage]["output"].append(line.rstrip())
                yield f"data: {json.dumps({'stage': stage, 'line': line.rstrip()})}\n\n"

            process.wait()
            exit_code = process.returncode
            if exit_code == 0:
                status[stage]["state"] = "success"
            else:
                status[stage]["state"] = "error"
            yield f"data: {json.dumps({'stage': stage, 'done': True, 'exit_code': exit_code})}\n\n"

        except Exception as e:
            exit_code = 1
            status[stage]["state"] = "error"
            yield f"data: {json.dumps({'stage': stage, 'error': str(e)})}\n\n"
        finally:
            if needs_lock:
                _write_in_progress.clear()
                _pipeline_lock.release()
            # Refresh cache AFTER releasing the write lock so reads can succeed
            if exit_code == 0 and stage in ("init", "ingest", "dbt"):
                _refresh_table_cache()

    return stream


# ---- Routes ----

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory("static", path)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/status")
def get_status():
    return jsonify(status)


@app.route("/api/files/<path:stage>")
def get_files(stage):
    """List files for a given stage."""
    try:
        if stage == "inbox":
            path = INBOX_DIR
        elif stage == "processing":
            path = PROCESSING_DIR
        elif stage == "archive":
            path = ARCHIVE_DIR
        elif stage == "logs":
            path = LOGS_DIR
        elif stage == "catalog":
            path = CATALOG_DIR
        elif stage == "data":
            path = DATA_DIR
        else:
            return jsonify({"error": "Unknown stage"}), 400

        if not path.exists():
            return jsonify({"files": []})

        files = []
        for f in sorted(path.iterdir()):
            if f.is_file():
                stat = f.stat()
                files.append({
                    "name": f.name,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/preview/<stage>")
def preview_data(stage):
    """Preview data from various stages."""
    try:
        if stage == "csv_sample":
            archive = ARCHIVE_DIR
            csv_files = sorted(archive.glob("*.csv"))
            inbox_files = sorted((INBOX_DIR).glob("*.csv"))
            all_files = inbox_files + csv_files
            if not all_files:
                return jsonify({"headers": [], "rows": [], "source": "No CSV files"})
            csv_file = all_files[0]

            with open(csv_file, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.strip().split("\r\n") if "\r\n" in content else content.strip().split("\n")
                if not lines:
                    return jsonify({"headers": [], "rows": [], "source": str(csv_file.name)})

                import re
                field_re = re.compile(r'"([^"]*)"')
                headers = [m.group(1) for m in field_re.finditer(lines[0])]
                rows = []
                for line in lines[1:11]:
                    if line.strip():
                        values = [m.group(1) for m in field_re.finditer(line)]
                        rows.append(dict(zip(headers, values)))

                return jsonify({
                    "headers": headers[:10],
                    "rows": [{k: v for k, v in row.items() if k in headers[:10]} for row in rows],
                    "source": csv_file.name
                })

        elif stage == "staging":
            conn, busy = _get_read_conn()
            if conn is None:
                if busy:
                    return jsonify({"error": "Database is busy — a write operation is in progress", "busy": True})
                return jsonify({"headers": [], "rows": []})
            try:
                tables = [t for t in _discover_tables(conn) if "stg_" in t]
                result = []
                columns = []
                if tables:
                    try:
                        result = conn.execute(f"SELECT * FROM vaccination_lake.{tables[0]} LIMIT 5").fetchall()
                        columns = [desc[0] for desc in conn.description]
                    except Exception:
                        pass

                rows = []
                for row in result:
                    row_dict = {}
                    for i, col in enumerate(columns[:8]):
                        row_dict[col] = str(row[i])[:50] if row[i] is not None else None
                    rows.append(row_dict)

                return jsonify({"headers": columns[:8], "rows": rows})
            finally:
                conn.close()

        elif stage == "marts":
            conn, busy = _get_read_conn()
            if conn is None:
                if busy:
                    return jsonify({"error": "Database is busy — a write operation is in progress", "busy": True})
                return jsonify({"headers": [], "rows": []})
            try:
                tables = [t for t in _discover_tables(conn) if "fct_" in t]
                result = []
                columns = []
                if tables:
                    try:
                        result = conn.execute(f"SELECT * FROM vaccination_lake.{tables[0]} LIMIT 5").fetchall()
                        columns = [desc[0] for desc in conn.description]
                    except Exception:
                        pass

                rows = []
                for row in result:
                    row_dict = {}
                    for i, col in enumerate(columns[:8]):
                        row_dict[col] = str(row[i])[:50] if row[i] is not None else None
                    rows.append(row_dict)

                return jsonify({"headers": columns[:8], "rows": rows})
            finally:
                conn.close()

        elif stage == "row_counts":
            conn, busy = _get_read_conn()
            if conn is None:
                if busy:
                    return jsonify({"staging": 0, "marts": 0, "busy": True})
                return jsonify({"staging": 0, "marts": 0})
            try:
                staging_count = 0
                marts_count = 0
                for tname in _discover_tables(conn):
                    if "stg_" in tname:
                        try:
                            staging_count = conn.execute(f"SELECT COUNT(*) FROM vaccination_lake.{tname}").fetchone()[0]
                        except Exception:
                            pass
                    if "fct_" in tname:
                        try:
                            marts_count = conn.execute(f"SELECT COUNT(*) FROM vaccination_lake.{tname}").fetchone()[0]
                        except Exception:
                            pass
                return jsonify({"staging": staging_count, "marts": marts_count})
            finally:
                conn.close()

        return jsonify({"error": "Unknown preview stage"}), 400

    except Exception as e:
        if "lock" in str(e).lower() or "conflict" in str(e).lower():
            if stage == "row_counts":
                return jsonify({"staging": 0, "marts": 0, "busy": True})
            return jsonify({"error": "Database is busy", "busy": True})
        return jsonify({"error": str(e)}), 500


@app.route("/api/sample-files")
def list_sample_files():
    """List all CSV files in inbox with summary info."""
    try:
        inbox = INBOX_DIR
        archive = ARCHIVE_DIR
        results = []

        for csv_dir, location in [(inbox, "inbox"), (archive, "archive")]:
            if not csv_dir.exists():
                continue
            for f in sorted(csv_dir.glob("*.csv")):
                lines_count = 0
                vaccine_type = f.stem.split("_")[0] if "_" in f.stem else f.stem
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        for _ in fh:
                            lines_count += 1
                except Exception:
                    pass

                results.append({
                    "name": f.name,
                    "location": location,
                    "size": f.stat().st_size,
                    "rows": max(0, lines_count - 1),
                    "vaccine_type": vaccine_type,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                })

        return jsonify({"files": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sample-file/<path:filename>")
def preview_sample_file(filename):
    """Preview a specific CSV file from inbox or archive."""
    try:
        for csv_dir in [(INBOX_DIR, "inbox"), (ARCHIVE_DIR, "archive")]:
            csv_dir_path, location = csv_dir
            filepath = csv_dir_path / filename
            if filepath.exists() and filepath.suffix == ".csv":
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    lines = content.strip().split("\r\n") if "\r\n" in content else content.strip().split("\n")
                    if not lines:
                        return jsonify({"headers": [], "rows": [], "total_rows": 0, "source": filename, "location": location})

                    import re
                    field_re = re.compile(r'"([^"]*)"')
                    headers = [m.group(1) for m in field_re.finditer(lines[0])]
                    rows = []
                    for line in lines[1:51]:
                        if line.strip():
                            values = [m.group(1) for m in field_re.finditer(line)]
                            rows.append(dict(zip(headers, values)))

                    return jsonify({
                        "headers": headers,
                        "rows": rows,
                        "total_rows": len(lines) - 1,
                        "source": filename,
                        "location": location,
                        "size": filepath.stat().st_size,
                    })

        return jsonify({"error": f"File not found: {filename}"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


EXCLUDE_SCHEMAS = {"main", "information_schema", "pg_catalog"}
EXCLUDE_PREFIXES = ("ducklake_", "__ducklake_metadata")


def _discover_tables(conn=None):
    """Query DuckLake metadata to discover all user tables and views."""
    own_conn = conn is None
    if own_conn:
        try:
            conn, busy = _get_read_conn()
            if conn is None:
                return []
        except Exception:
            return []
    try:
        tables = conn.execute("""
            SELECT schema_name, table_name
            FROM duckdb_tables()
            WHERE database_name = 'vaccination_lake'
        """).fetchall()
        views = conn.execute("""
            SELECT schema_name, view_name
            FROM duckdb_views()
            WHERE database_name = 'vaccination_lake'
        """).fetchall()

        result = []
        for schema, name in tables + views:
            if schema in EXCLUDE_SCHEMAS:
                continue
            if any(schema.startswith(p) or name.startswith(p) for p in EXCLUDE_PREFIXES):
                continue
            result.append(f"{schema}.{name}")
        return sorted(result)
    except Exception:
        return []
    finally:
        if own_conn:
            try:
                conn.close()
            except Exception:
                pass


@app.route("/api/tables")
def list_tables():
    """List tables from cache, refreshing if empty."""
    if not cached_tables:
        _refresh_table_cache()
    return jsonify({"tables": cached_tables})


@app.route("/api/query/<path:table_name>")
def query_table(table_name):
    """Query a DuckLake table with pagination support."""
    allowed = {t["name"] for t in cached_tables} or set(_discover_tables())
    if table_name not in allowed:
        return jsonify({"error": f"Table not found: {table_name}"}), 400

    conn, busy = _get_read_conn()
    if conn is None:
        if busy:
            return jsonify({"error": "Database is busy — a write operation is in progress", "busy": True}), 503
        return jsonify({"error": "Cannot connect to DuckLake"}), 500

    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
        limit = min(limit, 200)
        offset = max(offset, 0)

        total = conn.execute(f"SELECT COUNT(*) FROM vaccination_lake.{table_name}").fetchone()[0]

        result = conn.execute(
            f"SELECT * FROM vaccination_lake.{table_name} LIMIT {limit} OFFSET {offset}"
        ).fetchall()
        columns = [desc[0] for desc in conn.description]

        rows = []
        for row in result:
            row_dict = {}
            for i, col in enumerate(columns):
                val = row[i]
                if val is None:
                    row_dict[col] = None
                elif isinstance(val, (int, float)):
                    row_dict[col] = val
                else:
                    row_dict[col] = str(val)[:200]
            rows.append(row_dict)

        return jsonify({
            "table": table_name,
            "columns": columns,
            "rows": rows,
            "total": total,
            "limit": limit,
            "offset": offset,
        })
    except Exception as e:
        if "lock" in str(e).lower() or "conflict" in str(e).lower():
            return jsonify({"error": "Database is busy", "busy": True}), 503
        return jsonify({"error": str(e)})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.route("/api/run/<stage>")
def run_stage(stage):
    """Stream output from running a pipeline stage."""
    def generate():
        if stage == "generate":
            # Write to the same inbox that MESH simulator reads from
            # (ARCHIVE_DIR.parent/inbox, which respects MESH_ARCHIVE_DIR env var)
            cmd = [sys.executable, "-m", "duck_lakehouse.data_generator",
                   "--output", str(ARCHIVE_DIR.parent / "inbox"),
                   "--records", "100", "--type", "all"]
        elif stage == "mesh":
            # Use ARCHIVE_DIR's parent as base-dir so generated files
            # land where ingest expects them (respects MESH_ARCHIVE_DIR env var)
            cmd = [sys.executable, "-m", "duck_lakehouse.mesh_simulator",
                   "--base-dir", str(ARCHIVE_DIR.parent), "--once"]
        elif stage == "init":
            cmd = [sys.executable, "-c",
                   f"from duck_lakehouse.ducklake.init_ducklake import main; main("
                   f"catalog_path='{CATALOG_PATH}', data_path='{DATA_PATH}')"]
        elif stage == "ingest":
            cmd = [sys.executable, "-c",
                   f"from duck_lakehouse.ducklake.ingest import ingest_files; "
                   f"ingest_files(archive_dir='{ARCHIVE_DIR}', "
                   f"catalog_path='{CATALOG_PATH}', data_path='{DATA_PATH}')"]
        elif stage == "dbt":
            dbt_target = os.environ.get("DBT_TARGET", "dev")
            cmd = ["bash", "-c",
                   f"dbt deps --project-dir {DBT_DIR} && "
                   f"dbt run --profiles-dir {DBT_DIR} "
                   f"--project-dir {DBT_DIR} --target {dbt_target}"]
        else:
            yield f"data: {json.dumps({'error': 'Unknown stage'})}\n\n"
            return

        yield from run_command(cmd, cwd=str(BASE_DIR), stage=stage)()

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/run/dbt-test")
def run_dbt_test():
    """Run dbt tests."""
    def generate():
        dbt_target = os.environ.get("DBT_TARGET", "dev")
        cmd = ["dbt", "test", "--profiles-dir", str(DBT_DIR),
               "--project-dir", str(DBT_DIR), "--target", dbt_target]
        yield from run_command(cmd, cwd=str(BASE_DIR), stage="dbt")()

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/clean", methods=["POST"])
def clean_all():
    """Clean generated data."""
    try:
        import shutil

        # Clean MESH directories
        for path in [INBOX_DIR, PROCESSING_DIR, ARCHIVE_DIR]:
            if path.exists():
                for f in path.glob("*.csv"):
                    f.unlink()

        # Clean logs
        logs = LOGS_DIR
        if logs.exists():
            for f in logs.glob("*.jsonl"):
                f.unlink()

        # Clean DuckLake catalog and data
        catalog = CATALOG_DIR
        if catalog.exists():
            shutil.rmtree(catalog)
        data = DATA_DIR
        if data.exists():
            shutil.rmtree(data)

        # Reset status
        for key in status:
            status[key]["state"] = "idle"
            status[key]["output"] = []
        cached_tables.clear()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


_duckdb_ui_process = None


def _start_duckdb_ui():
    """Start DuckDB local UI server with DuckLake pre-attached."""
    global _duckdb_ui_process
    if _duckdb_ui_process is not None and _duckdb_ui_process.poll() is None:
        return True
    try:
        # Check if duckdb CLI is available
        result = subprocess.run(["which", "duckdb"], capture_output=True, text=True)
        if result.returncode != 0:
            print("[DuckDB UI] duckdb CLI not found in PATH")
            return False

        init_sql = (
            f"INSTALL ducklake; LOAD ducklake; "
            f"ATTACH 'ducklake:{CATALOG_PATH}' AS vaccination_lake "
            f"(DATA_PATH '{DATA_PATH}', OVERRIDE_DATA_PATH true); "
            f"USE vaccination_lake;"
        )
        _duckdb_ui_process = subprocess.Popen(
            ["duckdb", "-c", init_sql, "-ui"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        return True
    except Exception as e:
        print(f"[DuckDB UI] Failed to start: {e}")
        return False


@app.route("/api/duckdb-ui/status")
def duckdb_ui_status():
    """Check if DuckDB UI is running."""
    running = _duckdb_ui_process is not None and _duckdb_ui_process.poll() is None
    return jsonify({"running": running})


@app.route("/api/duckdb-ui/start")
def duckdb_ui_start():
    """Start the DuckDB UI."""
    if _start_duckdb_ui():
        return jsonify({"status": "started"})
    return jsonify({"status": "error", "message": "Failed to start DuckDB UI"}), 500


@app.route("/duckdb-ui")
@app.route("/duckdb-ui/")
@app.route("/duckdb-ui/<path:subpath>")
def duckdb_ui_proxy(subpath=""):
    """Reverse proxy DuckDB UI through the dashboard so remote clients can access it."""
    if _duckdb_ui_process is None or _duckdb_ui_process.poll() is not None:
        return jsonify({"error": "DuckDB UI not running"}), 503
    try:
        import requests as req
        target = f"http://127.0.0.1:4213/{subpath}"
        fwd_headers = {k: v for k, v in request.headers if k.lower() not in ("host", "origin", "referer")}
        resp = req.request(
            method=request.method,
            url=target,
            headers=fwd_headers,
            data=request.get_data(),
            params=request.args,
            allow_redirects=False,
        )
        excluded = {"transfer-encoding", "content-encoding", "connection"}
        out_headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in excluded]
        content = resp.content
        ct = resp.headers.get("content-type", "")
        if "text/html" in ct:
            text = content.decode("utf-8", errors="replace")
            text = text.replace('<base href="/"/>', '<base href="/duckdb-ui/">')
            content = text.encode("utf-8")
        elif "javascript" in ct or "text/javascript" in ct:
            text = content.decode("utf-8", errors="replace")
            text = text.replace('localhost:4213', f'{request.host}/duckdb-ui')
            text = text.replace('"ws://', f'"wss://{request.host}/duckdb-ui/ws/')
            content = text.encode("utf-8")
        return Response(content, status=resp.status_code, headers=out_headers)
    except Exception as e:
        return jsonify({"error": str(e)}), 502


if __name__ == "__main__":
    import socket
    port = int(os.environ.get("DUCKLAKE_PORT", os.environ.get("PORT", "8765")))
    host = os.environ.get("DUCKLAKE_HOST", "0.0.0.0")
    print("Starting DuckLake Dashboard...")
    print(f"Base directory: {BASE_DIR}")
    print(f"Listening on http://{host}:{port}")
    debug = os.environ.get("FLASK_ENV") != "production"
    app.run(debug=debug, host=host, port=port, threaded=True)