.PHONY: init generate send ingest dbt-run dbt-test smoke clean up down

DUCKLAKE_BASE ?= duck_lakehouse/ducklake
MESH_DIR       ?= duck_lakehouse/mesh_simulator
RECORDS        ?= 200
ORG_CODE        ?= ABC123

init:
	@echo "=== Initialising DuckLake ==="
	python -c "from duck_lakehouse.ducklake.init_ducklake import main; main()"

generate:
	@echo "=== Generating v5 vaccination data ==="
	python -m duck_lakehouse.data_generator --output $(MESH_DIR)/inbox --records $(RECORDS) --org-code $(ORG_CODE)

send:
	@echo "=== Moving generated files to MESH inbox ==="
	@if [ -d duck_lakehouse/data/generated ]; then \
		cp duck_lakehouse/data/generated/*.csv $(MESH_DIR)/inbox/ 2>/dev/null || echo "No files to copy"; \
	fi

ingest:
	@echo "=== Running MESH simulator ==="
	python -m duck_lakehouse.mesh_simulator --once
	@echo "=== Ingesting into DuckLake ==="
	python -m duck_lakehouse.ducklake.ingest

dbt-run:
	@echo "=== Running dbt models ==="
	cd dbt/dbt_ducklake && dbt run --profiles-dir .

dbt-test:
	@echo "=== Running dbt tests ==="
	cd dbt/dbt_ducklake && dbt test --profiles-dir .

smoke: init generate ingest dbt-run dbt-test
	@echo "=== Smoke test complete ==="

clean:
	@echo "=== Cleaning generated data ==="
	rm -rf $(DUCKLAKE_BASE)/catalog/*.ducklake
	rm -rf $(DUCKLAKE_BASE)/data/*.parquet
	rm -rf $(MESH_DIR)/archive/*.csv
	rm -rf $(MESH_DIR)/processing/*.csv
	rm -rf $(MESH_DIR)/inbox/*.csv
	rm -rf $(MESH_DIR)/logs/*.jsonl

up:
	docker compose up -d

down:
	docker compose down